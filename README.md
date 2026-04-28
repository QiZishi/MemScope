<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-135%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/test--cases-200-blueviolet.svg" alt="Test Cases">
  <img src="https://img.shields.io/badge/ablation-94.5%25-success.svg" alt="Ablation Score">
</p>

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。

### 四大记忆能力

| 能力模块 | 核心功能 | 子模块 |
|----------|---------|--------|
| **command_memory** CLI命令记忆 | 高频命令统计、项目路径关联、子命令分析、上下文感知推荐 | command_tracker, pattern_analyzer, recommender |
| **decision_memory** 飞书决策记忆 | 中英文决策提取、理由/否决方案识别、历史决策卡片推送 | decision_extractor, decision_card |
| **preference_memory** 个人偏好记忆 | 偏好提取(显式+隐式)、行为模式推断、偏好生命周期管理、冲突解决 | preference_extractor, preference_manager, habit_inference |
| **knowledge_health** 团队知识健康 | 艾宾浩斯遗忘曲线(8种类型)、10领域覆盖分析、单点故障识别、遗忘预警 | ebbinghaus, freshness_monitor, gap_detector, knowledge_evaluator |

---

## Repository Structure

```
MemScope/
├── plugin.yaml                          # Hermes Agent 插件配置 (14 tools)
│
├── src/                                 # 核心源码
│   ├── __init__.py                      # MemScopeProvider 主入口
│   │
│   ├── core/                            # 核心存储层 (from memos)
│   │   ├── store.py                     # SQLite 存储 (9张表, 40+方法)
│   │   └── embedder.py                  # Embedding 封装
│   │
│   ├── recall/                          # 混合检索引擎 (from memos)
│   │   ├── engine.py                    # 三路混合检索 (FTS5+向量+Pattern)
│   │   ├── rrf.py                       # RRF 融合算法
│   │   ├── mmr.py                       # MMR 多样性重排
│   │   └── recency.py                   # 时间衰减评分
│   │
│   ├── ingest/                          # 摄取管线 (from memos)
│   │   ├── chunker.py                   # 对话分块器
│   │   ├── dedup.py                     # 去重引擎
│   │   ├── summarizer.py                # LLM 摘要生成
│   │   └── task_processor.py            # 任务边界检测
│   │
│   ├── shared/                          # 共享工具 (from memos)
│   │   └── llm_call.py                  # LLM 3层降级调用器
│   │
│   ├── skill/                           # 技能系统 (from memos)
│   │   ├── generator.py                 # 技能生成
│   │   ├── evaluator.py                 # 技能评估
│   │   ├── evolver.py                   # 技能进化
│   │   └── installer.py                 # 技能部署
│   │
│   ├── context_engine/                  # 上下文注入 (from memos)
│   │   └── index.py
│   │
│   ├── viewer/                          # Web 查看器 (from memos)
│   │   └── server.py
│   │
│   ├── command_memory/                  # 🔹 CLI 命令记忆
│   │   ├── command_tracker.py           # 命令记录与跟踪
│   │   ├── pattern_analyzer.py          # 命令模式分析
│   │   └── recommender.py              # 上下文感知推荐
│   │
│   ├── decision_memory/                 # 🔹 飞书决策记忆
│   │   ├── decision_extractor.py        # 决策信息提取 (中英文)
│   │   └── decision_card.py            # 历史决策卡片推送
│   │
│   ├── preference_memory/               # 🔹 个人偏好记忆
│   │   ├── preference_extractor.py      # 偏好提取 (显式+隐式)
│   │   ├── preference_manager.py        # 偏好生命周期管理
│   │   └── habit_inference.py           # 习惯推断引擎
│   │
│   └── knowledge_health/                # 🔹 团队知识健康
│       ├── ebbinghaus.py                # 艾宾浩斯遗忘曲线模型
│       ├── freshness_monitor.py         # 知识新鲜度监控
│       ├── gap_detector.py             # 知识缺口检测
│       └── knowledge_evaluator.py       # 知识重要性评估
│
├── tests/test_memscope.py               # 96 个单元测试
│
├── eval/                                # 评估框架
│   ├── datasets/                        # 200 条结构化测试用例
│   │   ├── command_memory.json          # 30 条 — CLI命令记忆
│   │   ├── decision_memory.json         # 30 条 — 飞书决策记忆
│   │   ├── preference_memory.json       # 30 条 — 个人偏好记忆
│   │   ├── knowledge_health.json        # 30 条 — 团队知识健康
│   │   ├── long_term_memory.json        # 20 条 — 长时序记忆 (3个月跨度)
│   │   ├── anti_interference.json       # 20 条 — 抗干扰能力
│   │   ├── contradiction_update.json    # 20 条 — 矛盾信息更新
│   │   └── efficiency.json              # 20 条 — 效率指标
│   ├── test_command_memory.py
│   ├── test_decision_memory.py
│   ├── test_preference_memory.py
│   ├── test_knowledge_health.py
│   ├── test_anti_interference.py
│   ├── test_contradiction_update.py
│   ├── test_efficiency.py
│   ├── test_feishu_integration.py
│   ├── run_ablation.py                  # 消融对比评测
│   ├── feishu_real_eval.py              # 飞书真实环境评测
│   └── ablation_results.json
│
├── demo/                                # 演示脚本
└── docs/                                # 设计文档
    ├── architecture_design.md
    ├── bad_case_analysis.md
    ├── evaluation_scheme.md
    ├── memory_whitepaper.md
    └── ...
```

---

## 📊 评测结果

### 消融对比实验

| 配置 | 加权得分 | 说明 |
|------|---------|------|
| 无记忆 | 30.0% | 纯 baseline |
| 原生 Memos | 67.5% | C/D 有基础能力，A/B 完全缺失 |
| **MemScope** | **94.5%** | 全维度覆盖，+27% 提升 |

### 飞书真实环境评测: 100/100

### 测试统计

| 类别 | 数量 |
|------|------|
| 单元测试 | 96 |
| 评估测试 | 39 |
| **总测试** | **135 (全部通过)** |
| 测试用例 | **200** (8个数据集) |

```bash
python3 -m pytest tests/ eval/ -v          # 运行全部测试
python3 eval/run_ablation.py               # 消融评测
python3 eval/feishu_real_eval.py           # 飞书评测
```

---

## Plugin Tools (14)

| Tool | Module | Description |
|------|--------|-------------|
| `memory_search` | core | 语义搜索记忆 |
| `command_log` | command_memory | 记录 CLI 命令 |
| `command_recommend` | command_memory | 推荐命令 |
| `decision_record` | decision_memory | 记录项目决策 |
| `decision_search` | decision_memory | 搜索决策 |
| `decision_cards` | decision_memory | 获取决策卡片 |
| `preference_set` | preference_memory | 设置偏好 |
| `preference_get` | preference_memory | 获取偏好 |
| `preference_list` | preference_memory | 列出偏好 |
| `habit_patterns` | preference_memory | 获取习惯模式 |
| `knowledge_health` | knowledge_health | 知识健康检查 |
| `knowledge_gaps` | knowledge_health | 知识缺口检测 |
| `knowledge_alerts` | knowledge_health | 知识预警 |
| `team_knowledge_map` | knowledge_health | 团队知识地图 |

---

## License

[MIT](LICENSE) — *Built for Feishu OpenClaw Competition — 2025*
