<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-104%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/test--cases-140-blueviolet.svg" alt="Test Cases">
  <img src="https://img.shields.io/badge/code-7,800%20lines-orange.svg" alt="Code Lines">
</p>

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。

### 四大记忆方向

| 方向 | 名称 | 核心能力 | 状态 |
|------|------|---------|------|
| **A** | CLI 命令与工作流记忆 | 高频命令统计、项目路径关联、上下文感知推荐 | ✅ |
| **B** | 飞书项目决策记忆 | 决策提取、结构化存储、历史决策卡片推送 | ✅ |
| **C** | 个人工作习惯与偏好 | LLM辅助偏好提取、行为模式推断、偏好生命周期管理 | ✅ 增强 |
| **D** | 团队知识健康与遗忘预警 | 艾宾浩斯遗忘曲线、知识缺口检测、单点故障识别 | ✅ 增强 |

### 核心技术特性

| 特性 | 描述 |
|------|------|
| **混合搜索** | FTS5 全文检索 + 向量语义搜索 + Pattern 关键词匹配 |
| **RRF 融合** | Reciprocal Rank Fusion 统一不同评分尺度 |
| **MMR 重排** | Maximal Marginal Relevance 避免结果重复 |
| **时间衰减** | 半衰期 14 天，保留 30% 基础分 |
| **艾宾浩斯遗忘曲线** | R = e^(-λt)，按知识类型调参（8种类型） |
| **偏好生命周期** | 显式声明 > 行为推断，置信度动态衰减，冲突自动解决 |
| **决策提取** | 中英文决策信号词匹配，自动提取决策-理由-否决方案 |
| **零依赖** | 纯 Python 标准库 + SQLite，即插即用 |

---

## Repository Structure

```
MemScope/
├── README.md
├── LICENSE
├── .gitignore
├── plugin.yaml                        # Hermes Agent 插件配置
│
├── src/                               # 核心源码 (~7,800 行)
│   ├── __init__.py                    # MemScopeProvider 主入口
│   ├── core/
│   │   ├── store.py                   # SQLite 存储层 (9张表, 40+方法)
│   │   └── embedder.py                # Embedding 封装
│   ├── recall/
│   │   ├── engine.py                  # 混合检索引擎
│   │   ├── rrf.py                     # RRF 融合算法
│   │   ├── mmr.py                     # MMR 重排算法
│   │   └── recency.py                 # 时间衰减评分
│   ├── ingest/
│   │   ├── chunker.py                 # 对话分块器
│   │   ├── dedup.py                   # 去重引擎
│   │   └── summarizer.py              # LLM 摘要生成
│   ├── context_engine/
│   │   └── index.py                   # 上下文注入引擎
│   ├── direction_a/                   # 方向A: CLI 命令记忆
│   │   ├── command_tracker.py         # 命令记录与模式跟踪
│   │   └── recommender.py             # 上下文感知命令推荐
│   ├── direction_b/                   # 方向B: 飞书决策记忆
│   │   ├── decision_extractor.py      # 决策信息提取 (中英文)
│   │   └── decision_card.py           # 历史决策卡片推送
│   ├── direction_c/                   # 方向C: 个人偏好记忆
│   │   ├── preference_extractor.py    # LLM辅助偏好提取
│   │   ├── preference_manager.py      # 偏好生命周期管理
│   │   └── habit_inference.py         # 习惯推断引擎
│   └── direction_d/                   # 方向D: 团队知识健康
│       ├── ebbinghaus.py              # 艾宾浩斯遗忘曲线模型
│       ├── freshness_monitor.py       # 知识新鲜度监控
│       └── gap_detector.py            # 知识缺口检测
│
├── tests/                             # 单元测试 (96 tests)
│   └── test_memscope.py
│
├── eval/                              # 评估框架
│   ├── conftest.py
│   ├── eval_runner.py
│   ├── eval_report_generator.py
│   ├── test_anti_interference.py      # 抗干扰测试
│   ├── test_contradiction_update.py   # 矛盾更新测试
│   ├── test_efficiency.py             # 效率指标测试
│   ├── test_direction_a.py            # 方向A评估
│   ├── test_direction_b.py            # 方向B评估
│   ├── test_direction_c.py            # 方向C评估
│   ├── test_direction_d.py            # 方向D评估
│   ├── test_feishu_integration.py     # 飞书集成测试
│   └── datasets/                      # 140 条结构化测试用例
│       ├── anti_interference.json     # 20 条
│       ├── contradiction_update.json  # 20 条
│       ├── efficiency.json            # 20 条
│       ├── direction_a.json           # 20 条 (CLI命令记忆)
│       ├── direction_b.json           # 20 条 (飞书决策记忆)
│       ├── direction_c.json           # 20 条 (个人偏好)
│       └── direction_d.json           # 20 条 (团队知识健康)
│
├── demo/                              # 演示脚本
│   ├── demo_cli.py
│   ├── demo_feishu.py
│   └── demo_scenario.md
│
└── docs/                              # 设计文档
    ├── architecture_design.md
    ├── evaluation_scheme.md
    ├── memory_whitepaper.md
    ├── memory_research_report.md
    ├── memos_analysis.md
    └── enterprise_memory_architecture_comparison.md
```

