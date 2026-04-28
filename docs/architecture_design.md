# MemScope 架构设计文档

## 总体架构

基于 memos-local-hermes-plugin 源码二次开发，扩展四大方向能力。

```
MemScope/
├── plugin.yaml                 # 插件声明 (hooks + tools)
├── src/
│   ├── __init__.py             # MemScopeProvider (extends MemosLocalProvider)
│   ├── core/
│   │   ├── store.py            # 扩展 SqliteStore，新增 A/B/C/D 表
│   │   ├── config.py           # 配置管理
│   │   └── embedder.py         # Embedding 封装
│   ├── recall/
│   │   ├── engine.py           # 混合检索引擎 (from memos)
│   │   ├── rrf.py              # RRF 融合
│   │   ├── mmr.py              # MMR 重排
│   │   └── recency.py          # 时间衰减
│   ├── ingest/
│   │   ├── chunker.py          # 分块器
│   │   ├── dedup.py            # 去重引擎
│   │   └── summarizer.py       # 摘要生成
│   ├── direction_a/            # CLI 命令记忆
│   │   ├── command_tracker.py  # 命令模式跟踪
│   │   └── recommender.py      # 上下文感知推荐
│   ├── direction_b/            # 飞书决策记忆
│   │   ├── decision_extractor.py # 决策信息提取
│   │   └── decision_card.py    # 历史决策卡片推送
│   ├── direction_c/            # 个人偏好记忆 (增强)
│   │   ├── preference_manager.py   # 偏好管理器
│   │   ├── habit_inference.py      # 习惯推断引擎
│   │   └── preference_extractor.py # LLM辅助偏好提取
│   ├── direction_d/            # 团队知识健康 (增强)
│   │   ├── freshness_monitor.py    # 知识新鲜度监控
│   │   ├── gap_detector.py         # 知识缺口检测
│   │   └── ebbinghaus.py           # 艾宾浩斯遗忘曲线
│   └── context_engine/
│       └── index.py            # 上下文注入引擎
├── eval/                       # 评估框架
├── demo/                       # 演示脚本
└── docs/                       # 设计文档
```

## 数据库 Schema (扩展)

### 现有表 (from memos)
- chunks, tasks, skills, embeddings, tool_logs, FTS5

### 新增表

#### Direction A: CLI 命令记忆
```sql
CREATE TABLE IF NOT EXISTS command_history (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    command TEXT NOT NULL,
    args TEXT,
    project_path TEXT,
    exit_code INTEGER,
    working_dir TEXT,
    timestamp_ms INTEGER NOT NULL,
    session_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_cmd_owner_ts ON command_history(owner, timestamp_ms DESC);
CREATE INDEX IF NOT EXISTS idx_cmd_project ON command_history(project_path);

CREATE TABLE IF NOT EXISTS command_patterns (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    pattern TEXT NOT NULL,         -- 命令模式 (如 "git commit -m")
    frequency INTEGER DEFAULT 1,
    avg_args TEXT,                 -- 常用参数组合 JSON
    project_context TEXT,          -- 关联项目路径
    last_used_ms INTEGER,
    confidence REAL DEFAULT 0.5,
    UNIQUE(owner, pattern, project_context)
);
```

#### Direction B: 飞书决策记忆
```sql
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,           -- 决策标题
    decision TEXT NOT NULL,        -- 决策结论
    rationale TEXT,                -- 决策理由
    alternatives TEXT,             -- 被否决方案 JSON
    participants TEXT,             -- 参与者 JSON
    source_message_ids TEXT,       -- 来源消息ID JSON
    source_platform TEXT DEFAULT 'feishu',
    decided_at_ms INTEGER,
    project_phase TEXT,            -- 项目阶段
    status TEXT DEFAULT 'active',  -- active/overturned/superseded
    related_decisions TEXT,        -- 关联决策ID JSON
    created_at_ms INTEGER,
    owner TEXT DEFAULT 'default'
);
CREATE INDEX IF NOT EXISTS idx_decision_project ON decisions(project_id, decided_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_decision_status ON decisions(status);

CREATE TABLE IF NOT EXISTS decision_cards (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    trigger_topic TEXT,            -- 触发话题
    push_channel TEXT,             -- 推送渠道
    pushed_at_ms INTEGER,
    acknowledged BOOLEAN DEFAULT 0,
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);
```

