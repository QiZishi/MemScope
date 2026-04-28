<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-25%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/test--cases-100-blueviolet.svg" alt="Test Cases">
</p>

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，作为 Hermes Agent 的插件运行。它在通用对话记忆的基础上，扩展了两大核心能力：

- **方向 C — 个人工作习惯 / 偏好记忆**：自动推断用户工作习惯，管理偏好生命周期
- **方向 D — 团队知识健康 / 遗忘预警**：监控团队知识覆盖，检测缺口并主动预警

核心创新：**将记忆从被动的「信息存储」升级为主动的「认知增强」**——Agent 不仅记住用户说过什么，还能理解工作习惯、预测需求、守护团队知识资产。

### 核心技术特性

| 特性 | 描述 |
|------|------|
| **混合搜索** | RRF (Reciprocal Rank Fusion) + MMR (Maximal Marginal Relevance) + 时间衰减加权 |
| **偏好生命周期** | 显式声明 > 行为推断，置信度动态衰减，冲突自动解决 |
| **习惯推断引擎** | 时间模式、工具频率、主题聚类、工作流序列挖掘 |
| **知识健康监控** | 新鲜 → 老化 → 过期 → 被遗忘 四阶段生命周期 |
| **团队覆盖分析** | 10 大知识领域自动检测 + 单点故障识别 |
| **零依赖部署** | 纯 Python 标准库实现，SQLite 存储，即插即用 |

---

## Repository Structure

```
MemScope/
├── README.md                          # 项目说明
├── LICENSE                            # MIT License
├── .gitignore
├── plugin.yaml                        # Hermes Agent 插件配置
├── __init__.py                        # 插件入口
│
├── alert/                             # 方向 D — 知识健康监控
│   ├── __init__.py
│   ├── freshness_monitor.py           # 知识新鲜度监控（四阶段生命周期）
│   └── gap_detector.py                # 团队知识缺口检测（10 大领域覆盖分析）
│
├── preference/                        # 方向 C — 个人偏好记忆
│   ├── __init__.py
│   ├── preference_manager.py          # 偏好 CRUD + 冲突解决 + 置信度衰减
│   └── habit_inference.py             # 行为模式推断（时间/工具/主题/工作流）
│
├── storage/                           # 存储层
│   └── schema_v2.py                   # SQLite Schema v2（4 张新表 + 全量 CRUD）
│
├── eval/                              # 评估框架
│   ├── conftest.py                    # pytest fixtures
│   ├── eval_runner.py                 # 评估运行器（5 维度加权评分）
│   ├── eval_report_generator.py       # HTML/Markdown 报告生成
│   ├── test_anti_interference.py      # 抗干扰测试（5 测试类）
│   ├── test_contradiction_update.py   # 矛盾信息更新测试（5 测试类）
│   ├── test_efficiency.py             # 效率指标测试（6 测试类）
│   ├── test_direction_c.py            # 方向 C 测试（4 测试类）
│   ├── test_direction_d.py            # 方向 D 测试（5 测试类）
│   ├── test_feishu_integration.py     # 飞书集成端到端测试（6 测试类）
│   └── datasets/                      # 100 条结构化测试用例
│       ├── anti_interference.json     # 20 条 — 噪声环境下的召回精度
│       ├── contradiction_update.json  # 20 条 — 矛盾信息更新正确性
│       ├── efficiency.json            # 20 条 — 延迟/内存/Token/并发
│       ├── direction_c.json           # 20 条 — 偏好记忆准确率
│       └── direction_d.json           # 20 条 — 知识缺口检测率
│
├── demo/                              # 演示脚本
│   ├── demo_cli.py                    # CLI 全功能演示
│   ├── demo_feishu.py                 # 飞书 API 集成演示
│   └── demo_scenario.md               # 详细场景演练文档
│
└── docs/                              # 设计文档
    ├── evaluation_scheme.md           # 评估方案（5 维度 + 评分标准）
    ├── memory_whitepaper.md           # 记忆定义与架构白皮书
    └── enterprise_memory_architecture_comparison.md  # 架构对比分析
```

---

## Core Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Hermes Agent                          │
│  on_session_start │ pre_llm_call │ post_llm_call │ ...  │
└──────┬───────────────┬───────────────┬──────────────────┘
       │               │               │
       ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│              MemScope Plugin (plugin.yaml)                │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  preference/  │  │    alert/    │  │   storage/    │  │
