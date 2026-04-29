<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/eval--cases-240-blueviolet.svg" alt="Eval Cases">
  <img src="https://img.shields.io/badge/pass%20rate-67.1%25-yellow.svg" alt="Pass Rate">
</p>

---

## 📋 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条(每集30条)；新增LONGMEMEVAL/LOCOMO基准分析；长时序评测扩展至2年跨度；test/与eval/目录分离；新增评测方案v2.0 |
| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块(command/decision/preference/knowledge_health)全部实现；14个插件工具；7800+行代码 |
| 2026-04-27 | v1.0 | 初始版本：基于memos-local-hermes-plugin二次开发；基础存储层+检索引擎+摄取管线 |

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
│   ├── core/                            # 核心存储层 (from memos)
│   │   ├── store.py                     # SQLite 存储 (9张表, 40+方法)
│   │   └── embedder.py                  # Embedding 封装
│   ├── recall/                          # 混合检索引擎 (from memos)
│   │   ├── engine.py                    # 三路混合检索 (FTS5+向量+Pattern)
│   │   ├── rrf.py                       # RRF 融合算法
│   │   ├── mmr.py                       # MMR 多样性重排
│   │   └── recency.py                   # 时间衰减评分
│   ├── ingest/                          # 摄取管线 (from memos)
│   │   ├── chunker.py                   # 对话分块器
│   │   ├── dedup.py                     # 去重引擎
│   │   ├── summarizer.py                # LLM 摘要生成
│   │   └── task_processor.py            # 任务边界检测
│   ├── shared/                          # 共享工具 (from memos)
│   │   └── llm_call.py                  # LLM 3层降级调用器
│   ├── skill/                           # 技能系统 (from memos)
│   │   ├── generator.py                 # 技能生成
│   │   ├── evaluator.py                 # 技能评估
│   │   ├── evolver.py                   # 技能进化
│   │   └── installer.py                 # 技能部署
│   ├── context_engine/                  # 上下文注入 (from memos)
│   │   └── index.py
│   ├── viewer/                          # Web 查看器 (from memos)
│   │   └── server.py
│   ├── command_memory/                  # 🔹 CLI 命令记忆
│   │   ├── command_tracker.py           # 命令记录与跟踪
│   │   ├── pattern_analyzer.py          # 命令模式分析
│   │   └── recommender.py              # 上下文感知推荐
│   ├── decision_memory/                 # 🔹 飞书决策记忆
│   │   ├── decision_extractor.py        # 决策信息提取 (中英文)
│   │   └── decision_card.py            # 历史决策卡片推送
│   ├── preference_memory/               # 🔹 个人偏好记忆
│   │   ├── preference_extractor.py      # 偏好提取 (显式+隐式)
│   │   ├── preference_manager.py        # 偏好生命周期管理
│   │   └── habit_inference.py           # 习惯推断引擎
│   └── knowledge_health/                # 🔹 团队知识健康
│       ├── ebbinghaus.py                # 艾宾浩斯遗忘曲线模型
│       ├── freshness_monitor.py         # 知识新鲜度监控
│       ├── gap_detector.py             # 知识缺口检测
│       └── knowledge_evaluator.py       # 知识重要性评估
│
├── test/                                # 代码测试（检验代码是否有bug）
│   ├── conftest.py                      # pytest fixtures
│   ├── eval_runner.py                   # 测试运行器
│   └── test_*.py                        # 8个测试文件
│
├── eval/                                # 评测（衡量真实性能）
│   ├── datasets/                        # 240 条结构化评测用例 (8×30)
│   │   ├── anti_interference.json       # 30 条 — 抗干扰能力
│   │   ├── contradiction_update.json    # 30 条 — 矛盾信息更新
│   │   ├── efficiency.json              # 30 条 — 效率指标
│   │   ├── command_memory.json          # 30 条 — CLI命令记忆
│   │   ├── decision_memory.json         # 30 条 — 飞书决策记忆
│   │   ├── preference_memory.json       # 30 条 — 个人偏好记忆
│   │   ├── knowledge_health.json        # 30 条 — 团队知识健康
│   │   └── long_term_memory.json        # 30 条 — 长时序记忆 (2年跨度)
│   ├── real_evaluation.py               # 真实系统评测脚本
│   ├── run_ablation.py                  # 消融对比评测
│   └── feishu_real_eval.py              # 飞书真实环境评测
│
├── .hermes/                             # 开发配置
│   └── competition_requirements.md      # 赛题要求
│
├── demo/                                # 演示脚本
└── docs/                                # 设计文档
    ├── architecture_design.md           # 架构设计
    ├── evaluation_scheme.md             # 评测方案 v1.0
    ├── evaluation_scheme_v2.md          # 评测方案 v2.0
    ├── evaluation_benchmark_analysis.md # LONGMEMEVAL/LOCOMO 基准分析
    ├── memory_whitepaper.md             # 记忆白皮书
    └── ...
