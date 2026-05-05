<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/hit--rate-50.00%25-yellow.svg" alt="Hit Rate">
  <img src="https://img.shields.io/badge/f1--score-38.78%25-yellow.svg" alt="F1 Score">
</p>

---

## 📊 最新评测结果（端到端评测）

> 评测时间：2026-05-06
> 评测方式：直接调用MemScope API测试
> 评测数据集：飞书业务场景（chunk/query/answer格式）

### 核心Memory指标

| 指标 | 值 | 说明 |
|------|-----|------|
| **命中率 Hit Rate** | **50.00%** | 搜索结果中包含目标信息的比例 |
| **精确率 Precision** | **33.89%** | 搜索结果中正确信息的比例 |
| **召回率 Recall** | **50.00%** | 目标信息被检索到的比例 |
| **F1分数** | **38.78%** | 精确率和召回率的调和平均 |
| 噪声注入率 | 16.67% | 搜索结果中噪声信息的比例 |

### 各数据集指标

| 数据集 | 命中率 | 精确率 | 召回率 | F1分数 | 用例数 |
|--------|--------|--------|--------|--------|--------|
| feishu_decision_memory | 50.00% | 28.33% | 50.00% | 35.00% | 10 |
| feishu_knowledge_health | 80.00% | 65.00% | 80.00% | 69.67% | 10 |
| feishu_preference_memory | 20.00% | 8.33% | 20.00% | 11.67% | 10 |

### 评测结果文件

每次评测会生成以下文件：
- `eval_results.json` — 完整评测结果
- `eval_report.md` — Markdown评测报告
- `metrics_summary.json` — 指标摘要

最新评测结果：`eval/history/20260506_015659/`

---

## 📋 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-05-06 | v3.1 | **评测数据集重构**：贴合飞书业务场景，每个样本包含chunk/query/answer；修复中文分词问题；命中率从3.33%提升到50.00% |
| 2026-05-06 | v3.0 | **评测体系重构**：删除虚假的本地评测，实现真正的memory指标计算（命中率/精确率/召回率/F1） |
| 2026-05-06 | v2.4 | 第1轮对抗优化：修复FTS5索引同步、UNIQUE约束冲突、中文分词 |
| 2026-05-05 | v2.3 | README重构：基于深度审查更新 |
| 2026-05-05 | v2.2 | 评测体系全面修复 + 飞书真实集成 |
| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条 |
| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块全部实现 |
| 2026-04-27 | v1.0 | 初始版本 |

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。

### 四大记忆能力

| 能力模块 | 核心功能 | 子模块 |
|----------|---------|--------|
| **command_memory** CLI命令记忆 | 高频命令统计、项目路径关联、上下文感知推荐 | command_tracker, pattern_analyzer, recommender |
| **decision_memory** 飞书决策记忆 | 中英文决策提取、历史决策卡片推送 | decision_extractor, decision_card |
| **preference_memory** 个人偏好记忆 | 偏好提取(显式+隐式)、行为模式推断、冲突解决 | preference_extractor, preference_manager, habit_inference |
| **knowledge_health** 团队知识健康 | 艾宾浩斯遗忘曲线、知识缺口检测、遗忘预警 | ebbinghaus, freshness_monitor, gap_detector, knowledge_evaluator |

---

## Repository Structure

```
MemScope/
├── plugin.yaml                          # Hermes Agent 插件配置 (14 tools)
│
├── src/                                 # 核心源码
│   ├── __init__.py                      # MemScopeProvider 主入口
│   ├── core/                            # 核心存储层
│   │   ├── store.py                     # SQLite 存储 (FTS5 + CJK 分词)
│   │   └── embedder.py                  # Embedding 封装
│   ├── recall/                          # 混合检索引擎
│   ├── ingest/                          # 摄取管线
│   ├── command_memory/                  # 🔹 方向A: CLI 命令记忆
│   ├── decision_memory/                 # 🔹 方向B: 飞书决策记忆
│   ├── preference_memory/               # 🔹 方向C: 个人偏好记忆
│   ├── knowledge_health/                # 🔹 方向D: 团队知识健康
│   └── feishu/                          # 🔹 飞书 API 集成
│
├── eval/                                # 评测
│   ├── datasets/                        # 飞书业务场景评测数据集
│   │   ├── feishu_decision_memory.json  # 决策记忆数据集
│   │   ├── feishu_knowledge_health.json # 知识健康数据集
│   │   └── feishu_preference_memory.json# 偏好记忆数据集
│   ├── e2e_feishu_eval.py               # 端到端评测脚本
│   ├── history/                         # 评测历史记录
│   └── schema_v2.py                     # 数据库schema
│
├── demo/                                # 演示脚本
├── docs/                                # 设计文档
├── AGENTS.md                            # 开发指南
├── README.md                            # 本文件
└── LICENSE                              # MIT License
```

---

## 运行方式

```bash
# 端到端评测（直接调用MemScope API测试）
python3 eval/e2e_feishu_eval.py

# CLI 演示
python3 demo/demo_cli.py

# 飞书 API 演示
python3 demo/demo_feishu.py
```

---

## 参考文献与致谢

### 学术基准

1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.

### 开源项目

3. [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) — MemScope 的基础框架
4. [Hermes Agent](https://github.com/damxin/memos-local-hermes-plugin) — AI Agent 运行时环境
5. [飞书 CLI](https://github.com/larksuite/cli) — 飞书官方 CLI 工具

### 赛题

6. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统（公开版）. [赛题链接](https://bytedance.larkoffice.com/wiki/TYewweOPuiHMtBkA1aXcldJonic)

---

## License

[MIT](LICENSE) — *Built for Feishu OpenClaw Competition — 2025*
