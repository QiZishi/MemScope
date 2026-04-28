# Enterprise Memory Architecture Comparison

**Date:** 2026-04-28  
**Purpose:** Inform the design of an enterprise-level memory engine for the Feishu OpenClaw competition, based on Hermes Agent architecture.

---

## 1. HERMES AGENT — Memory Architecture

### 1.1 Overview

Hermes Agent (v0.11.0, Nous Research) uses a **dual-layer memory system**:
- **Built-in Memory** (always active): File-backed curated memory (`MEMORY.md` + `USER.md`)
- **External Plugin Memory** (optional, one at a time): Pluggable providers (Honcho, Mem0, SuperMemory, Hindsight, Holographic, OpenViking, ByteRover)

### 1.2 Memory Storage Format

| Component | Format | Location | Limits |
|-----------|--------|----------|--------|
| `MEMORY.md` | Plain text, §-delimited entries | `~/.hermes/memories/MEMORY.md` | 2,200 chars (hard limit) |
| `USER.md` | Plain text, §-delimited entries | `~/.hermes/memories/USER.md` | 1,375 chars (hard limit) |
| Session history | JSON files (`session_*.json`) | `~/.hermes/sessions/` | Retention: 90 days (configurable) |
| Session index | `sessions.json` | `~/.hermes/sessions/` | Maps session_key → session metadata |
| External providers | Provider-specific (vector DB, cloud API) | Provider-dependent | Provider-dependent |

**Key design decisions:**
- **Char-based limits** (not tokens) — model-independent, predictable
- **Frozen snapshot pattern** — system prompt captures memory at load time; mid-session writes update files but NOT the system prompt (preserves prefix cache)
- **§ (section sign) delimiter** — avoids splitting on newlines or other common characters
- **Atomic file writes** — temp file + `os.replace()` for crash safety
- **File locking** — `fcntl.flock()` (Unix) / `msvcrt.locking()` (Windows) for concurrent access

### 1.3 Retrieval Mechanism

| Mechanism | Description |
|-----------|-------------|
| **System prompt injection** | MEMORY.md + USER.md rendered as frozen blocks in system prompt at session start |
| **Prefetch (per-turn)** | Before each API call, `MemoryManager.prefetch_all(query)` collects context from all providers |
| **Context fencing** | Prefetched context wrapped in `<memory-context>` tags with system note: "NOT new user input" |
| **Background queue** | After each turn, `queue_prefetch_all()` pre-fetches for the NEXT turn (async optimization) |
| **Memory tool (explicit)** | Agent can call `memory(action="read")` to inspect current memory state |

**Retrieval flow per turn:**
```
1. queue_prefetch_all() from previous turn → background thread
2. prefetch_all(query) → collect cached results from all providers
3. Wrap in <memory-context> fences → inject into API messages
4. API call with full context
```

### 1.4 Update Mechanism

| Trigger | Mechanism |
|---------|-----------|
| **Tool call** | Agent calls `memory(action="add"|"replace"|"remove", target="memory"|"user", ...)` |
| **Memory flush** | Before compression/session-end: system injects flush prompt, agent makes one API call with only memory tool |
| **Sync per turn** | `MemoryManager.sync_all(user_msg, assistant_response)` — notifies all providers |
| **Delegation** | `MemoryManager.on_delegation(task, result)` — parent learns from subagent work |
| **End of session** | `MemoryManager.on_session_end(messages)` — extract insights from full conversation |

**Memory flush details:**
- Triggered when `_user_turn_count >= flush_min_turns` (default: 6)
- Uses auxiliary (cheaper) model for the flush call
- Injects: "The session is being compressed. Save anything worth remembering"
- Processes any memory tool calls, then strips flush artifacts from message list
- Called before context compression, session reset, or CLI exit

### 1.5 Forgetting Strategy

| Strategy | Description |
|----------|-------------|
| **Hard char limits** | MEMORY.md: 2,200 chars; USER.md: 1,375 chars — agent must replace/remove before adding |
| **No automatic pruning** | Agent decides what to keep/discard; no TTL or decay |
| **Compression** | Context compressor summarizes old turns; memory provider gets `on_pre_compress()` hook |
| **Session pruning** | Sessions auto-pruned after `retention_days` (default: 90) |
| **Duplicate detection** | Exact duplicate entries rejected on add |
| **Security scanning** | Injection/exfiltration patterns blocked before write |