```

---

## 📊 评测结果

> 以下数据基于 240 条评测数据集对真实 MemScope 系统的评估（非 mock），评估时间：2026-04-29

### 总体结果

| 指标 | 值 |
|------|-----|
| 评测数据集 | 8 个，共 240 条用例 |
| 通过 | 161 条 |
| 失败 | 48 条 |
| 错误 | 31 条 |
| **通过率** | **67.1%** |

### 各维度性能

| 维度 | 数据集 | 用例数 | 通过 | 通过率 | 状态 |
|------|--------|--------|------|--------|------|
| 抗干扰能力 | anti_interference | 30 | 30 | 100.0% | ✅ |
| 矛盾信息更新 | contradiction_update | 30 | 30 | 100.0% | ✅ |
| 团队知识健康 | knowledge_health | 30 | 30 | 100.0% | ✅ |
| CLI命令记忆 | command_memory | 30 | 26 | 86.7% | ✅ |
| 飞书决策记忆 | decision_memory | 30 | 16 | 53.3% | ⚠️ |
| 长时序记忆 | long_term_memory | 30 | 15 | 50.0% | ⚠️ |
| 个人偏好记忆 | preference_memory | 30 | 14 | 46.7% | ⚠️ |
| 效率指标 | efficiency | 30 | 0 | 0.0% | ❌ |

### 效率指标（实测）

| 指标 | P50 | P95 | P99 |
|------|-----|-----|-----|
| 写入延迟 | 6.04ms | 9.24ms | 11.37ms |
| 查询延迟 | 0.23ms | 0.30ms | — |

### 待改进项

- **效率指标（0%）**：评测脚本对新数据集格式兼容不足，效率测量逻辑需重写
- **偏好记忆（46.7%）**：PreferenceExtractor 的模式匹配对隐式偏好覆盖不足
- **长时序记忆（50.0%）**：2年跨度下的记忆召回能力有待增强
- **决策记忆（53.3%）**：DecisionExtractor 对部分中文决策信号词漏提

```bash
# 运行全部 240 条评测数据集的真实评估
python3 eval/real_evaluation.py

# 运行代码测试（检验代码是否有 bug，不作为性能指标）
python3 -m pytest test/ -v
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

## 参考文献与致谢

### 学术基准

1. Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*. [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)
2. Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., & Fang, Y. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*. [arXiv:2402.17753](https://arxiv.org/abs/2402.17753)

### 开源项目

3. [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) — MemScope 的基础框架
4. [Hermes Agent](https://github.com/damxin/memos-local-hermes-plugin) — AI Agent 运行时环境
5. [mem0](https://github.com/mem0ai/mem0) — 记忆系统参考实现

### 赛题

6. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统（公开版）. [赛题链接](https://bytedance.larkoffice.com/wiki/TYewweOPuiHMtBkA1aXcldJonic)

---

## License

[MIT](LICENSE) — *Built for Feishu OpenClaw Competition — 2025*