│  │              │  │              │  │               │  │
│  │ • preference  │  │ • freshness  │  │ • schema_v2   │  │
│  │   _manager   │  │   _monitor   │  │ • SQLite      │  │
│  │ • habit      │  │ • gap        │  │ • 4 tables    │  │
│  │   _inference │  │   _detector  │  │               │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Database Schema (v2)

| Table | Purpose | Direction |
|-------|---------|-----------|
| `user_preferences` | 用户偏好存储（显式声明 + 行为推断） | C |
| `behavior_patterns` | 行为模式记录（时间/工具/主题/工作流） | C |
| `knowledge_health` | 知识新鲜度追踪（四阶段生命周期） | D |
| `team_knowledge_map` | 团队领域覆盖分析（10 大领域） | D |

### Evaluation Framework

评估采用 **5 维度加权评分** 体系，满分 100 分：

| 维度 | 权重 | 子维度 |
|------|------|--------|
| 抗干扰能力 | 25% | 召回率、精确率、噪声注入率、F1 |
| 矛盾更新能力 | 25% | 最新值准确率、历史保留、时序排序、部分更新保真度 |
| 效率指标 | 20% | 写入延迟、查询延迟、内存占用、Token 效率、并发能力 |
| 方向 C — 个人偏好 | 15% | 偏好召回率、更新准确性、历史可追溯、上下文感知、偏好区分 |
| 方向 D — 团队知识 | 15% | 缺口检测率、告警及时性、冲突识别、覆盖准确率、安全合规 |

---

## Test Performance

> 以下数据基于 25 个 pytest 测试类、100 条结构化测试用例的实际执行结果。

| 测试维度 | 测试类数 | 用例数 | 状态 |
|----------|---------|--------|------|
| 抗干扰 (Anti-Interference) | 5 | 20 | ✅ 全部通过 |
| 矛盾更新 (Contradiction Update) | 5 | 20 | ✅ 全部通过 |
| 效率指标 (Efficiency) | 6 | 20 | ✅ 全部通过 |
| 方向 C — 个人偏好 | 4 | 20 | ✅ 全部通过 |
| 方向 D — 团队知识 | 5 | 20 | ✅ 全部通过 |
| **合计** | **25** | **100** | **✅ 25/25 通过** |

```bash
# 运行全部测试
cd eval/ && python3 -m pytest -v

# 运行单维度测试
python3 -m pytest test_anti_interference.py -v
python3 -m pytest test_direction_c.py -v
python3 -m pytest test_efficiency.py -v

# 生成评估报告
python3 eval_runner.py --output eval_results.json --verbose
```

---

## Quick Start

### Prerequisites

```bash
python3 >= 3.8
# 无额外依赖，仅使用标准库 (sqlite3, json, time, uuid 等)
```

### Run CLI Demo

```bash
cd demo/
python3 demo_cli.py
```

演示流程：
1. 初始化 SQLite 数据库和 Schema v2
2. 设置用户偏好 → `preference_set`
3. 查询偏好 → `preference_get` / `preference_list`
4. 习惯推断 → `habit_patterns`
5. 知识健康检查 → `knowledge_health`
6. 团队知识缺口 → `knowledge_gaps` / `knowledge_alerts`
7. 知识地图 → `team_knowledge_map`
8. 新鲜度监控 → `knowledge_freshness`

### Run Feishu Integration Demo

```bash
python3 demo/demo_feishu.py
```

> 需要配置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 环境变量。未配置时以模拟模式运行。

---

## Plugin Tools

MemScope 为 Hermes Agent 注册以下工具：

| Tool | Description | Direction |
|------|-------------|-----------|
| `preference_set` | 设置用户偏好 | C |
| `preference_get` | 查询单个偏好 | C |
| `preference_list` | 列出所有偏好 | C |
| `habit_patterns` | 习惯推断分析 | C |
| `knowledge_health` | 知识健康状态检查 | D |
| `knowledge_gaps` | 团队知识缺口检测 | D |
| `knowledge_alerts` | 知识预警推送 | D |
| `team_knowledge_map` | 团队知识地图 | D |
| `knowledge_freshness` | 新鲜度监控 | D |

---

## License

[MIT](LICENSE)

---

*Built for Feishu OpenClaw Competition — 2025*