### 1.6 CLI ↔ Messaging Platform Flow

```
CLI (local terminal)                    Gateway (Feishu/Telegram/Discord/etc.)
┌─────────────────────┐                ┌──────────────────────────────┐
│ Session JSON files  │                │ Session JSON files           │
│ (same format)       │                │ (same format, same path)     │
│                     │                │                              │
│ MEMORY.md ◄─────── same file ────► MEMORY.md                      │
│ USER.md    ◄─────── same file ────► USER.md                        │
│                     │                │                              │
│ MemoryManager       │                │ MemoryManager                │
│   ├─ BuiltinProvider│                │   ├─ BuiltinProvider         │
│   └─ ExtProvider    │                │   └─ ExtProvider (optional)  │
│                     │                │                              │
│ platform="cli"      │                │ platform="feishu"            │
│ session_id from CWD │                │ session_id from chat_id      │
│ Direct tool calls   │                │ Tool calls via gateway       │
└─────────────────────┘                └──────────────────────────────┘
              │                                    │
              └──────── shared state.db ───────────┘
                     (SQLite, profile-scoped)
```

**Key insight:** The same `MemoryManager` + `BuiltinMemoryProvider` runs in both CLI and gateway contexts. Memory files are shared. The `platform` kwarg lets providers scope behavior per channel.

---

## 2. OPENCLAW (Feishu Agent Platform) — Memory Architecture

### 2.1 Overview

OpenClaw is Feishu's agent gateway platform. From the workspace configuration at `~/.openclaw/`, it uses a **file-based memory system** similar to Claude Code / Cursor's approach — agents read and write markdown files in a workspace directory.

### 2.2 Memory Storage Format

| Component | Format | Location |
|-----------|--------|----------|
| `SOUL.md` | Markdown — agent identity/personality | `~/.openclaw/workspace/SOUL.md` |
| `USER.md` | Markdown — user profile (name, timezone, preferences) | `~/.openclaw/workspace/USER.md` |
| `MEMORY.md` | Markdown — curated long-term memories | `~/.openclaw/workspace/MEMORY.md` |
| `memory/YYYY-MM-DD.md` | Markdown — daily raw notes/logs | `~/.openclaw/workspace/memory/` |
| `AGENTS.md` | Markdown — workspace instructions | `~/.openclaw/workspace/AGENTS.md` |
| `TOOLS.md` | Markdown — local tool notes | `~/.openclaw/workspace/TOOLS.md` |
| `HEARTBEAT.md` | Markdown — periodic task checklist | `~/.openclaw/workspace/HEARTBEAT.md` |
| `BOOTSTRAP.md` | Markdown — first-run instructions (deleted after use) | `~/.openclaw/workspace/BOOTSTRAP.md` |
| `memory/heartbeat-state.json` | JSON — last check timestamps | `~/.openclaw/workspace/memory/` |

**Key differences from Hermes:**
- **No char limits** — files can grow freely
- **Daily journaling** — `memory/YYYY-MM-DD.md` for raw logs
- **Agent identity** — `SOUL.md` defines who the agent IS
- **Heartbeat-driven maintenance** — periodic review of daily files → update MEMORY.md

### 2.3 Retrieval Mechanism

| Mechanism | Description |
|-----------|-------------|
| **Session boot protocol** | Agent reads SOUL.md → USER.md → memory/today.md + memory/yesterday.md → MEMORY.md (main session only) |
| **Direct file reads** | Agent uses file tools to read any workspace file on demand |
| **Heartbeat checks** | Periodic polling triggers proactive file reads (email, calendar, etc.) |
| **No vector search** | Pure file-based; agent reads files manually or via instructions |

**Session boot sequence:**
```
1. Read SOUL.md (identity)
2. Read USER.md (who you're helping)
3. Read memory/YYYY-MM-DD.md (today + yesterday)
4. If main session: Read MEMORY.md
```

### 2.4 Update Mechanism

