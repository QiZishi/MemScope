<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/eval--cases-240-blueviolet.svg" alt="Eval Cases">
  <img src="https://img.shields.io/badge/score-54.94-yellow.svg" alt="Score">
  <img src="https://img.shields.io/badge/status-优化中-orange.svg" alt="Status">
</p>

---

## 📋 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-05-06 | v2.4 | **第1轮对抗优化**：修复FTS5索引同步、UNIQUE约束冲突、中文分词；综合得分从33.59提升到54.94 |
| 2026-05-05 | v2.3 | **README 重构**：基于深度审查更新，明确标注评测体系问题；同步 AGENTS.md 项目目标 |
| 2026-05-05 | v2.2 | 评测体系全面修复 + 飞书真实集成 + 2000行审查报告 |
| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条；新增基准分析；test/与eval/分离 |
| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块全部实现；14个插件工具 |
| 2026-04-27 | v1.0 | 初始版本：基础存储层+检索引擎+摄取管线 |

---

## 📊 最新评测结果（2026-05-06）

> 基于 240 条评测数据集对真实 MemScope 系统的评估

### 总体结果

| 指标 | 值 |
|------|-----|
| 评测数据集 | 8 个，共 240 条用例 |
| 通过 | 135 条 |
| 失败 | 68 条 |
| 错误 | 37 条 |
| 通过率 | 56.2% |
| **综合得分** | **54.94 / 100** |
| **评级** | **不及格** |

### 各维度性能

| 维度 | 数据集 | 用例数 | 得分 | 权重 | 状态 |
|------|--------|--------|------|------|------|
| 抗干扰能力 | anti_interference | 30 | 60.4 | 15% | ⚠️ 待提升 |
| 矛盾信息更新 | contradiction_update | 30 | 80.0 | 15% | ✅ 良好 |
| 团队知识健康 | knowledge_health | 30 | 97.9 | 10% | ✅ 优秀 |
| CLI命令记忆 | command_memory | 30 | 86.7 | 10% | ✅ 优秀 |
| 长时序记忆 | long_term_memory | 30 | 85.0 | 5% | ✅ 良好 |
| 飞书决策记忆 | decision_memory | 30 | 41.7 | 15% | ❌ 不及格 |
| 个人偏好记忆 | preference_memory | 30 | 32.8 | 15% | ❌ 严重不足 |
| 效率指标 | efficiency | 30 | 0.0 | 15% | ❌ 未测试 |

### 核心指标

| 指标 | 目标值 | 当前值 | 状态 |
|------|--------|--------|------|
| 命中率 Hit Rate | >= 85% | 待计算 | ⏳ |
| 精确率 Precision | >= 85% | 待计算 | ⏳ |
| 召回率 Recall | >= 90% | 待计算 | ⏳ |
| F1-Score | >= 87% | 待计算 | ⏳ |
| 写入延迟 P50 | <= 200ms | 6.04ms | ✅ |
| 查询延迟 P50 | <= 300ms | 0.23ms | ✅ |

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
│   │   ├── engine.py                    # 三路混合检索 (FTS5+向量+Pattern)
│   │   ├── rrf.py                       # RRF 融合算法
│   │   ├── mmr.py                       # MMR 多样性重排
│   │   └── recency.py                   # 时间衰减评分
│   ├── ingest/                          # 摄取管线
│   │   ├── chunker.py                   # 对话分块器
│   │   ├── dedup.py                     # 去重引擎
│   │   ├── summarizer.py                # LLM 摘要生成
│   │   └── task_processor.py            # 任务边界检测
│   ├── shared/                          # 共享工具
│   │   └── llm_call.py                  # LLM 3层降级调用器
│   ├── skill/                           # 技能系统
│   ├── context_engine/                  # 上下文注入
│   ├── viewer/                          # Web 查看器
│   ├── command_memory/                  # 🔹 方向A: CLI 命令记忆
│   ├── decision_memory/                 # 🔹 方向B: 飞书决策记忆
│   ├── preference_memory/               # 🔹 方向C: 个人偏好记忆
│   ├── knowledge_health/                # 🔹 方向D: 团队知识健康
│   └── feishu/                          # 🔹 飞书 API 集成
│
├── test/                                # 代码测试
├── eval/                                # 评测
│   ├── datasets/                        # 240 条结构化评测用例 (8×30)
│   ├── real_evaluation.py               # 真实系统评测脚本
│   └── history/                         # 评测历史记录
│
├── demo/                                # 演示脚本
├── docs/                                # 设计文档
│   ├── feishu_cli_integration.md        # 飞书CLI集成分析
│   ├── optimization_history.md          # 优化历史记录
│   └── ...
│
├── AGENTS.md                            # 开发指南
├── README.md                            # 本文件
└── LICENSE                              # MIT License
```

---

## 🎯 项目目标

详见 [AGENTS.md](AGENTS.md) 中的完整定义。

1. 评测数据集全面评估 MemScope 真实性能
2. 评测数据集格式符合主流 memory 评测规范
3. 包含长时序多轮对话样本
4. 评测代码连接 Hermes Agent/OpenClaw 做实际评测
5. MemScope 真正连接 Hermes Agent 替代原有记忆架构
6. CLI 终端和飞书端可自由切换交互演示

---

## 运行方式

```bash
# 运行代码测试
python3 -m pytest test/ -v

# 运行评测
python3 eval/real_evaluation.py

# 查看评测历史
ls eval/history/

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
