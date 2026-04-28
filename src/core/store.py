"""
SQLite storage backend for MemOS Local (Hermes Agent).
Extended version with command tracking, decisions, preferences, and knowledge health.
"""

import sqlite3
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SqliteStore:
    """SQLite-based storage for conversation memories."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Chunks table - stores conversation memory chunks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                sessionKey TEXT NOT NULL,
                turnId TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT DEFAULT 'paragraph',
                summary TEXT,
                owner TEXT DEFAULT 'local',
                visibility TEXT DEFAULT 'private',
                sharedWith TEXT,
                taskId TEXT,
                skillId TEXT,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                UNIQUE(sessionKey, turnId, seq)
            )
        """)

        # Tasks table - stores task summaries (for skill generation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                summary TEXT,
                owner TEXT DEFAULT 'local',
                startedAt INTEGER NOT NULL,
                endedAt INTEGER,
                updatedAt INTEGER NOT NULL
            )
        """)

        # Skills table - stores learned skills (optional feature)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                taskId TEXT,
                owner TEXT DEFAULT 'local',
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL
            )
        """)

        # Task-Skill relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_skills (
                taskId TEXT NOT NULL,
                skillId TEXT NOT NULL,
                relation TEXT DEFAULT 'derived',
                PRIMARY KEY (taskId, skillId)
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(sessionKey)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_role ON chunks(role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_visibility ON chunks(visibility)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_shared ON chunks(sharedWith)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_task ON chunks(taskId)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_owner ON skills(owner)")
        
        # FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content, summary, content='chunks', content_rowid='rowid'
            )
        """)
        
        # Embeddings table for vector search
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                chunkId TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                createdAt INTEGER NOT NULL,
                FOREIGN KEY (chunkId) REFERENCES chunks(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON embeddings(chunkId)")

        # ========== Direction A: Command History & Patterns ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                command TEXT NOT NULL,
                args TEXT,
                project_path TEXT,
                exit_code INTEGER,
                working_dir TEXT,
                session_key TEXT,
                createdAt INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_history_owner ON command_history(owner)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_history_project ON command_history(project_path)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_patterns (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                command TEXT NOT NULL,
                project_path TEXT,
                frequency INTEGER DEFAULT 1,
                last_used_at INTEGER NOT NULL,
                success_rate REAL DEFAULT 1.0,
                avg_exit_code REAL DEFAULT 0.0,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                UNIQUE(owner, command, project_path)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_patterns_owner ON command_patterns(owner)")

        # ========== Direction B: Decisions ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                project TEXT,
                title TEXT NOT NULL,
                context TEXT,
                chosen TEXT,
                alternatives TEXT,
                outcome TEXT,
                status TEXT DEFAULT 'active',
                tags TEXT,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_owner ON decisions(owner)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_cards (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                rationale TEXT,
                impact TEXT,
                createdAt INTEGER NOT NULL,
                FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_cards_id ON decision_cards(decision_id)")

        # ========== Direction C: User Preferences & Behavior Patterns ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                confidence REAL DEFAULT 1.0,
                source TEXT DEFAULT 'explicit',
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                UNIQUE(owner, category, key)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_owner ON user_preferences(owner)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS behavior_patterns (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                description TEXT,
                data TEXT,
                frequency INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                last_seen_at INTEGER NOT NULL,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_behavior_owner ON behavior_patterns(owner)")

        # ========== Direction D: Knowledge Health & Forgetting Schedule ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_health (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                topic TEXT NOT NULL,
                source TEXT,
                freshness_score REAL DEFAULT 1.0,
                accuracy_score REAL DEFAULT 1.0,
                completeness_score REAL DEFAULT 1.0,
                last_verified_at INTEGER,
                next_review_at INTEGER,
                metadata TEXT,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                UNIQUE(owner, topic)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_owner ON knowledge_health(owner)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_knowledge_map (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                topic TEXT NOT NULL,
                expert TEXT,
                resource_url TEXT,
                description TEXT,
                tags TEXT,
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL,
                UNIQUE(owner, topic)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tkm_owner ON team_knowledge_map(owner)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forgetting_schedule (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                chunk_id TEXT,
                topic TEXT,
                interval_days REAL DEFAULT 1.0,
                ease_factor REAL DEFAULT 2.5,
                repetitions INTEGER DEFAULT 0,
                next_review_at INTEGER NOT NULL,
                last_reviewed_at INTEGER,
                status TEXT DEFAULT 'pending',
                createdAt INTEGER NOT NULL,
                updatedAt INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_owner ON forgetting_schedule(owner)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_due ON forgetting_schedule(next_review_at)")

        self.conn.commit()
        logger.info(f"memos-local: database initialized at {self.db_path}")

    def insert_chunk(self, chunk: Dict[str, Any]) -> str:
        """Insert a memory chunk."""
        import uuid
        from datetime import datetime

        chunk_id = chunk.get("id") or str(uuid.uuid4())
        now = int(datetime.now().timestamp() * 1000)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO chunks 
            (id, sessionKey, turnId, seq, role, content, kind, summary, owner, visibility, sharedWith, taskId, skillId, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chunk_id,
            chunk.get("sessionKey", "default"),
            chunk.get("turnId", ""),
            chunk.get("seq", 0),
            chunk.get("role", "assistant"),
            chunk.get("content", ""),
            chunk.get("kind", "paragraph"),
            chunk.get("summary"),
            chunk.get("owner", "local"),
            chunk.get("visibility", "private"),
            chunk.get("sharedWith"),
            chunk.get("taskId"),
            chunk.get("skillId"),
            now,
            now,
        ))

        self.conn.commit()
        return chunk_id

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a chunk by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_neighbor_chunks(
        self,
        session_key: str,
        turn_id: str,
        seq: int,
        window: int = 2,
    ) -> List[Dict[str, Any]]:
        """Get chunks surrounding a specific chunk."""
        cursor = self.conn.cursor()

        # Get chunks in the same session within the window
        min_seq = seq - window
        max_seq = seq + window

        cursor.execute("""
            SELECT * FROM chunks 
            WHERE sessionKey = ? AND seq >= ? AND seq <= ?
            ORDER BY seq ASC
        """, (session_key, min_seq, max_seq))

        return [dict(row) for row in cursor.fetchall()]

    def search_chunks(
        self,
        query: str,
        max_results: int = 10,
        min_score: float = 0.45,
        role: Optional[str] = None,
        scope: str = "private",
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search chunks with visibility scope support."""
        cursor = self.conn.cursor()

        # Build visibility filter based on scope
        visibility_filter = ""
        params = [f"%{query}%", f"%{query}%"]

        if scope == "private":
            # Only private memories owned by this agent
            visibility_filter = " AND (visibility = 'private' OR visibility IS NULL)"
            if agent_id:
                visibility_filter += " AND (owner = ? OR owner IS NULL)"
                params.append(agent_id)
        elif scope == "shared":
            # Only shared memories
            visibility_filter = " AND visibility = 'shared'"
            if agent_id:
                # Include memories shared with this agent
                visibility_filter += " AND (sharedWith IS NULL OR sharedWith LIKE ?)"
                params.append(f"%{agent_id}%")
        elif scope == "all":
            # All memories (private + shared)
            if agent_id:
                # Private owned by agent + all shared
                visibility_filter = " AND (visibility = 'shared' OR owner = ? OR visibility IS NULL)"
                params.append(agent_id)

        if role:
            visibility_filter += " AND role = ?"
            params.append(role)

        cursor.execute(f"""
            SELECT * FROM chunks 
            WHERE (content LIKE ? OR summary LIKE ?){visibility_filter}
            ORDER BY createdAt DESC
            LIMIT ?
        """, params + [max_results])

        results = []
        for row in cursor.fetchall():
            chunk = dict(row)
            # Simple scoring based on match position
            score = 0.5  # Base score
            if query.lower() in chunk.get("content", "").lower():
                score += 0.2
            if chunk.get("summary") and query.lower() in chunk.get("summary", "").lower():
                score += 0.1

            if score >= min_score:
                chunk["score"] = score
                results.append(chunk)

        return results[:max_results]

    def share_chunk(self, chunk_id: str, shared_with: Optional[List[str]] = None) -> bool:
        """Share a private chunk with other agents or make it globally shared."""
        cursor = self.conn.cursor()
        
        # Update visibility to shared
        shared_with_str = ",".join(shared_with) if shared_with else None
        
        cursor.execute("""
            UPDATE chunks 
            SET visibility = 'shared', 
                sharedWith = ?,
                updatedAt = ?
            WHERE id = ?
        """, (shared_with_str, int(__import__('time').time() * 1000), chunk_id))
        
        self.conn.commit()
        return cursor.rowcount > 0

    def make_chunk_private(self, chunk_id: str) -> bool:
        """Make a shared chunk private again."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE chunks 
            SET visibility = 'private', 
                sharedWith = NULL,
                updatedAt = ?
            WHERE id = ?
        """, (int(__import__('time').time() * 1000), chunk_id))
        
        self.conn.commit()
        return cursor.rowcount > 0

    def get_shared_chunks(
        self, 
        agent_id: str, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all chunks shared with a specific agent."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE visibility = 'shared' 
            AND (sharedWith IS NULL OR sharedWith LIKE ?)
            ORDER BY createdAt DESC
            LIMIT ?
        """, (f"%{agent_id}%", max_results))
        
        return [dict(row) for row in cursor.fetchall()]

    def list_agents_with_shared_memory(self) -> List[str]:
        """List all agent IDs that have shared memory."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT owner FROM chunks 
            WHERE visibility = 'shared' AND owner IS NOT NULL
        """)
        
        return [row[0] for row in cursor.fetchall() if row[0]]

    # ========== Task Management (for skill generation) ==========
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def insert_task(self, task: Dict[str, Any]) -> str:
        """Insert or update a task."""
        from datetime import datetime

        now = int(datetime.now().timestamp() * 1000)
        task_id = task.get("id", str(now))

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tasks 
            (id, title, status, summary, owner, startedAt, endedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            task.get("title", ""),
            task.get("status", "active"),
            task.get("summary"),
            task.get("owner", "local"),
            task.get("startedAt", now),
            task.get("endedAt"),
            now,
        ))

        self.conn.commit()
        return task_id

    def get_active_task(self, session_key: str, owner: str) -> Optional[Dict[str, Any]]:
        """Get active task for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE sessionKey = ? AND owner = ? AND status = 'active'
            ORDER BY startedAt DESC
            LIMIT 1
        """, (session_key, owner))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def finalize_task(self, task_id: str, summary: str) -> bool:
        """Finalize a task with summary."""
        from datetime import datetime

        now = int(datetime.now().timestamp() * 1000)
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tasks 
            SET summary = ?, status = 'completed', endedAt = ?, updatedAt = ?
            WHERE id = ?
        """, (summary, now, now, task_id))
        self.conn.commit()
        return cursor.rowcount > 0

    # ========== Skill Management (optional feature) ==========
    
    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get a skill by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def insert_skill(self, skill: Dict[str, Any]) -> str:
        """Insert or update a skill."""
        from datetime import datetime

        now = int(datetime.now().timestamp() * 1000)
        skill_id = skill.get("id", str(now))

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO skills 
            (id, name, version, content, status, taskId, owner, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            skill_id,
            skill.get("name", ""),
            skill.get("version", "1.0.0"),
            skill.get("content", ""),
            skill.get("status", "active"),
            skill.get("taskId"),
            skill.get("owner", "local"),
            now,
            now,
        ))

        self.conn.commit()
        return skill_id

    def get_skills_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Get skills associated with a task."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.* FROM skills s
            JOIN task_skills ts ON s.id = ts.skillId
            WHERE ts.taskId = ?
        """, (task_id,))
        return [dict(row) for row in cursor.fetchall()]

    def link_task_skill(self, task_id: str, skill_id: str, relation: str = "derived") -> None:
        """Link a task to a skill."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO task_skills (taskId, skillId, relation)
            VALUES (?, ?, ?)
        """, (task_id, skill_id, relation))
        self.conn.commit()

    def search_skills(
        self,
        query: str,
        max_results: int = 10,
        owner: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search skills by name or content."""
        cursor = self.conn.cursor()
        
        params = [f"%{query}%", f"%{query}%"]
        where_clause = "(name LIKE ? OR content LIKE ?) AND status = 'active'"
        
        if owner:
            where_clause += " AND (owner = ? OR owner IS NULL)"
            params.append(owner)
        
        cursor.execute(f"""
            SELECT * FROM skills 
            WHERE {where_clause}
            ORDER BY updatedAt DESC
            LIMIT ?
        """, params + [max_results])
        
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("memos-local: database connection closed")
    
    # ========== FTS Search ==========
    
    def fts_search(
        self,
        query: str,
        limit: int = 100,
        scope: str = "private",
        agent_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """FTS5 full-text search."""
        cursor = self.conn.cursor()
        
        # Build visibility filter
        visibility_filter = ""
        params = [query]
        
        if scope == "private":
            visibility_filter = " AND (c.visibility = 'private' OR c.visibility IS NULL)"
            visibility_filter += " AND (c.owner = ? OR c.owner IS NULL)"
            params.append(agent_id)
        elif scope == "shared":
            visibility_filter = " AND c.visibility = 'shared'"
        elif scope == "all":
            visibility_filter = " AND (c.visibility = 'shared' OR c.owner = ? OR c.visibility IS NULL)"
            params.append(agent_id)
        
        cursor.execute(f"""
            SELECT c.*, rank FROM chunks c
            JOIN chunks_fts f ON c.rowid = f.rowid
            WHERE chunks_fts MATCH ?{visibility_filter}
            ORDER BY rank
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            chunk = dict(row)
            # Convert rank to score (lower rank = higher score)
            chunk["score"] = 1.0 / (1 + row["rank"])
            results.append(chunk)
        
        return results
    
    def pattern_search(
        self,
        terms: List[str],
        limit: int = 100,
        scope: str = "private",
        agent_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """Pattern search for short terms (2-char bigrams)."""
        cursor = self.conn.cursor()
        
        if not terms:
            return []
        
        # Build LIKE conditions
        conditions = []
        params = []
        
        for term in terms:
            conditions.append("(c.content LIKE ? OR c.summary LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])
        
        # Build visibility filter
        visibility_filter = ""
        
        if scope == "private":
            visibility_filter = " AND (c.visibility = 'private' OR c.visibility IS NULL)"
            visibility_filter += " AND (c.owner = ? OR c.owner IS NULL)"
            params.append(agent_id)
        elif scope == "shared":
            visibility_filter = " AND c.visibility = 'shared'"
        elif scope == "all":
            visibility_filter = " AND (c.visibility = 'shared' OR c.owner = ? OR c.visibility IS NULL)"
            params.append(agent_id)
        
        cursor.execute(f"""
            SELECT c.* FROM chunks c
            WHERE ({' OR '.join(conditions)}){visibility_filter}
            ORDER BY c.createdAt DESC
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            chunk = dict(row)
            chunk["score"] = 0.5  # Base score for pattern match
            results.append(chunk)
        
        return results
    
    # ========== Vector Search ==========
    
    def insert_embedding(self, chunk_id: str, embedding: List[float]) -> None:
        """Insert embedding for a chunk."""
        import struct
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        
        # Convert float list to binary blob
        embedding_bytes = struct.pack(f'{len(embedding)}f', *embedding)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO embeddings (chunkId, embedding, createdAt)
            VALUES (?, ?, ?)
        """, (chunk_id, embedding_bytes, now))
        
        self.conn.commit()
    
    def get_embedding(self, chunk_id: str) -> Optional[List[float]]:
        """Get embedding for a chunk."""
        import struct
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT embedding FROM embeddings WHERE chunkId = ?", (chunk_id,))
        row = cursor.fetchone()
        
        if row and row[0]:
            embedding_bytes = row[0]
            # Convert binary blob back to float list
            num_floats = len(embedding_bytes) // 4
            return list(struct.unpack(f'{num_floats}f', embedding_bytes))
        
        return None
    
    def get_all_embeddings(self, owner: str = "default") -> List[Dict[str, Any]]:
        """Get all embeddings for an owner."""
        import struct
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT e.chunkId, e.embedding, c.content, c.owner
            FROM embeddings e
            JOIN chunks c ON e.chunkId = c.id
            WHERE c.owner = ? OR c.owner IS NULL
        """, (owner,))
        
        results = []
        for row in cursor.fetchall():
            embedding_bytes = row[1]
            num_floats = len(embedding_bytes) // 4
            embedding = list(struct.unpack(f'{num_floats}f', embedding_bytes))
            
            results.append({
                "id": row[0],
                "embedding": embedding,
                "content": row[2],
                "owner": row[3],
            })
        
        return results
    
    def vector_search(
        self,
        query_vec: List[float],
        limit: int = 100,
        scope: str = "private",
        agent_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """Vector similarity search."""
        import numpy as np
        
        # Get all embeddings for the owner
        all_embeddings = self.get_all_embeddings(agent_id)
        
        if not all_embeddings:
            return []
        
        query_vec = np.array(query_vec)
        
        # Calculate cosine similarity
        results = []
        for item in all_embeddings:
            chunk_id = item["id"]
            embedding = item["embedding"]
            
            if not embedding or len(embedding) != len(query_vec):
                continue
            
            vec = np.array(embedding)
            
            # Cosine similarity
            dot_product = np.dot(query_vec, vec)
            norm_q = np.linalg.norm(query_vec)
            norm_v = np.linalg.norm(vec)
            
            if norm_q == 0 or norm_v == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (norm_q * norm_v)
            
            if similarity > 0.3:  # Minimum threshold
                results.append({
                    "id": chunk_id,
                    "score": float(similarity),
                })
        
        # Sort by similarity
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:limit]
    
    # ========== Task Management (Enhanced) ==========
    
    def create_task(self, task: Dict[str, Any]) -> str:
        """Create a new task."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        task_id = task.get("id")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tasks 
            (id, title, status, summary, owner, startedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            task.get("title", task.get("goal", "")),
            task.get("status", "active"),
            task.get("summary", ""),
            task.get("owner", "local"),
            task.get("created_at", now),
            now,
        ))
        
        self.conn.commit()
        return task_id
    
    def update_task(self, task: Dict[str, Any]) -> None:
        """Update a task."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tasks 
            SET title = ?, status = ?, summary = ?, owner = ?, updatedAt = ?
            WHERE id = ?
        """, (
            task.get("title", task.get("goal", "")),
            task.get("status", "active"),
            task.get("summary", ""),
            task.get("owner", "local"),
            now,
            task.get("id"),
        ))
        
        self.conn.commit()
    
    def get_all_active_tasks(self, owner: str) -> List[Dict[str, Any]]:
        """Get all active tasks for an owner."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE owner = ? AND status = 'active'
            ORDER BY startedAt DESC
        """, (owner,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_task_messages(self, task_id: str) -> List[Dict[str, Any]]:
        """Get messages associated with a task."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE taskId = ?
            ORDER BY seq ASC
        """, (task_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_messages(self, session_key: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent messages for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE sessionKey = ?
            ORDER BY createdAt DESC
            LIMIT ?
        """, (session_key, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_chunk(self, chunk_id: str, updates: Dict[str, Any]) -> None:
        """Update a chunk."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        
        # Build update query
        fields = []
        params = []
        
        for key, value in updates.items():
            if key in ["summary", "merge_history", "merge_count"]:
                fields.append(f"{key} = ?")
                params.append(value)
        
        if not fields:
            return
        
        fields.append("updatedAt = ?")
        params.append(now)
        params.append(chunk_id)
        
        cursor = self.conn.cursor()
        cursor.execute(f"""
            UPDATE chunks 
            SET {', '.join(fields)}
            WHERE id = ?
        """, params)
        
        self.conn.commit()
    
    # ========== Skill Management (Enhanced) ==========
    
    def create_skill(self, skill: Dict[str, Any]) -> str:
        """Create a new skill."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        skill_id = skill.get("id")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO skills 
            (id, name, version, content, status, taskId, owner, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            skill_id,
            skill.get("name", ""),
            str(skill.get("version", 1)),
            skill.get("content", ""),
            skill.get("status", "active"),
            skill.get("task_id"),
            skill.get("owner", "local"),
            now,
            now,
        ))
        
        self.conn.commit()
        return skill_id
    
    def update_skill(self, skill: Dict[str, Any]) -> None:
        """Update a skill."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE skills 
            SET name = ?, version = ?, content = ?, status = ?, updatedAt = ?
            WHERE id = ?
        """, (
            skill.get("name", ""),
            str(skill.get("version", 1)),
            skill.get("content", ""),
            skill.get("status", "active"),
            now,
            skill.get("id"),
        ))
        
        self.conn.commit()
    
    def search_skills(
        self,
        query: str,
        limit: int = 10,
        scope: str = "mix",
        owner: str = "default",
    ) -> List[Dict[str, Any]]:
        """Search skills by query."""
        cursor = self.conn.cursor()
        
        params = [f"%{query}%", f"%{query}%"]
        where_clause = "(name LIKE ? OR content LIKE ?) AND status = 'active'"
        
        if scope == "self":
            where_clause += " AND owner = ?"
            params.append(owner)
        elif scope == "public":
            where_clause += " AND owner = 'public'"
        elif scope == "mix":
            where_clause += " AND (owner = ? OR owner = 'public')"
            params.append(owner)
        
        cursor.execute(f"""
            SELECT * FROM skills 
            WHERE {where_clause}
            ORDER BY updatedAt DESC
            LIMIT ?
        """, params + [limit])
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_skill_embeddings(
        self,
        scope: str,
        owner: str,
    ) -> List[Dict[str, Any]]:
        """Get embeddings for skills."""
        import struct
        
        cursor = self.conn.cursor()
        
        # This would require a separate skill_embeddings table
        # For now, return empty list
        return []
    
    def skill_fts_search(
        self,
        query: str,
        limit: int = 10,
        scope: str = "mix",
        owner: str = "default",
    ) -> List[Dict[str, Any]]:
        """FTS search for skills."""
        cursor = self.conn.cursor()
        
        params = [query]
        where_clause = "s.status = 'active'"
        
        if scope == "self":
            where_clause += " AND s.owner = ?"
            params.append(owner)
        elif scope == "public":
            where_clause += " AND s.owner = 'public'"
        elif scope == "mix":
            where_clause += " AND (s.owner = ? OR s.owner = 'public')"
            params.append(owner)
        
        cursor.execute(f"""
            SELECT s.*, rank FROM skills s
            JOIN skills_fts f ON s.rowid = f.rowid
            WHERE skills_fts MATCH ? AND {where_clause}
            ORDER BY rank
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            skill = dict(row)
            skill["score"] = 1.0 / (1 + row["rank"])
            results.append(skill)
        
        return results

    # ========== Task/Skill CRUD ==========

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its associated chunks."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM chunks WHERE taskId = ?", (task_id,))
        cursor.execute("DELETE FROM task_skills WHERE taskId = ?", (task_id,))
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_task_fields(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific task fields."""
        from datetime import datetime
        now = int(datetime.now().timestamp() * 1000)
        allowed = {"title", "status", "summary"}
        fields, params = [], []
        for k, v in updates.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        fields.append("updatedAt = ?")
        params.extend([now, task_id])
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM task_skills WHERE skillId = ?", (skill_id,))
        cursor.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_skill_fields(self, skill_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific skill fields."""
        from datetime import datetime
        now = int(datetime.now().timestamp() * 1000)
        allowed = {"name", "content", "version", "owner", "status"}
        fields, params = [], []
        for k, v in updates.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        fields.append("updatedAt = ?")
        params.extend([now, skill_id])
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE skills SET {', '.join(fields)} WHERE id = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0

    def link_task_skill(self, task_id: str, skill_id: str, relation: str = "derived") -> None:
        """Link a task to a skill."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO task_skills (taskId, skillId, relation) VALUES (?, ?, ?)",
            (task_id, skill_id, relation),
        )
        self.conn.commit()

    def log_tool_call(self, tool: str, args: str, result: str, owner: str = "local") -> None:
        """Log a tool call."""
        from datetime import datetime
        now = int(datetime.now().timestamp() * 1000)
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool TEXT NOT NULL,
                    args TEXT,
                    result TEXT,
                    owner TEXT DEFAULT 'local',
                    ts INTEGER NOT NULL
                )
            """)
            cursor.execute(
                "INSERT INTO tool_logs (tool, args, result, owner, ts) VALUES (?, ?, ?, ?, ?)",
                (tool, args[:500], result[:500], owner, now),
            )
            self.conn.commit()
        except Exception:
            pass

    def get_tool_logs(self, limit: int = 100, owner: str = "local") -> List[Dict[str, Any]]:
        """Get tool call logs."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM tool_logs WHERE owner = ? ORDER BY ts DESC LIMIT ?",
                (owner, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def scan_native_memories(self, hermes_home: str) -> Dict[str, Any]:
        """Scan ~/.openclaw/ for native memory files (SQLite + JSONL)."""
        import json
        home = Path(hermes_home).parent
        results = {"files": [], "total_sessions": 0, "total_messages": 0}
        if not home.exists():
            return results
        # Scan SQLite DBs
        for db_file in home.rglob("*.db"):
            if "memos" in str(db_file) or "node_modules" in str(db_file):
                continue
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_file))
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in c.fetchall()]
                msg_count = 0
                for table in tables:
                    try:
                        c.execute(f"PRAGMA table_info({table})")
                        cols = [r[1] for r in c.fetchall()]
                        if "content" in cols or "message" in cols:
                            c.execute(f"SELECT COUNT(*) FROM {table}")
                            msg_count += c.fetchone()[0]
                    except Exception:
                        pass
                conn.close()
                if msg_count > 0:
                    results["files"].append({"path": str(db_file), "type": "sqlite", "messages": msg_count, "sessions": 1})
                    results["total_messages"] += msg_count
                    results["total_sessions"] += 1
            except Exception:
                continue
        # Scan JSONL logs
        for jsonl_file in home.rglob("*.jsonl"):
            if "node_modules" in str(jsonl_file):
                continue
            try:
                with open(jsonl_file, "r") as f:
                    msg_count = sum(1 for line in f if line.strip())
                if msg_count > 0:
                    results["files"].append({"path": str(jsonl_file), "type": "jsonl", "messages": msg_count, "sessions": 1})
                    results["total_messages"] += msg_count
                    results["total_sessions"] += 1
            except Exception:
                continue
        return results


    def get_all_chunks(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all chunks with pagination."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chunks
            ORDER BY createdAt DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_tasks(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all tasks with pagination."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks
            ORDER BY updatedAt DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_skills(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all skills with pagination."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM skills
            ORDER BY updatedAt DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_shared_chunks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all shared chunks (all owners)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chunks
            WHERE visibility = 'shared'
            ORDER BY createdAt DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_tool_logs_all(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get tool logs from all owners."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM tool_logs ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_recent_chunks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent chunks for timeline."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chunks
            ORDER BY createdAt DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, int]:
        """Get aggregate statistics."""
        cursor = self.conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) FROM chunks")
        stats["total_chunks"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tasks")
        stats["total_tasks"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM skills")
        stats["total_skills"] = cursor.fetchone()[0]
        try:
            cursor.execute("SELECT COUNT(*) FROM tool_logs")
            stats["total_tool_logs"] = cursor.fetchone()[0]
        except Exception:
            stats["total_tool_logs"] = 0
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE visibility = 'shared'")
        stats["shared_chunks"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT sessionKey) FROM chunks")
        stats["total_sessions"] = cursor.fetchone()[0]
        return stats

    # ========== Direction A: Command History & Patterns ==========

    def log_command(
        self,
        owner: str,
        command: str,
        args: Optional[str] = None,
        project_path: Optional[str] = None,
        exit_code: Optional[int] = None,
        working_dir: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> str:
        """Log a CLI command to command_history."""
        try:
            cmd_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO command_history
                (id, owner, command, args, project_path, exit_code, working_dir, session_key, createdAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cmd_id, owner, command, args, project_path, exit_code, working_dir, session_key, now),
            )
            self.conn.commit()
            return cmd_id
        except Exception as e:
            logger.error(f"log_command failed: {e}")
            return ""

    def get_command_history(
        self,
        owner: str,
        project_path: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve command history for an owner."""
        try:
            cursor = self.conn.cursor()
            if project_path:
                cursor.execute(
                    """
                    SELECT * FROM command_history
                    WHERE owner = ? AND project_path = ?
                    ORDER BY createdAt DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner, project_path, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM command_history
                    WHERE owner = ?
                    ORDER BY createdAt DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner, limit, offset),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_command_history failed: {e}")
            return []

    def get_command_patterns(
        self,
        owner: str,
        project_path: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get command usage patterns for an owner."""
        try:
            cursor = self.conn.cursor()
            if project_path:
                cursor.execute(
                    """
                    SELECT * FROM command_patterns
                    WHERE owner = ? AND project_path = ?
                    ORDER BY frequency DESC, last_used_at DESC
                    LIMIT ?
                    """,
                    (owner, project_path, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM command_patterns
                    WHERE owner = ?
                    ORDER BY frequency DESC, last_used_at DESC
                    LIMIT ?
                    """,
                    (owner, limit),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_command_patterns failed: {e}")
            return []

    def update_command_pattern(
        self,
        owner: str,
        command: str,
        project_path: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        """Upsert a command pattern (increment frequency)."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            # Try to get existing pattern
            cursor.execute(
                """
                SELECT id, frequency, success_rate, avg_exit_code FROM command_patterns
                WHERE owner = ? AND command = ? AND (project_path = ? OR (project_path IS NULL AND ? IS NULL))
                """,
                (owner, command, project_path, project_path),
            )
            row = cursor.fetchone()
            if row:
                pat_id = row[0]
                freq = row[1] + 1
                old_sr = row[2] or 1.0
                old_avg = row[3] or 0.0
                # Update success rate
                success = 1.0 if (exit_code is None or exit_code == 0) else 0.0
                new_sr = (old_sr * (freq - 1) + success) / freq
                new_avg = (old_avg * (freq - 1) + (exit_code or 0)) / freq
                cursor.execute(
                    """
                    UPDATE command_patterns
                    SET frequency = ?, last_used_at = ?, success_rate = ?, avg_exit_code = ?, updatedAt = ?
                    WHERE id = ?
                    """,
                    (freq, now, new_sr, new_avg, now, pat_id),
                )
            else:
                pat_id = str(uuid.uuid4())
                sr = 1.0 if (exit_code is None or exit_code == 0) else 0.0
                cursor.execute(
                    """
                    INSERT INTO command_patterns
                    (id, owner, command, project_path, frequency, last_used_at, success_rate, avg_exit_code, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                    """,
                    (pat_id, owner, command, project_path, now, sr, float(exit_code or 0), now, now),
                )
            self.conn.commit()
        except Exception as e:
            logger.error(f"update_command_pattern failed: {e}")

    # ========== Direction B: Decisions ==========

    def insert_decision(
        self,
        owner: str,
        title: str,
        project: Optional[str] = None,
        context: Optional[str] = None,
        chosen: Optional[str] = None,
        alternatives: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> str:
        """Insert a new decision record."""
        try:
            decision_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO decisions
                (id, owner, project, title, context, chosen, alternatives, tags, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (decision_id, owner, project, title, context, chosen, alternatives, tags, now, now),
            )
            self.conn.commit()
            return decision_id
        except Exception as e:
            logger.error(f"insert_decision failed: {e}")
            return ""

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a decision by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_decision failed: {e}")
            return None

    def search_decisions(
        self,
        owner: str,
        query: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search decisions by title/context keywords."""
        try:
            cursor = self.conn.cursor()
            conditions = ["owner = ?"]
            params: List[Any] = [owner]
            if query:
                conditions.append("(title LIKE ? OR context LIKE ? OR chosen LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
            if project:
                conditions.append("project = ?")
                params.append(project)
            where = " AND ".join(conditions)
            cursor.execute(
                f"SELECT * FROM decisions WHERE {where} ORDER BY createdAt DESC LIMIT ?",
                params + [limit],
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"search_decisions failed: {e}")
            return []

    def update_decision(
        self,
        decision_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Update fields on a decision."""
        try:
            now = int(time.time() * 1000)
            allowed = {"title", "context", "chosen", "alternatives", "outcome", "status", "tags"}
            fields: List[str] = []
            params: List[Any] = []
            for k, v in updates.items():
                if k in allowed:
                    fields.append(f"{k} = ?")
                    params.append(v)
            if not fields:
                return False
            fields.append("updatedAt = ?")
            params.append(now)
            params.append(decision_id)
            cursor = self.conn.cursor()
            cursor.execute(f"UPDATE decisions SET {', '.join(fields)} WHERE id = ?", params)
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"update_decision failed: {e}")
            return False

    def get_decisions_by_project(
        self,
        owner: str,
        project: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all decisions for a specific project."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM decisions
                WHERE owner = ? AND project = ?
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (owner, project, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_decisions_by_project failed: {e}")
            return []

    # ========== Direction C: User Preferences ==========

    def upsert_preference(
        self,
        owner: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "explicit",
    ) -> str:
        """Insert or replace a user preference."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            # Check existing
            cursor.execute(
                "SELECT id FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
                (owner, category, key),
            )
            row = cursor.fetchone()
            if row:
                pref_id = row[0]
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET value = ?, confidence = ?, source = ?, updatedAt = ?
                    WHERE id = ?
                    """,
                    (value, confidence, source, now, pref_id),
                )
            else:
                pref_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO user_preferences
                    (id, owner, category, key, value, confidence, source, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pref_id, owner, category, key, value, confidence, source, now, now),
                )
            self.conn.commit()
            return pref_id
        except Exception as e:
            logger.error(f"upsert_preference failed: {e}")
            return ""

    def get_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific preference."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
                (owner, category, key),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_preference failed: {e}")
            return None

    def list_preferences(
        self,
        owner: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List preferences for an owner, optionally filtered by category."""
        try:
            cursor = self.conn.cursor()
            if category:
                cursor.execute(
                    "SELECT * FROM user_preferences WHERE owner = ? AND category = ? ORDER BY updatedAt DESC",
                    (owner, category),
                )
            else:
                cursor.execute(
                    "SELECT * FROM user_preferences WHERE owner = ? ORDER BY category, key",
                    (owner,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"list_preferences failed: {e}")
            return []

    def delete_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> bool:
        """Delete a specific preference."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
                (owner, category, key),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"delete_preference failed: {e}")
            return False

    def decay_preference_confidence(
        self,
        owner: str,
        decay_factor: float = 0.95,
    ) -> int:
        """Decay confidence of all preferences for an owner. Returns count of affected rows."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE user_preferences
                SET confidence = confidence * ?, updatedAt = ?
                WHERE owner = ? AND confidence > 0.01
                """,
                (decay_factor, now, owner),
            )
            self.conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"decay_preference_confidence failed: {e}")
            return 0

    def insert_behavior_pattern(
        self,
        owner: str,
        pattern_type: str,
        description: Optional[str] = None,
        data: Optional[str] = None,
        frequency: int = 1,
        confidence: float = 1.0,
    ) -> str:
        """Insert a behavior pattern."""
        try:
            pat_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO behavior_patterns
                (id, owner, pattern_type, description, data, frequency, confidence, last_seen_at, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pat_id, owner, pattern_type, description, data, frequency, confidence, now, now, now),
            )
            self.conn.commit()
            return pat_id
        except Exception as e:
            logger.error(f"insert_behavior_pattern failed: {e}")
            return ""

    def get_behavior_patterns(
        self,
        owner: str,
        pattern_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get behavior patterns for an owner."""
        try:
            cursor = self.conn.cursor()
            if pattern_type:
                cursor.execute(
                    "SELECT * FROM behavior_patterns WHERE owner = ? AND pattern_type = ? ORDER BY frequency DESC",
                    (owner, pattern_type),
                )
            else:
                cursor.execute(
                    "SELECT * FROM behavior_patterns WHERE owner = ? ORDER BY frequency DESC",
                    (owner,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_behavior_patterns failed: {e}")
            return []

    # ========== Direction D: Knowledge Health ==========

    def upsert_knowledge_health(
        self,
        owner: str,
        topic: str,
        source: Optional[str] = None,
        freshness_score: float = 1.0,
        accuracy_score: float = 1.0,
        completeness_score: float = 1.0,
        metadata: Optional[str] = None,
    ) -> str:
        """Insert or update a knowledge health record."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id FROM knowledge_health WHERE owner = ? AND topic = ?",
                (owner, topic),
            )
            row = cursor.fetchone()
            if row:
                kh_id = row[0]
                cursor.execute(
                    """
                    UPDATE knowledge_health
                    SET source = ?, freshness_score = ?, accuracy_score = ?, completeness_score = ?,
                        last_verified_at = ?, metadata = ?, updatedAt = ?
                    WHERE id = ?
                    """,
                    (source, freshness_score, accuracy_score, completeness_score, now, metadata, now, kh_id),
                )
            else:
                kh_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO knowledge_health
                    (id, owner, topic, source, freshness_score, accuracy_score, completeness_score,
                     last_verified_at, metadata, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (kh_id, owner, topic, source, freshness_score, accuracy_score, completeness_score,
                     now, metadata, now, now),
                )
            self.conn.commit()
            return kh_id
        except Exception as e:
            logger.error(f"upsert_knowledge_health failed: {e}")
            return ""

    def get_knowledge_health(
        self,
        owner: str,
        topic: str,
    ) -> Optional[Dict[str, Any]]:
        """Get knowledge health for a specific topic."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM knowledge_health WHERE owner = ? AND topic = ?",
                (owner, topic),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_knowledge_health failed: {e}")
            return None

    def list_knowledge_health(
        self,
        owner: str,
        min_freshness: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """List knowledge health records for an owner."""
        try:
            cursor = self.conn.cursor()
            if min_freshness is not None:
                cursor.execute(
                    "SELECT * FROM knowledge_health WHERE owner = ? AND freshness_score >= ? ORDER BY topic",
                    (owner, min_freshness),
                )
            else:
                cursor.execute(
                    "SELECT * FROM knowledge_health WHERE owner = ? ORDER BY topic",
                    (owner,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"list_knowledge_health failed: {e}")
            return []

    def update_freshness(
        self,
        owner: str,
        topic: str,
        freshness_score: float,
    ) -> bool:
        """Update the freshness score of a knowledge health record."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE knowledge_health
                SET freshness_score = ?, last_verified_at = ?, updatedAt = ?
                WHERE owner = ? AND topic = ?
                """,
                (freshness_score, now, now, owner, topic),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"update_freshness failed: {e}")
            return False

    # ========== Direction D: Team Knowledge Map ==========

    def upsert_team_knowledge_map(
        self,
        owner: str,
        topic: str,
        expert: Optional[str] = None,
        resource_url: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> str:
        """Insert or update a team knowledge map entry."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id FROM team_knowledge_map WHERE owner = ? AND topic = ?",
                (owner, topic),
            )
            row = cursor.fetchone()
            if row:
                tkm_id = row[0]
                cursor.execute(
                    """
                    UPDATE team_knowledge_map
                    SET expert = ?, resource_url = ?, description = ?, tags = ?, updatedAt = ?
                    WHERE id = ?
                    """,
                    (expert, resource_url, description, tags, now, tkm_id),
                )
            else:
                tkm_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO team_knowledge_map
                    (id, owner, topic, expert, resource_url, description, tags, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tkm_id, owner, topic, expert, resource_url, description, tags, now, now),
                )
            self.conn.commit()
            return tkm_id
        except Exception as e:
            logger.error(f"upsert_team_knowledge_map failed: {e}")
            return ""

    def get_team_knowledge_map(
        self,
        owner: str,
        topic: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get team knowledge map entries."""
        try:
            cursor = self.conn.cursor()
            if topic:
                cursor.execute(
                    "SELECT * FROM team_knowledge_map WHERE owner = ? AND topic = ?",
                    (owner, topic),
                )
                row = cursor.fetchone()
                return [dict(row)] if row else []
            else:
                cursor.execute(
                    "SELECT * FROM team_knowledge_map WHERE owner = ? ORDER BY topic",
                    (owner,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_team_knowledge_map failed: {e}")
            return []

    # ========== Direction D: Forgetting Schedule ==========

    def insert_forgetting_schedule(
        self,
        owner: str,
        chunk_id: Optional[str] = None,
        topic: Optional[str] = None,
        interval_days: float = 1.0,
        ease_factor: float = 2.5,
    ) -> str:
        """Insert a new forgetting schedule entry (SM-2 style)."""
        try:
            fs_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            next_review = now + int(interval_days * 86400 * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO forgetting_schedule
                (id, owner, chunk_id, topic, interval_days, ease_factor, repetitions,
                 next_review_at, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (fs_id, owner, chunk_id, topic, interval_days, ease_factor, next_review, now, now),
            )
            self.conn.commit()
            return fs_id
        except Exception as e:
            logger.error(f"insert_forgetting_schedule failed: {e}")
            return ""

    def get_due_reviews(
        self,
        owner: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get forgetting schedule entries due for review."""
        try:
            now = int(time.time() * 1000)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM forgetting_schedule
                WHERE owner = ? AND next_review_at <= ? AND status = 'pending'
                ORDER BY next_review_at ASC
                LIMIT ?
                """,
                (owner, now, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"get_due_reviews failed: {e}")
            return []
