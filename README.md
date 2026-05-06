<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/samples-240-brightgreen.svg" alt="240 Samples">
  <img src="https://img.shields.io/badge/fact_extraction-90%25-brightgreen.svg" alt="Fact Extraction F1">
  <img src="https://img.shields.io/badge/contradiction-100%25-brightgreen.svg" alt="Contradiction Detection">
  <img src="https://img.shields.io/badge/recall@1-58.01%25-brightgreen.svg" alt="Recall@1">
</p>

---


## 功能特性

### 10 项 Memory 能力

MemScope 不是 RAG，而是完整的 Memory 系统：

| # | 能力 | 说明 | RAG 有？ |
|---|------|------|----------|
| 1 | 事实提取 | 从对话中自动提取决策/偏好/知识 | ❌ |
| 2 | 矛盾检测 | 新信息自动覆写旧信息（含跨类型） | ❌ |
| 3 | 统一召回 | 跨 chunks+决策+偏好+知识搜索 | 部分 |
| 4 | 记忆一致性 | 矛盾后只返回最新信息 | ❌ |
| 5 | 时序排序 | 后续信息优先于早期信息 | ❌ |
| 6 | 记忆整合 | 多个相关记忆合并为高层知识 | ❌ |
| 7 | 健康监控 | freshness/consistency/coverage | ❌ |
| 8 | 跨Agent共享 | Alice 的记忆可共享给 Bob | ❌ |
| 9 | 记忆遗忘 | 过时/被覆写记忆自动遗忘 | ❌ |
| 10 | 主动推荐 | 基于上下文自动推送相关记忆 | ❌ |

### 四大记忆方向（赛题）

| 方向 | 场景 | 示例 |
|------|------|------|
| **A: CLI命令记忆** | 高频命令、操作模式 | 「git push 用了47次」 |
| **B: 飞书决策记忆** | 技术选型、方案讨论 | 「前端框架选了React」 |
| **C: 个人偏好记忆** | 工具偏好、工作习惯 | 「我喜欢用Python」 |
| **D: 团队知识健康** | 知识新鲜度、遗忘预警 | 「API文档6个月无人查阅」 |

---

## 评测数据集与性能

### 评测数据集

8 个数据集，每个 30 条样本，共 240 条：

| 数据集 | 样本数 | 推理类型 | 覆盖方向 |
|--------|--------|----------|----------|
| feishu_anti_interference | 30 | single_hop, adversarial | 抗干扰测试 |
| feishu_contradiction_update | 30 | knowledge_update, temporal | 矛盾更新测试 |
| feishu_efficiency | 30 | single_hop | 效能验证 |
| feishu_command_memory | 30 | single_hop, multi_hop | 方向A: CLI命令 |
| feishu_decision_memory | 30 | single_hop, multi_hop, temporal | 方向B: 决策记忆 |
| feishu_preference_memory | 30 | single_hop, adversarial | 方向C: 偏好记忆 |
| feishu_knowledge_health | 30 | single_hop | 方向D: 知识健康 |
| feishu_long_term_memory | 30 | temporal, multi_hop | 长时序记忆 |

### 性能指标

#### Memory 能力指标（核心创新）

| 能力 | 指标 | 值 |
|------|------|-----|
| 事实提取 | Precision / Recall / F1 | **90% / 90% / 90%** |
| 矛盾检测 | Detection Rate | **100%** |
| 矛盾检测 | False Positives | **0** |
| 主动推荐 | Precision | **100%** |
| 主动推荐 | F1 | **76.9%** |

#### 检索指标（240 样本）

| 指标 | 值 |
|------|-----|
| Recall@1 | **58.01%** |
| Recall@3 | **77.84%** |
| Recall@5 | **84.99%** |
| MRR | **68.67%** |
| F1 | **50.29%** |
| 综合评分 | **67.05** |

#### 效能指标

| 指标 | 值 | 目标 |
|------|-----|------|
| 写入延迟 P50 | **1.88ms** | ≤200ms ✅ |
| 查询延迟 P50 | **1.56ms** | ≤300ms ✅ |
| 操作节省率 | **77.0%** | ≥50% ✅ |