#### Direction C: 个人偏好 (增强)
```sql
CREATE TABLE IF NOT EXISTS user_preferences (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    category TEXT NOT NULL,        -- tool|schedule|style|workflow|communication
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'inferred', -- explicit|inferred|observed
    first_seen_ms INTEGER,
    last_seen_ms INTEGER,
    decay_rate REAL DEFAULT 0.01,
    conflict_resolution TEXT,      -- 冲突解决记录
    UNIQUE(owner, category, key)
);
CREATE INDEX IF NOT EXISTS idx_pref_owner ON user_preferences(owner, category);

CREATE TABLE IF NOT EXISTS behavior_patterns (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    pattern_type TEXT NOT NULL,    -- time_pattern|tool_frequency|topic_cluster|workflow
    pattern_data TEXT NOT NULL,    -- JSON
    confidence REAL DEFAULT 0.5,
    sample_count INTEGER DEFAULT 0,
    first_seen_ms INTEGER,
    last_seen_ms INTEGER,
    UNIQUE(owner, pattern_type, pattern_data)
);
```

#### Direction D: 团队知识健康 (增强)
```sql
CREATE TABLE IF NOT EXISTS knowledge_health (
    id TEXT PRIMARY KEY,
    chunk_id TEXT,
    team_id TEXT,
    category TEXT,                 -- api_doc|architecture|process|client|competitor
    importance_score REAL DEFAULT 0.5,
    last_accessed_ms INTEGER,
    access_count INTEGER DEFAULT 0,
    freshness_status TEXT DEFAULT 'fresh', -- fresh|aging|stale|forgotten
    freshness_score REAL DEFAULT 1.0,
    holder_count INTEGER DEFAULT 1,
    holders TEXT,                  -- JSON: who knows this
    last_verified_ms INTEGER,
    created_at_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_kh_team ON knowledge_health(team_id, freshness_status);
CREATE INDEX IF NOT EXISTS idx_kh_fresh ON knowledge_health(freshness_score);

CREATE TABLE IF NOT EXISTS team_knowledge_map (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    domain TEXT NOT NULL,          -- 10 大知识领域
    member_coverage TEXT,          -- JSON: {member: coverage_ratio}
    overall_coverage REAL DEFAULT 0.0,
    gap_areas TEXT,                -- JSON
    single_point_risk TEXT,        -- JSON: members who are single points
    last_updated_ms INTEGER,
    UNIQUE(team_id, domain)
);

CREATE TABLE IF NOT EXISTS forgetting_schedule (
    id TEXT PRIMARY KEY,
    knowledge_id TEXT NOT NULL,
    team_id TEXT,
    next_review_ms INTEGER,
    review_interval_hours REAL,
    ebbinghaus_lambda REAL,
    last_reviewed_ms INTEGER,
    review_count INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'normal', -- critical|high|normal|low
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_health(id)
);
```

## 方向 A: CLI 命令与工作流记忆

### 核心能力
1. **命令记录**: 自动记录用户的 CLI 命令、参数、工作目录、退出码
2. **模式识别**: 统计高频命令、常用参数组合、项目路径关联
3. **上下文推荐**: 基于当前项目目录和历史模式推荐命令
4. **显式+隐式**: 用户可主动教 (preference_set) + 系统自动统计

### 工具接口
- `command_log`: 记录命令执行
- `command_search`: 搜索历史命令
- `command_recommend`: 推荐命令

## 方向 B: 飞书项目决策与上下文记忆

### 核心能力
1. **决策提取**: 从飞书对话中提取决策信息 (LLM辅助)
2. **结构化存储**: 决策-理由-结论-反对意见 完整记录
3. **主动推送**: 当相关话题被提及时，推送历史决策卡片
4. **时序关联**: 决策与项目阶段、时间点关联

### 工具接口
- `decision_record`: 记录决策
- `decision_search`: 搜索决策
- `decision_cards`: 获取相关决策卡片

## 方向 C: 个人工作习惯与偏好记忆 (增强)

### 增强点
1. **LLM辅助偏好提取**: 从对话中自动提取偏好三元组
2. **多源融合**: 显式声明 + 行为推断 + 工具调用日志
3. **偏好感知检索**: 搜索时考虑用户偏好，个性化排序
4. **偏好演进追踪**: 记录偏好变化历史，支持回溯
5. **冲突自动解决**: 显式 > 隐式，新 > 旧

## 方向 D: 团队知识断层与遗忘预警 (增强)

### 增强点
1. **艾宾浩斯遗忘曲线**: 精确建模遗忘过程，按知识类型调参
2. **知识重要性评估**: 5维加权公式
3. **单点风险识别**: 关键知识仅1人掌握时告警
4. **主动复习提醒**: 基于遗忘曲线的定时推送
5. **知识版本管理**: 信息更新后自动废弃旧版本