| Trigger | Mechanism |
|---------|-----------|
| **User instruction** | "Remember this" → write to memory/YYYY-MM-DD.md or MEMORY.md |
| **Agent initiative** | Agent decides to write lessons/corrections to files |
| **Heartbeat maintenance** | Periodic review: daily files → distill → update MEMORY.md |
| **No automated flush** | Agent must explicitly write; no automatic memory extraction |

### 2.5 Forgetting Strategy

| Strategy | Description |
|----------|-------------|
| **No explicit forgetting** | Files persist indefinitely unless manually edited |
| **Curation by agent** | Agent reviews daily files, decides what to promote to MEMORY.md |
| **No char limits** | Memory can grow without bound |
| **Security by scoping** | MEMORY.md only loaded in main sessions (not group chats) |

### 2.6 CLI ↔ Messaging Platform Flow

```
OpenClaw Gateway (Feishu)
┌──────────────────────────────┐
│ Gateway process              │
│   ├─ Session per chat_id     │
│   ├─ Compaction mode:        │
│   │   "safeguard"            │
│   ├─ DM scope:               │
│   │   "per-channel-peer"     │
│   └─ Workspace:              │
│       ~/.openclaw/workspace/ │
│                              │
│ Agent reads SOUL.md, USER.md │
│ Agent writes memory/*.md     │
│ Agent reads/writes MEMORY.md │
└──────────────────────────────┘
         │
         ▼
    Shared workspace files
    (git-tracked for versioning)
```

**Key insight:** OpenClaw treats the workspace as a git repository — memory files are version-controlled. The agent has full read/write access to all workspace files.

---

## 3. GENERIC AGENT PATTERNS (VoltAgent / Industry)

### 3.1 VoltAgent

VoltAgent (found at `~/hermes-data/skills/creative/popular-web-designs/templates/voltagent.md`) is a **design system template**, not a memory system. It's used by Hermes Agent to generate VoltAgent-styled landing pages.

**No memory architecture** — it's a UI design specification.

### 3.2 Industry Memory Patterns (for reference)

Based on the Hermes plugin ecosystem and anthropic SDK types found on the system:

| System | Storage | Retrieval | Update | Forgetting |
|--------|---------|-----------|--------|------------|
| **Hermes Builtin** | Markdown files, §-delimited | System prompt + prefetch | Tool calls + flush | Hard char limits |
| **Hermes + Honcho** | Cloud API | Semantic search | Auto-sync | Provider-managed |
| **Hermes + Mem0** | Vector DB | Embedding similarity | Auto-extract | Provider-managed |
| **Hermes + SuperMemory** | Cloud API | Semantic search | Auto-sync | Provider-managed |
| **Hermes + Holographic** | In-memory HRR vectors | Phase-encoded bind/unbundle | Bundle operation | Fixed-dim vectors (O(√n) capacity) |
| **OpenClaw** | Markdown files | Direct file reads | Manual + heartbeat | Agent-curated |
| **Anthropic Memory API** | Cloud memory stores | REST API | CRUD operations | Versioned (soft delete) |

---

## 4. COMPARATIVE ANALYSIS

### 4.1 Architecture Comparison

| Dimension | Hermes Agent | OpenClaw | Industry Best Practice |
|-----------|-------------|----------|----------------------|
| **Storage** | Markdown files + optional vector DB | Markdown files | Vector DB + structured metadata |
| **Retrieval** | System prompt + prefetch + tool | File reads + boot protocol | Semantic search + recency + importance |
| **Update** | Tool calls + flush + sync | Manual + heartbeat | Auto-extraction + manual curation |
| **Forgetting** | Hard char limits | Agent-curated | TTL + decay + importance scoring |
| **Cross-platform** | Shared files via gateway | Single gateway | Multi-tenant with isolation |
| **Security** | Injection scanning, session scoping | MEMORY.md only in main sessions | RBAC, encryption at rest |
| **Concurrency** | File locking + atomic writes | Git-based (no locking) | Database transactions |
| **Compression** | Context compressor (LLM-based) | Compaction mode "safeguard" | Summarization + extraction |

### 4.2 Strengths & Weaknesses