> 详细评测报告见 [自证评测报告.md](自证评测报告.md)

---

## 目录结构

```
MemScope/
├── src/                                    # 核心源码
│   ├── __init__.py                         # MemScopeProvider 主入口
│   ├── core/
│   │   ├── store.py                        # SQLite存储层（FTS5 + LIKE + 评分）
│   │   ├── fact_extractor.py               # FactExtractor + MemoryManager
│   │   └── embedder.py                     # 向量嵌入
│   ├── recall/                             # 混合检索引擎
│   │   ├── engine.py                       # RecallEngine（FTS + Pattern + RRF）
│   │   ├── rrf.py                          # RRF 多源融合
│   │   ├── mmr.py                          # MMR 多样性重排
│   │   └── recency.py                      # 时间衰减
│   ├── command_memory/                     # 方向A: CLI命令记忆
│   │   ├── command_tracker.py              # 命令追踪
│   │   └── recommender.py                  # 命令推荐
│   ├── decision_memory/                    # 方向B: 飞书决策记忆
│   │   ├── decision_extractor.py           # 决策提取
│   │   └── decision_card.py                # 决策卡片
│   ├── preference_memory/                  # 方向C: 个人偏好记忆
│   │   ├── preference_extractor.py         # 偏好提取
│   │   ├── preference_manager.py           # 偏好管理
│   │   └── habit_inference.py              # 习惯推断
│   ├── knowledge_health/                   # 方向D: 团队知识健康
│   │   ├── ebbinghaus.py                   # 艾宾浩斯遗忘曲线
│   │   ├── freshness_monitor.py            # 新鲜度监控
│   │   └── gap_detector.py                 # 知识缺口检测
│   ├── ingest/                             # 摄取管线
│   │   ├── chunker.py                      # 语义分块
│   │   └── summarizer.py                   # 摘要生成
│   ├── context_engine/                     # 上下文自动注入
│   │   └── index.py                        # ContextEngine
│   └── shared/                             # 共享工具
│       └── utils.py                        # cosine_similarity 等
│
├── eval/                                   # 评测体系
│   ├── datasets/                           # 评测数据集（8×30=240条）
│   │   ├── feishu_anti_interference.json
│   │   ├── feishu_command_memory.json
│   │   ├── feishu_contradiction_update.json
│   │   ├── feishu_decision_memory.json
│   │   ├── feishu_efficiency.json
│   │   ├── feishu_knowledge_health.json
│   │   ├── feishu_long_term_memory.json
│   │   └── feishu_preference_memory.json
│   ├── direct_api_eval.py                  # 检索评测（240样本）
│   ├── memory_performance_eval.py          # Memory能力性能评测
│   ├── memory_lifecycle_eval_v2.py         # 生命周期评测
│   ├── e2e_integration_test.py             # 端到端集成测试
│   ├── efficiency_eval.py                  # 效能评测
│   └── history/                            # 评测历史记录
│
├── demo/                                   # 演示脚本
│   ├── demo_cli.py                         # CLI演示
│   ├── demo_feishu.py                      # 飞书演示
│   └── demo_scenario.md                    # 演示场景说明
│
├── test/                                   # 代码测试（pytest）
│   ├── conftest.py
│   ├── test_anti_interference.py
│   ├── test_command_memory.py
│   ├── test_contradiction_update.py
│   ├── test_decision_memory.py
│   ├── test_efficiency.py
│   ├── test_feishu_integration.py
│   ├── test_knowledge_health.py
│   └── test_preference_memory.py
│
├── docs/                                   # 设计文档
│   ├── architecture_design.md              # 核心架构设计
│   ├── evaluation_scheme.md                # 评测方案
│   ├── evaluation_benchmark_analysis.md    # LongMemEval/LOCOMO分析
│   ├── memos_analysis.md                   # MemOS架构分析
│   ├── memory_research_report.md           # 记忆研究综述
│   ├── enterprise_memory_architecture_comparison.md  # 架构对比
│   └── feishu_cli_integration.md           # 飞书集成方案
│
├── Memory定义与架构白皮书.md                # 记忆定义与架构白皮书
├── 自证评测报告.md                          # 自证评测报告
├── plugin.yaml                             # Hermes插件配置
├── LICENSE                                 # MIT License
└── README.md                               # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.8+
- SQLite 3.35+（支持 FTS5）

### 安装

```bash
git clone https://github.com/QiZishi/MemScope.git
cd MemScope
pip install -r requirements.txt
```

### 运行评测

```bash
# 检索评测（240 样本，Recall@k / MRR / F1）
python3 eval/direct_api_eval.py

