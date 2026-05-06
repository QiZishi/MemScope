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
    """SQLite-based storage for conversation memories.

    # TODO(God Class): This class has grown to 2000+ lines covering too many concerns.
    # Planned refactoring (Phase 2):
    #   - ChunkStore: chunk CRUD, FTS, pattern search, embeddings, vector search
    #   - TaskStore: task CRUD, task-skill linking
    #   - SkillStore: skill CRUD, skill search
    #   - CommandStore: command_history, command_patterns
    #   - DecisionStore: decisions, decision_cards
    #   - PreferenceStore: user_preferences, behavior_patterns
    #   - KnowledgeHealthStore: knowledge_health, forgetting_schedule, team_knowledge_map
    #   - SharedMemoryStore: visibility management, cross-agent sharing
    # Each sub-store would receive a sqlite3.Connection and expose domain-specific methods.
    # SqliteStore would become a facade delegating to sub-stores.
    """

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
                sessionKey TEXT,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                summary TEXT,
                owner TEXT DEFAULT 'local',
                startedAt INTEGER NOT NULL,
                endedAt INTEGER,
                updatedAt INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(sessionKey)")

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
        
        # Composite indexes for common query patterns (improvement: reduce query time)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session_role ON chunks(sessionKey, role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_visibility_role ON chunks(visibility, role)")
        
        # FTS5 virtual table for full-text search (standalone mode)
        # 使用unicode61 tokenizer支持中文
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content, summary, tokenize='unicode61'
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_owner_category ON user_preferences(owner, category)")

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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_owner_due_status ON forgetting_schedule(owner, next_review_at, status)")

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

        # Sync FTS5 index (standalone mode - insert into FTS5 table)
        try:
            content = chunk.get("content", "")
            summary = chunk.get("summary", "")
            if content:
                cursor.execute("INSERT INTO chunks_fts(rowid, content, summary) VALUES(last_insert_rowid(), ?, ?)", 
                             (content, summary or ""))
        except Exception:
            pass  # FTS5 table may not exist in all configurations

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
        min_score: float = 0.0,
        role: Optional[str] = None,
        scope: str = "private",
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search chunks with visibility scope support and CJK term splitting.
        
        Uses FTS5 for full-text search when available, falls back to LIKE search.
        """
        import re
        cursor = self.conn.cursor()

        # Split query into individual terms for better Chinese text matching
        # Use multiple strategies: Chinese segments, English words, numbers
        terms = []
        
        # Strategy 1: Extract Chinese word groups (2-3 chars for better granularity)
        # 改进：使用更细粒度的分词，提取2-3字符的中文词汇
        cjk_runs = re.findall(r'[\u4e00-\u9fff]+', query)
        for run in cjk_runs:
            # 2字符切分
            for i in range(len(run) - 1):
                terms.append(run[i:i+2])
            # 3字符切分
            for i in range(len(run) - 2):
                terms.append(run[i:i+3])
        
        # Strategy 2: Extract English words (including technical terms)
        english_words = re.findall(r'[a-zA-Z][a-zA-Z0-9_]*', query)
        terms.extend(english_words)
        
        # Strategy 3: Extract numbers
        numbers = re.findall(r'\d+', query)
        terms.extend(numbers)
        
        # Strategy 4: Extract mixed terms (e.g., "React Native", "GitHub Actions")
        # 提取英文+中文的混合词汇
        mixed_terms = re.findall(r'[a-zA-Z]+[\u4e00-\u9fff]+|[\u4e00-\u9fff]+[a-zA-Z]+', query)
        terms.extend(mixed_terms)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        terms = unique_terms
        
        # ---- Classify terms as 'distinctive' vs 'common' ----
        # Common 2-char Chinese terms that match almost everything
        COMMON_CHINESE_2CHAR = {
            '什么', '的是', '了不', '不在', '我们', '他们', '可以', '这个', '那个',
            '怎么', '如何', '哪些', '哪个', '一下', '一些', '一个', '还是', '但是',
            '而且', '因为', '所以', '如果', '已经', '需要', '能够', '应该', '比较',
            '非常', '可能', '或者', '以及', '关于', '通过', '进行', '使用', '没有',
            '所有', '其中', '之后', '之前', '开始', '现在', '时候', '问题', '情况',
            '方面', '部分', '一些', '其他', '这些', '那些', '大家', '你们', '我的',
            '他的', '她的', '它的', '们前', '端框', '架选', '选了', '确认', '决定',
            '方案', '部署', '采用', '建议', '讨论', '分析', '总结', '认为', '觉得',
            '发现', '知道', '了解', '认为', '觉得', '告诉', '希望', '需要', '想到',
            '来说', '起来', '出来', '下去', '上去', '过来', '过去', '到了', '得到',
            '做过', '做了', '做好', '看到', '看到', '听到', '找到', '问到', '学到',
        }
        COMMON_CHINESE_PREFIXES = set('的了是在有不人大中上下来和到会能要也就说对很')

        distinctive_terms = []
        common_terms = []
        for term in terms:
            is_distinctive = False
            if re.match(r'^[a-zA-Z0-9]+$', term):
                # English words and numbers are always distinctive
                is_distinctive = True
            elif len(term) >= 3:
                # 3+ char Chinese terms are generally distinctive
                is_distinctive = True
            elif len(term) == 2 and re.match(r'^[\u4e00-\u9fff]{2}$', term):
                # 2-char Chinese: check if it's a common/generic term
                if term not in COMMON_CHINESE_2CHAR and not all(c in COMMON_CHINESE_PREFIXES for c in term):
                    is_distinctive = True
            elif re.match(r'[\u4e00-\u9fff]', term) and re.search(r'[a-zA-Z0-9]', term):
                # Mixed terms are distinctive
                is_distinctive = True
            
            if is_distinctive:
                distinctive_terms.append(term)
            else:
                common_terms.append(term)

        # Keep all terms for search, but track which are distinctive
        all_search_terms = distinctive_terms + common_terms
        if not all_search_terms:
            all_search_terms = [query]
            distinctive_terms = [query]
        
        # Store classification info for scoring later
        distinctive_set = set(distinctive_terms)

        # Build visibility filter based on scope
        visibility_filter = ""
        extra_params = []

        if scope == "private":
            visibility_filter = " AND (c.visibility = 'private' OR c.visibility IS NULL)"
            if agent_id:
                visibility_filter += " AND (c.owner = ? OR c.owner IS NULL)"
                extra_params.append(agent_id)
        elif scope == "shared":
            visibility_filter = " AND c.visibility = 'shared'"
            if agent_id:
                visibility_filter += " AND (c.sharedWith IS NULL OR c.sharedWith LIKE ?)"
                extra_params.append(f"%{agent_id}%")
        elif scope == "all":
            if agent_id:
                visibility_filter = " AND (c.visibility = 'shared' OR c.owner = ? OR c.visibility IS NULL)"
                extra_params.append(agent_id)

        if role:
            visibility_filter += " AND c.role = ?"
            extra_params.append(role)

        # Try FTS5 search first
        try:
            # Build FTS5 query: if we have distinctive terms, require them AND allow common terms with OR
            if distinctive_terms:
                # Require at least one distinctive term, allow common terms freely
                # FTS5 syntax: (distinctive1 OR distinctive2) AND (common1 OR common2 OR ...)
                distinct_part = " OR ".join(distinctive_terms)
                if common_terms:
                    common_part = " OR ".join(common_terms)
                    fts_query = f"({distinct_part}) AND ({common_part})"
                else:
                    fts_query = f"({distinct_part})"
            else:
                # Fallback to OR logic when no distinctive terms
                fts_query = " OR ".join(all_search_terms)
            all_params = [fts_query] + extra_params + [max_results]
            cursor.execute(f"""
                SELECT c.*, rank FROM chunks c
                JOIN chunks_fts f ON c.rowid = f.rowid
                WHERE chunks_fts MATCH ?{visibility_filter}
                ORDER BY rank
                LIMIT ?
            """, all_params)
            
            results = []
            for row in cursor.fetchall():
                chunk = dict(row)
                content = chunk.get("content", "").lower()
                summary = (chunk.get("summary") or "").lower()
                
                # Score based on term coverage with distinctive boost
                matching_distinctive = sum(1 for t in distinctive_terms if t.lower() in content or t.lower() in summary)
                matching_common = sum(1 for t in common_terms if t.lower() in content or t.lower() in summary)
                total_matching = matching_distinctive + matching_common
                
                # Distinctive terms weighted 3x common terms
                if distinctive_terms:
                    distinctive_ratio = matching_distinctive / len(distinctive_terms)
                    score = 0.2 + 0.5 * distinctive_ratio
                    if common_terms:
                        common_ratio = matching_common / len(common_terms)
                        score += 0.3 * common_ratio
                else:
                    score = 0.1 + 0.7 * (total_matching / len(all_search_terms))
                
                # Exact match bonus
                query_lower = query.lower()
                if query_lower in content:
                    score += 0.15
                
                # Proximity boost
                matched_all_terms = [t for t in all_search_terms if t.lower() in content or t.lower() in (summary or "")]
                if len(matched_all_terms) >= 2:
                    min_distance = float('inf')
                    for i, t1 in enumerate(matched_all_terms):
                        pos1 = content.find(t1.lower())
                        if pos1 < 0:
                            pos1 = (summary or "").lower().find(t1.lower())
                        for t2 in matched_all_terms[i+1:]:
                            pos2 = content.find(t2.lower())
                            if pos2 < 0:
                                pos2 = (summary or "").lower().find(t2.lower())
                            if pos1 >= 0 and pos2 >= 0:
                                min_distance = min(min_distance, abs(pos1 - pos2))
                    if min_distance < 50:
                        score += 0.15
                    elif min_distance < 100:
                        score += 0.08
                    elif min_distance < 200:
                        score += 0.03
                
                score = min(score, 1.0)
                
                # Require at least one distinctive term match if available
                if distinctive_terms and matching_distinctive == 0:
                    continue
                
                if score >= min_score:
                    chunk["score"] = score
                    results.append(chunk)
            
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            if results:
                return results[:max_results]
        except Exception:
            pass  # FTS5 not available, fall back to LIKE search

        # Fall back to LIKE search
        # Use hybrid AND/OR logic based on term classification
        term_conditions = []
        term_params = []
        for term in all_search_terms:
            term_conditions.append("(c.content LIKE ? OR c.summary LIKE ?)")
            term_params.extend([f"%{term}%", f"%{term}%"])
        
        # If we have distinctive terms, require at least one distinctive match via AND in subquery
        if distinctive_terms:
            # Build: at least one distinctive term matches AND at least one common term matches (if any)
            distinctive_conditions = []
            distinctive_params = []
            for term in distinctive_terms:
                distinctive_conditions.append("(c.content LIKE ? OR c.summary LIKE ?)")
                distinctive_params.extend([f"%{term}%", f"%{term}%"])
            distinct_where = " OR ".join(distinctive_conditions)
            
            common_conditions = []
            common_params = []
            for term in common_terms:
                common_conditions.append("(c.content LIKE ? OR c.summary LIKE ?)")
                common_params.extend([f"%{term}%", f"%{term}%"])
            
            # Require at least one distinctive term match; common terms are bonus
            term_where = f"({distinct_where})"
            all_params = distinctive_params + extra_params + [max_results * 3]
        else:
            # No distinctive terms - fall back to OR logic
            term_where = " OR ".join(term_conditions)
            all_params = term_params + extra_params + [max_results * 3]

        # 计算相关性分数 (all_search_terms used for SQL relevance)
        relevance_conditions = []
        for term in all_search_terms:
            relevance_conditions.append(f"CASE WHEN c.content LIKE '%{term}%' THEN 1 ELSE 0 END")
        relevance_score = " + ".join(relevance_conditions)

        cursor.execute(f"""
            SELECT c.*, ({relevance_score}) as relevance_score FROM chunks c
            WHERE ({term_where}){visibility_filter}
            ORDER BY relevance_score DESC, c.createdAt DESC
            LIMIT ?
        """, all_params)

        results = []
        for row in cursor.fetchall():
            chunk = dict(row)
            content = chunk.get("content", "").lower()
            summary = (chunk.get("summary") or "").lower()
            query_lower = query.lower()
            
            # Score based on term coverage with distinctive boost
            matching_distinctive = sum(1 for t in distinctive_terms if t.lower() in content or t.lower() in summary)
            matching_common = sum(1 for t in common_terms if t.lower() in content or t.lower() in summary)
            
            # Require at least one distinctive term match when available
            if distinctive_terms and matching_distinctive == 0:
                continue
            
            # Distinctive terms weighted heavily
            if distinctive_terms:
                distinctive_ratio = matching_distinctive / len(distinctive_terms)
                score = 0.2 + 0.5 * distinctive_ratio
                if common_terms:
                    common_ratio = matching_common / len(common_terms)
                    score += 0.3 * common_ratio
            else:
                total_matching = matching_distinctive + matching_common
                score = 0.1 + 0.7 * (total_matching / len(all_search_terms))
            
            # Exact match bonus (full query phrase match)
            if query_lower in content:
                score += 0.15
            if summary and query_lower in summary:
                score += 0.05
            
            # Proximity boost: if multiple matched terms appear close together, boost score
            # This helps distinguish relevant context from scattered term matches
            matched_all_terms = [t for t in all_search_terms if t.lower() in content or t.lower() in (summary or "")]
            if len(matched_all_terms) >= 2:
                # Find minimum distance between any two matched terms
                min_distance = float('inf')
                for i, t1 in enumerate(matched_all_terms):
                    pos1 = content.find(t1.lower())
                    if pos1 < 0:
                        pos1 = (summary or "").lower().find(t1.lower())
                    for t2 in matched_all_terms[i+1:]:
                        pos2 = content.find(t2.lower())
                        if pos2 < 0:
                            pos2 = (summary or "").lower().find(t2.lower())
                        if pos1 >= 0 and pos2 >= 0:
                            min_distance = min(min_distance, abs(pos1 - pos2))
                # Boost if terms are close (within 100 chars = roughly same sentence)
                if min_distance < 50:
                    score += 0.15
                elif min_distance < 100:
                    score += 0.08
                elif min_distance < 200:
                    score += 0.03
            
            # Frequency bonus for distinctive term occurrences
            if distinctive_terms:
                keyword_count = sum(content.count(t.lower()) for t in distinctive_terms)
                if keyword_count > 1:
                    score += min(0.1, keyword_count * 0.03)
            
            score = min(score, 1.0)

            if score >= min_score:
                chunk["score"] = score
                results.append(chunk)

        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
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
            (id, sessionKey, title, status, summary, owner, startedAt, endedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            task.get("sessionKey", task.get("session_key")),
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
        """Pattern search for short terms - 优化版，改进评分算法"""
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
            content = (chunk.get("content") or "").lower()
            summary = (chunk.get("summary") or "").lower()
            
            # 改进的评分算法
            matching_terms = 0
            total_terms = len(terms)
            
            for term in terms:
                term_lower = term.lower()
                if term_lower in content or term_lower in summary:
                    matching_terms += 1
            
            # 计算term覆盖率
            term_ratio = matching_terms / total_terms if total_terms > 0 else 0
            
            # 基础分数 + term覆盖率加成
            score = 0.3 + 0.5 * term_ratio  # 0.3 base, up to 0.8 for full coverage
            
            # 如果有完全匹配的term，给予额外加分
            for term in terms:
                if term.lower() in content:
                    score += 0.1
                    break
            
            score = min(score, 1.0)
            chunk["score"] = score
            results.append(chunk)
        
        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
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
        """Vector similarity search — numpy batch computation."""
        import numpy as np
        
        # Get all embeddings for the owner
        all_embeddings = self.get_all_embeddings(agent_id)
        
        if not all_embeddings:
            return []
        
        # Build embedding matrix for batch computation
        chunk_ids = []
        valid_embeddings = []
        for item in all_embeddings:
            emb = item["embedding"]
            if emb and len(emb) == len(query_vec):
                chunk_ids.append(item["id"])
                valid_embeddings.append(emb)
        
        if not valid_embeddings:
            return []
        
        # Batch cosine similarity via matrix operations
        emb_matrix = np.array(valid_embeddings)  # (N, D)
        q = np.array(query_vec)  # (D,)
        
        # Normalize
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q_unit = q / q_norm
        
        emb_norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)  # (N, 1)
        # Avoid division by zero
        emb_norms = np.where(emb_norms == 0, 1, emb_norms)
        emb_unit = emb_matrix / emb_norms  # (N, D)
        
        similarities = emb_unit @ q_unit  # (N,)
        
        # Filter and sort
        mask = similarities > 0.3
        indices = np.where(mask)[0]
        # Sort by similarity descending
        sorted_indices = indices[np.argsort(similarities[indices])[::-1]]
        
        results = []
        for idx in sorted_indices[:limit]:
            results.append({
                "id": chunk_ids[idx],
                "score": float(similarities[idx]),
            })
        
        return results
    
    # ========== Task Management (Enhanced) ==========
    
    def create_task(self, task: Dict[str, Any]) -> str:
        """Create a new task."""
        from datetime import datetime
        
        now = int(datetime.now().timestamp() * 1000)
        task_id = task.get("id")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tasks
            (id, sessionKey, title, status, summary, owner, startedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            task.get("sessionKey", task.get("session_key")),
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
            SET title = ?, status = ?, summary = ?, owner = ?, updatedAt = ?,
                sessionKey = COALESCE(?, sessionKey)
            WHERE id = ?
        """, (
            task.get("title", task.get("goal", "")),
            task.get("status", "active"),
            task.get("summary", ""),
            task.get("owner", "local"),
            now,
            task.get("sessionKey", task.get("session_key")),
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
