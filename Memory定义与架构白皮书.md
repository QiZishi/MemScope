# Memory 定义与架构白皮书

> MemScope — 企业级长周期协作记忆引擎
> 版本：v5.9 | 日期：2026-05-06

---

## 一、记忆场景定义

企业协作中存在大量**隐性知识**散落在对话、文档、决策记录中。MemScope 从四个维度切入，将这些隐性知识转化为结构化记忆。

### 1.1 CLI 高频命令记忆（方向A）

**场景**：开发者每天执行大量 CLI 命令（git、docker、kubectl、npm 等），高频操作模式蕴含个人工作习惯。

**记忆内容**：
- 高频命令统计：`git push` 用了 47 次、`docker compose up` 用了 23 次
- 项目路径关联：在 `/project-a` 下常用 `pytest`，在 `/project-b` 下常用 `go test`
- 上下文感知推荐：检测到用户在前端项目目录下，推荐 `npm run dev` 而非 `go run`

**企业价值**：减少重复输入、降低操作失误、加速新人上手。

### 1.2 飞书决策历史（方向B）

**场景**：团队在飞书群中讨论技术选型、部署方案、架构设计，结论散落在聊天记录中。

**记忆内容**：
- 技术选型决策：「我们决定用 React 作为前端框架，不用 Vue 了」→ decision(title="前端框架选择", chosen="React")
- 方案讨论沉淀：部署方案从「自建机房」→「AWS」→「阿里云」的演变历史
- 决策卡片推送：当用户讨论「前端框架」时，自动推送历史决策卡片

**企业价值**：避免重复讨论、追溯决策依据、新人快速了解项目背景。

### 1.3 个人偏好记忆（方向C）

**场景**：每个开发者有独特的工具偏好和工作习惯，这些偏好影响协作效率。

**记忆内容**：
- 工具偏好：喜欢用 VS Code、偏好 Python、习惯用 Docker 部署
- 工作习惯：习惯上午写代码下午开会、偏好异步沟通
- 偏好冲突解决：「我更喜欢用 Go，不要用 Python 了」→ 自动更新偏好

**企业价值**：个性化推荐、减少沟通摩擦、提升工作舒适度。

### 1.4 团队知识健康（方向D）

**场景**：团队知识会随时间衰减，关键知识可能因人员变动而丢失。

**记忆内容**：
- 知识新鲜度追踪：「数据库用 PostgreSQL」→ freshness=1.0（刚记录）→ 90天后 freshness=0.3
- 遗忘预警：某 API 文档 6 个月无人查阅，触发遗忘预警
- 知识缺口检测：新项目用到 Kafka，但团队无人有相关知识

**企业价值**：防止知识流失、主动发现知识缺口、保障团队知识连续性。

---

## 二、为什么企业需要协作记忆

### 2.1 信息遗忘成本

| 场景 | 遗忘成本 | MemScope 解法 |
|------|----------|---------------|
| 新员工入职 | 2-4 周熟悉项目历史 | 决策历史一键召回 |
| 团队交接 | 关键知识随人员流失 | 结构化记忆持久化 |
| 历史决策追溯 | 翻阅数月聊天记录 | 决策卡片精准推送 |
| 重复讨论 | 同一话题反复讨论 | 主动推荐历史结论 |

### 2.2 协作效率提升

传统模式：「我们之前讨论过用什么数据库来着？」→ 翻聊天记录 → 找不到 → 重新讨论

MemScope 模式：用户提问 → 系统主动推荐「数据库选型：PostgreSQL（2026-01-15 决策）」→ 直接采纳

### 2.3 知识沉淀

隐性知识（存在于少数人脑中）→ 显性记忆（结构化存储在 MemScope 中）

```
对话："我们决定用 Docker 部署"
  ↓ FactExtractor 自动提取
结构化记忆：decision(title="部署方案", chosen="Docker")
  ↓ consolidate_memories 整合
高层知识：[决策历史] 部署方案: Docker (当前: Docker)
  ↓ proactive_recommend 主动推荐
新对话："新服务怎么部署？" → 自动推荐 Docker 方案
```