**Hermes Agent — Strengths:**
- Mature plugin architecture (7+ memory providers)
- Frozen snapshot pattern preserves prefix cache
- Memory flush before compression prevents information loss
- Injection/exfiltration scanning
- Cross-platform memory sharing
- File locking for concurrent access

**Hermes Agent — Weaknesses:**
- Hard char limits (2,200 / 1,375) are arbitrary and model-independent
- No semantic retrieval — relies on full-system-prompt injection
- No importance scoring or decay
- No cross-session search (relies on session_search for historical data)
- Memory flush uses auxiliary model — adds latency and cost

**OpenClaw — Strengths:**
- Simple, transparent (agent reads/writes files directly)
- Git versioning for memory history
- Heartbeat-driven maintenance
- Daily journaling pattern
- Identity file (SOUL.md) for personality persistence

**OpenClaw — Weaknesses:**
- No char limits — memory can bloat
- No semantic search — agent must read files manually
- No automated extraction from conversations
- No injection protection
- No concurrent access safety (relies on git)
- No structured metadata (timestamps, importance, source)

---

## 5. RECOMMENDATIONS FOR ENTERPRISE MEMORY ENGINE

### 5.1 Proposed Architecture

Based on the analysis, the enterprise memory engine should combine:

1. **Hermes Builtin pattern** — §-delimited markdown for human-readable, auditable memory
2. **Holographic HRR** — vector symbolic architecture for compositional memory binding
3. **OpenClaw daily journaling** — raw logs → curated long-term memory
4. **Semantic retrieval** — embedding-based search for relevant recall
5. **Importance scoring** — decay + recency + relevance for forgetting
6. **Cross-platform isolation** — per-user, per-channel memory scoping

### 5.2 Key Design Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Storage format | Dual: Markdown (human) + Vector DB (search) | Best of both worlds |
| Retrieval | Semantic search + recency + importance | Relevance > recency alone |
| Char limits | Dynamic, based on context window | Adapts to model capabilities |
| Forgetting | TTL + decay + importance scoring | Prevents bloat, preserves value |
| Update | Auto-extract + manual flush + heartbeat | Comprehensive coverage |
| Concurrency | File locking + DB transactions | Safety in multi-tenant setup |
| Security | Injection scanning + session scoping | Prevents prompt injection |
| Cross-platform | Shared vector DB + platform-scoped views | Consistent memory, isolated access |

### 5.3 Implementation Priorities

1. **Phase 1:** Extend Hermes builtin memory with importance scoring and decay
2. **Phase 2:** Add semantic retrieval via embeddings (integrate with existing HRR infrastructure)
3. **Phase 3:** Implement daily journaling + curation pipeline (OpenClaw pattern)
4. **Phase 4:** Cross-session memory search with privacy controls
5. **Phase 5:** Enterprise features (multi-tenant, audit logging, compliance)

---

## 6. FILES ANALYZED

| File | Purpose |
|------|---------|
| `/opt/hermes/agent/memory_manager.py` | MemoryManager orchestrator (414 lines) |
| `/opt/hermes/agent/memory_provider.py` | MemoryProvider abstract base class (240 lines) |
| `/opt/hermes/tools/memory_tool.py` | Built-in memory tool + MemoryStore (584 lines) |
| `/opt/hermes/agent/context_compressor.py` | Context window compression (1,299 lines) |
| `/opt/hermes/agent/context_engine.py` | Context engine abstraction (206 lines) |
| `/opt/hermes/plugins/memory/holographic/holographic.py` | HRR vector memory (203 lines) |
| `/opt/hermes/run_agent.py` | flush_memories() implementation (12,880 lines) |
| `/root/hermes-data/config.yaml` | Hermes configuration (388 lines) |
| `/root/hermes-data/memories/MEMORY.md` | Current memory content |
| `/root/hermes-data/memories/USER.md` | Current user profile |
| `/root/.openclaw/openclaw.json` | OpenClaw gateway config |
| `/root/.openclaw/workspace/AGENTS.md` | OpenClaw workspace instructions |
| `/root/.openclaw/workspace/USER.md` | OpenClaw user profile |
| `/opt/hermes/plugins/memory/` | 7 memory provider plugins |

---

*Document generated by Hermes Agent memory architecture analysis.*