# Memory 能力性能评测（P/R/F1 指标）
python3 eval/memory_performance_eval.py

# Memory 生命周期评测（10 项能力）
python3 eval/memory_lifecycle_eval_v2.py

# 端到端集成测试（9 阶段）
python3 eval/e2e_integration_test.py

# 效能评测（延迟 / 操作节省率）
python3 eval/efficiency_eval.py
```

### API 使用

```python
from core.store import SqliteStore
from core.fact_extractor import MemoryManager

# 初始化
store = SqliteStore("memos.db")
mm = MemoryManager(store)

# 摄入对话（自动提取事实 + 矛盾检测）
result = mm.ingest_conversation([
    {"role": "user", "content": "我们决定用React作为前端框架"},
    {"role": "user", "content": "数据库用的是PostgreSQL"},
], owner="team", session_key="meeting_001")
# result: {"chunks_stored": 2, "facts_extracted": {"decisions": 1, "knowledge": 1}, "contradictions_resolved": 0}

# 统一召回
recall = mm.recall("前端框架", owner="team")
# recall: {"chunks": [...], "decisions": [...], "preferences": [...], "knowledge": [...]}

# 主动推荐
rec = mm.proactive_recommend("我们需要优化数据库查询", owner="team")
# rec: {"recommendations": [...], "topics_detected": ["数据库", "性能"]}

# 记忆整合
mm.consolidate_memories(owner="team")

# 记忆遗忘
store.auto_forget(owner="team", force=True)
store.execute_forgetting(owner="team")
```

---

## 核心技术

### 事实提取（FactExtractor）

从非结构化对话中自动提取三类结构化事实：

| 类型 | 信号词 | 示例输入 | 提取结果 |
|------|--------|----------|----------|
| 决策 | 决定/确认/选定/切换到 | 「我们决定用React」 | decision(title="前端框架选择", chosen="React") |
| 偏好 | 喜欢/偏好/不要用 | 「我喜欢用Python」 | preference(category="language", value="Python") |
| 知识 | 用的是/部署在/版本是 | 「数据库用PostgreSQL」 | knowledge(topic="database:PostgreSQL") |

### 矛盾检测（Contradiction Detection）

新信息到达时自动检测与已有记忆的矛盾：

- **同类型**：decision "React" → 新 decision "Vue" → 旧标记 superseded
- **跨类型**：knowledge "database:MySQL" vs 新 decision "数据库选型:PostgreSQL" → 矛盾标记

### 记忆整合（Consolidation）

多个相关记忆合并为高层知识：

- **决策时间线**：MySQL → PostgreSQL（当前: PostgreSQL）
- **偏好画像**：language=Python, framework=React
- **知识图谱**：database:PostgreSQL, infra:AWS

### 主动推荐（Proactive Recommendation）

不需要用户搜索，基于对话上下文自动推送：

1. 提取话题：「优化数据库查询」→ topics=["数据库", "性能"]
2. 搜索记忆：匹配 decision/preference/knowledge/consolidated
3. 相关性评分：topic 匹配度 × 类型权重
4. 返回 top-N（min_relevance ≥ 0.1）

---

## 参考文献

1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.
3. Ebbinghaus, H. (1885). Memory: A Contribution to Experimental Psychology.
4. 飞书 OpenClaw 赛道 — 企业级长程协作 Memory 系统.
5. memos-local-hermes-plugin — MemScope 的基础架构.

---

## License

MIT