---

## Test Performance

### 单元测试 (96 tests)

| 测试类 | 测试数 | 状态 |
|--------|--------|------|
| TestStore | 29 | ✅ 全部通过 |
| TestDirectionA | 9 | ✅ 全部通过 |
| TestDirectionB | 11 | ✅ 全部通过 |
| TestDirectionC | 15 | ✅ 全部通过 |
| TestDirectionD | 16 | ✅ 全部通过 |
| TestMemScopeProvider | 16 | ✅ 全部通过 |

### 评估测试 (8 tests)

| 测试类 | 测试数 | 状态 |
|--------|--------|------|
| 方向A: CLI命令记忆 | 4 | ✅ 全部通过 |
| 方向B: 飞书决策记忆 | 4 | ✅ 全部通过 |

### 测试数据集 (140 cases)

| 数据集 | 用例数 | 覆盖维度 |
|--------|--------|---------|
| anti_interference | 20 | 抗干扰能力 |
| contradiction_update | 20 | 矛盾信息更新 |
| efficiency | 20 | 效率指标 |
| direction_a | 20 | CLI命令记忆 |
| direction_b | 20 | 飞书决策记忆 |
| direction_c | 20 | 个人偏好记忆 |
| direction_d | 20 | 团队知识健康 |

```bash
# 运行全部测试
python3 -m pytest tests/ eval/ -v

# 运行单元测试
python3 -m pytest tests/ -v

# 运行评估测试
python3 -m pytest eval/test_direction_a.py eval/test_direction_b.py -v
```

---

## Plugin Tools (14 tools)

| Tool | Direction | Description |
|------|-----------|-------------|
| `memory_search` | Core | 语义搜索记忆 |
| `command_log` | A | 记录 CLI 命令 |
| `command_recommend` | A | 推荐命令 |
| `decision_record` | B | 记录项目决策 |
| `decision_search` | B | 搜索决策 |
| `decision_cards` | B | 获取相关决策卡片 |
| `preference_set` | C | 设置偏好 |
| `preference_get` | C | 获取偏好 |
| `preference_list` | C | 列出偏好 |
| `habit_patterns` | C | 获取习惯模式 |
| `knowledge_health` | D | 知识健康检查 |
| `knowledge_gaps` | D | 知识缺口检测 |
| `knowledge_alerts` | D | 知识预警 |
| `team_knowledge_map` | D | 团队知识地图 |

---

## Quick Start

```bash
python3 >= 3.8
# 无额外依赖，仅使用标准库
```

```bash
# CLI 演示
python3 demo/demo_cli.py

# 飞书集成演示 (需要 FEISHU_APP_ID + FEISHU_APP_SECRET)
python3 demo/demo_feishu.py
```

---

## License

[MIT](LICENSE)

---

*Built for Feishu OpenClaw Competition — 2025*
