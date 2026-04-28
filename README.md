<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-135%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/test--cases-140-blueviolet.svg" alt="Test Cases">
  <img src="https://img.shields.io/badge/code-7,800%20lines-orange.svg" alt="Code Lines">
  <img src="https://img.shields.io/badge/ablation-94.5%25-success.svg" alt="Ablation Score">
</p>

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。

### 四大记忆方向

| 方向 | 名称 | 核心能力 | 状态 |
|------|------|---------|------|
| **A** | CLI 命令与工作流记忆 | 高频命令统计、项目路径关联、上下文感知推荐、子命令分析 | ✅ |
| **B** | 飞书项目决策记忆 | 中英文决策提取、理由/否决方案识别、历史决策卡片推送 | ✅ |
| **C** | 个人工作习惯与偏好 | LLM辅助偏好提取、行为模式推断、偏好生命周期管理、冲突解决 | ✅ 增强 |
| **D** | 团队知识健康与遗忘预警 | 艾宾浩斯遗忘曲线(8种类型)、10领域覆盖分析、单点故障识别 | ✅ 增强 |

### 核心技术特性

| 特性 | 描述 |
|------|------|
| **混合搜索** | FTS5 全文检索 + 向量语义搜索 + Pattern 关键词匹配 |
| **RRF 融合** | Reciprocal Rank Fusion 统一不同评分尺度 |
| **MMR 重排** | Maximal Marginal Relevance 避免结果重复 |
| **时间衰减** | 半衰期 14 天，保留 30% 基础分 |
| **艾宾浩斯遗忘曲线** | R = e^(-λt)，按 8 种知识类型独立调参 |
| **偏好生命周期** | 显式声明 > 行为推断，置信度动态衰减，冲突自动解决 |
| **决策提取** | 中英文决策信号词匹配，自动提取决策-理由-否决方案 |
| **零依赖** | 纯 Python 标准库 + SQLite，即插即用 |

---

## 📊 评测结果

### 消融对比实验 (Ablation Study)

| 维度 | 无记忆 | 原生 Memos | **MemScope** | 提升 |
|------|--------|-----------|-------------|------|
| A: CLI 命令记忆 | 0% | 0% | **80%** | +80% (新能力) |
| B: 飞书决策记忆 | 0% | 0% | **100%** | +100% (新能力) |
| C: 个人偏好 | 0% | 100% | **100%** | 持平 |
| D: 团队知识健康 | 0% | 87.5% | **87.5%** | 持平 |
| 抗干扰 | 100% | 100% | 100% | 持平 |
| 矛盾更新 | 100% | 100% | 100% | 持平 |
| 效率 | 100% | 100% | 100% | 持平 |
| **加权总分** | **30.0%** | **67.5%** | **94.5%** | **+27.0%** |

### 飞书真实环境评测

| 方向 | 得分 | 测试项 |
|------|------|--------|
| A: CLI 命令记忆 | 100% | 高频命令识别、项目路径关联、上下文推荐 |
| B: 飞书决策记忆 | 100% | 中英文决策提取、搜索、卡片推送 |
| C: 个人偏好 | 100% | 偏好提取、存储、查询、团队统计 |
| D: 团队知识健康 | 100% | 知识注册、新鲜度监控、缺口检测、单点故障 |
| **总分** | **100/100** | |

> 详细评测报告: `eval/feishu_eval_report.md` | 消融数据: `eval/ablation_results.json`

### Bad Case 分析

| 问题 | 严重度 | 状态 |
|------|--------|------|
| 决策标题生成含前导标点 | 中 | ✅ 已修复 |
| 子命令分析仅支持 base command | 低 | ✅ 已修复 (支持 `git commit` 级别) |
| 向量搜索 O(n) 暴力扫描 | 高 | 📋 改进计划 P1 |
| 中文分词仅用 bigram | 中 | 📋 改进计划 P1 |

> 详细分析: `docs/bad_case_analysis.md`

---

## Repository Structure

```
MemScope/
├── README.md
├── LICENSE / .gitignore
├── plugin.yaml                        # Hermes Agent 插件配置 (14 tools)
│
├── src/                               # 核心源码 (~7,800 行)
│   ├── __init__.py                    # MemScopeProvider 主入口
│   ├── core/store.py + embedder.py    # 存储层 (9张表, 40+方法) + Embedding
│   ├── recall/engine + rrf + mmr + recency  # 混合检索引擎
│   ├── ingest/chunker + dedup + summarizer  # 摄取管线
│   ├── context_engine/index.py        # 上下文注入引擎
│   ├── direction_a/                   # 方向A: CLI 命令记忆
│   ├── direction_b/                   # 方向B: 飞书决策记忆
│   ├── direction_c/                   # 方向C: 个人偏好记忆
│   └── direction_d/                   # 方向D: 团队知识健康
│
├── tests/test_memscope.py             # 96 个单元测试
│
├── eval/                              # 评估框架
│   ├── datasets/ (7×20=140 cases)     # A/B/C/D + 抗干扰 + 矛盾 + 效率
│   ├── test_direction_a/b/c/d.py      # 方向评估
│   ├── test_anti/contra/eff/feishu.py # 通用评估
│   ├── run_ablation.py                # 消融对比评测
│   ├── feishu_real_eval.py            # 飞书真实环境评测
│   └── ablation_results.json          # 消融数据
│
├── demo/                              # 演示脚本
└── docs/                              # 设计文档 + Bad Case 分析
```

---

## Quick Start

```bash
python3 >= 3.8  # 无额外依赖

# 运行全部测试 (135 tests)
python3 -m pytest tests/ eval/ -v

# 运行消融评测
python3 eval/run_ablation.py

# 运行飞书真实环境评测
python3 eval/feishu_real_eval.py

# CLI 演示
python3 demo/demo_cli.py
```

---

## Plugin Tools (14 tools)

| Tool | Direction | Description |
|------|-----------|-------------|
| `memory_search` | Core | 语义搜索记忆 |
| `command_log` / `command_recommend` | A | 命令记录与推荐 |
| `decision_record` / `decision_search` / `decision_cards` | B | 决策管理 |
| `preference_set` / `preference_get` / `preference_list` / `habit_patterns` | C | 偏好管理 |
| `knowledge_health` / `knowledge_gaps` / `knowledge_alerts` / `team_knowledge_map` | D | 知识健康 |

---

## License

[MIT](LICENSE) — *Built for Feishu OpenClaw Competition — 2025*