---

## 三、MemScope 架构

### 3.1 整体架构

```
                    ┌─────────────────────────────────┐
                    │         MemScope Engine          │
                    ├─────────────────────────────────┤
                    │                                 │
  对话输入 ────────→│  FactExtractor (事实提取)        │
                    │      ↓                          │
                    │  Contradiction Detection (矛盾)  │
                    │      ↓                          │
                    │  SqliteStore (结构化存储)         │
                    │      ↓                          │
                    │  Memory Consolidation (整合)     │
                    │      ↓                          │
                    │  Proactive Recommend (推荐)      │
                    │      ↓                          │
                    │  Memory Forgetting (遗忘)        │
                    │      ↓                          │
  上下文注入 ←──────│  Recall Engine (统一召回)        │
                    │                                 │
                    └─────────────────────────────────┘
                              ↕
                    ┌─────────────────────────────────┐
                    │   SQLite + FTS5 全文索引          │
                    │   chunks / decisions / prefs /   │
                    │   knowledge / access_log /       │
                    │   forgetting_schedule            │
                    └─────────────────────────────────┘
```

### 3.2 数据流

```
对话消息 → 事实提取(FactExtractor)
  ├── 提取决策: "我们决定用React" → decision(title="前端框架选择", chosen="React")
  ├── 提取偏好: "我喜欢用Python" → preference(category="language", key="编程语言", value="Python")
  ├── 提取知识: "数据库用PostgreSQL" → knowledge(topic="database:PostgreSQL")
  └── 存储原文: chunk(content="我们决定用React作为前端框架")
                ↓
         矛盾检测
  ├── decision vs decision: "React" → "Vue" → 旧决策标记superseded
  ├── preference vs preference: "Python" → "Go" → 偏好自动更新
  ├── knowledge vs knowledge: "MySQL" → "PostgreSQL" → 知识更新
  └── cross-type: knowledge "MySQL" vs decision "PostgreSQL" → 矛盾标记
                ↓
         记忆整合(consolidate_memories)
  ├── 决策时间线: "前端框架选择: React → Vue (当前: Vue)"
  ├── 偏好画像: "language: Python, framework: React"
  └── 知识图谱: "database: PostgreSQL, infra: AWS"
                ↓
         主动推荐(proactive_recommend)
  ├── 分析对话话题: "优化数据库查询" → topics=["数据库", "性能"]
  ├── 搜索相关记忆: knowledge "database:PostgreSQL" 匹配
  └── 返回推荐: 推荐 PostgreSQL 相关知识（relevance=0.5）
                ↓
         记忆遗忘(auto_forget)
  ├── 被覆写决策: superseded 7天后 → forgotten
  ├── 低新鲜度知识: freshness < 0.3 → 调度遗忘
  └── 长期未访问: 90天无访问 → 调度遗忘
```

### 3.3 存储层

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `chunks` | 原文存储 | content, sessionKey, role, owner, visibility |
| `chunks_fts` | FTS5 全文索引 | content, summary (unicode61 tokenizer) |
| `decisions` | 决策记忆 | title, chosen, alternatives, status(active/superseded/forgotten) |
| `user_preferences` | 偏好记忆 | category, key, value, confidence |
| `knowledge_health` | 知识记忆 | topic, freshness_score, accuracy_score |
| `memory_access_log` | 访问日志 | memory_type, memory_id, accessed_at |
| `forgetting_schedule` | 遗忘调度 | memory_type, next_review_at, status |

---

## 四、核心技术

### 4.1 FactExtractor — 事实提取

从非结构化对话中自动提取结构化事实。

**决策提取**：识别「决定/确认/选定/采用/切换到」等信号词，提取 chosen 值。
- 输入：「我们最终决定把前端框架切换到 Vue」
- 输出：decision(title="前端框架选择", chosen="Vue")

**偏好提取**：识别「喜欢/偏好/习惯/不要用」等信号词，提取偏好值。
- 输入：「我喜欢用 Python 写代码」
- 输出：preference(category="language", key="编程语言", value="Python")

**知识提取**：识别「用的是/部署在/版本是」等信号词，提取事实。
- 输入：「数据库用的是 PostgreSQL」
- 输出：knowledge(topic="database:PostgreSQL")

### 4.2 Contradiction Detection — 矛盾检测

新信息到达时，自动检测是否与已有记忆矛盾。

**同类型矛盾**：
- decision "React" + 新 decision "Vue" → 旧标记 superseded
- preference "Python" + 新 preference "Go" → 自动更新

**跨类型矛盾**：
- knowledge "database:MySQL" + 新 decision "数据库选型: PostgreSQL" → 矛盾标记
- 决策和知识之间的不一致也能被检测到

**检测率**：100%（3/3 测试用例），误报率：0%

### 4.3 Memory Consolidation — 记忆整合

将多个相关记忆合并为更高层的知识。

**决策时间线**：MySQL → PostgreSQL（当前: PostgreSQL）
**偏好画像**：language=Python, framework=React, editor=VS Code
**知识图谱**：database:PostgreSQL, infrastructure:AWS, mq:RabbitMQ

### 4.4 Proactive Recommendation — 主动推荐

不需要用户主动搜索，基于对话上下文自动推送相关记忆。

**流程**：
1. 从消息中提取话题：「优化数据库查询」→ topics=["数据库", "性能"]
2. 搜索所有记忆类型：决策/偏好/知识/整合chunk
3. 计算相关性分数：topic 匹配度 × 类型权重
4. 返回 top-N 推荐（min_relevance ≥ 0.1）

**性能**：Precision=100%, Recall=62.5%, F1=76.9%

---

## 五、10 项 Memory 能力

| # | 能力 | 说明 | API |
|---|------|------|-----|
| 1 | 事实提取 | 从对话中自动提取决策/偏好/知识 | `FactExtractor.extract_and_store()` |
| 2 | 矛盾检测 | 新信息自动覆写旧信息（含跨类型） | `extract_and_store(detect_contradictions=True)` |
| 3 | 统一召回 | 跨 chunks+决策+偏好+知识搜索 | `MemoryManager.recall()` |
| 4 | 记忆一致性 | 矛盾后只返回最新信息 | decision.status = active/superseded/forgotten |
| 5 | 时序排序 | 后续信息优先于早期信息 | createdAt 排序 |
| 6 | 记忆整合 | 多个相关记忆合并为高层知识 | `consolidate_memories()` |
| 7 | 健康监控 | freshness/consistency/coverage | `check_memory_health()` |
| 8 | 跨Agent共享 | Alice 的记忆可共享给 Bob | `share_memory()` / `get_shared_memories()` |
| 9 | 记忆遗忘 | 过时/被覆写记忆自动遗忘 | `auto_forget()` / `execute_forgetting()` |
| 10 | 主动推荐 | 基于上下文自动推送相关记忆 | `proactive_recommend()` / `prefetch()` |

---

## 六、与 RAG 的本质区别

| 维度 | RAG | MemScope |
|------|-----|----------|
| 存储 | 原文存储 → 向量化 | 事实提取 → 结构化存储 |
| 检索 | 向量相似度搜索 | FTS5 + LIKE + 评分算法 |
| 更新 | 无（只增不改） | 矛盾检测 → 自动覆写 |
| 整合 | 无 | 多记忆合并为高层知识 |
| 遗忘 | 无 | 时效性衰减 + 主动遗忘 |
| 共享 | 无 | 跨 Agent 记忆共享 |
| 推荐 | 被动搜索 | 主动推送相关记忆 |

RAG 只做了一件事：存原文、搜原文。MemScope 做了十件事：提取、检测、存储、整合、推荐、遗忘、共享……

---

## 七、参考文献

1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.
3. Ebbinghaus, H. (1885). Memory: A Contribution to Experimental Psychology.
4. 飞书 OpenClaw 赛道 — 企业级长程协作 Memory 系统.

---

*MemScope — 让企业协作记忆永不遗忘*
