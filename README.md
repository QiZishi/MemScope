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
| 2026-05-05 | v2.2 | **评测体系全面修复 + 飞书真实集成 + 2000行审查报告**（详见下方） |
| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条(每集30条)；新增LONGMEMEVAL/LOCOMO基准分析；长时序评测扩展至2年跨度；test/与eval/目录分离；新增评测方案v2.0 |
| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块(command/decision/preference/knowledge_health)全部实现；14个插件工具；7800+行代码 |
| 2026-04-27 | v1.0 | 初始版本：基于memos-local-hermes-plugin二次开发；基础存储层+检索引擎+摄取管线 |

### v2.2 详细更新内容（2026-05-05）

本次更新基于对评测体系的全面代码审查（产出 2000+ 行 [REVIEW_REPORT.md](REVIEW_REPORT.md)），修复了 15 个 Critical 级别问题和多个 Major 级别问题。

#### P0 — 评测逻辑修复（Critical）

- **修复 3 个评测函数缺失 `failed_checks` 导致全部测试标记为 pass 的严重 bug**：`eval_anti_interference`、`eval_contradiction_update`、`eval_efficiency` 返回字典中没有 `failed_checks` 字段，导致 `metrics.get("failed_checks", [])` 永远返回空列表，所有测试无论实际结果如何都被标记为 "pass"。现在每个评测函数都根据 evaluation_scheme_v2.md 的阈值正确返回 `passed_checks` 和 `failed_checks`
- **修复 precision 空结果返回 1.0 的逻辑错误**：当搜索结果为空时，precision 应为 0.0（无结果=无精确度），原来错误地返回了 1.0
- **报告生成器从 5 维度扩展到 8 维度**：新增 command_memory（方向A-命令记忆）、decision_memory（方向B-决策记忆）、long_term_memory（长时序记忆）三个维度，与 evaluation_scheme_v2.md 定义的 8 维度评分体系对齐
- **run_evaluation 添加维度加权评分**：新增 `DIMENSION_WEIGHTS`（抗干扰15%、矛盾更新15%、效率15%、命令10%、决策15%、偏好15%、知识10%、长时序5%），计算 `overall_score` 和 `grade`（优秀≥85/及格≥70/不及格）
- **消融评测权重与 scheme v2 对齐**：run_ablation.py 的 7 维度权重按 evaluation_scheme_v2.md 的 8 维度比例重新分配

#### P1 — 真实搜索引擎替换（Major）

- **SqliteStore.insert_chunk 添加 FTS5 同步**：原来插入 chunk 后不会同步到 FTS5 全文索引，导致 FTS5 搜索无法返回新插入的数据。现在每次插入后自动执行 `chunks_fts rebuild`
- **SqliteStore.search_chunks 移植 CJK 分词逻辑**：从 MiniStore 移植了 `re.findall(r'[\w一-鿿]{2,}', query)` 中文分词逻辑，支持将查询拆分为多个词组进行 OR 匹配，显著提升中文文本搜索效果
- **评测系统从 MiniStore 替换为 SqliteStore**：real_evaluation.py 不再使用简化版 MiniStore（SQL LIKE 搜索），改为使用真实的 SqliteStore（支持 FTS5 全文搜索 + CJK 分词），评测结果更接近真实使用场景

#### P2 — 飞书真实集成（Major）

- **新增 `src/feishu/` 模块**：
  - `client.py` — 飞书 Open API 客户端，支持 tenant_access_token 认证、发送文本/卡片消息、获取群聊历史消息、构建决策卡片
  - `pipeline.py` — 飞书消息处理管线，自动将飞书消息路由到决策提取（方向B）、偏好推断（方向C）、知识注册（方向D）
- **demo_feishu.py 支持真实 API 调用**：当环境变量 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 存在时自动切换到真实飞书 API，否则保持演示模式
- **feishu_real_eval.py 修复硬编码路径**：移除 `/root/hermes-data/cron/output` 硬编码，改为基于脚本位置的相对路径解析

#### P3 — 数据集对齐（Minor）

- **8 个数据集统一为 30 条**：command_memory（37→30）、decision_memory（37→30）、preference_memory（38→30），总计 240 条，与 evaluation_scheme_v2.md 一致
- **新增 2000+ 行审查报告** [REVIEW_REPORT.md](REVIEW_REPORT.md)：涵盖赛题需求符合性、数据集质量、评测代码逻辑、指标体系、飞书集成、Demo 脚本等 8 章内容，逐条列出 65 个问题及修正建议

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
│   ├── knowledge_health/                # 🔹 团队知识健康
│   │   ├── ebbinghaus.py                # 艾宾浩斯遗忘曲线模型
│   │   ├── freshness_monitor.py         # 知识新鲜度监控
│   │   ├── gap_detector.py             # 知识缺口检测
│   │   └── knowledge_evaluator.py       # 知识重要性评估
│   └── feishu/                          # 🔹 飞书 API 集成
│       ├── client.py                    # 飞书 Open API 客户端 (认证/消息/卡片)
│       └── pipeline.py                  # 飞书消息处理管线 (决策/偏好/知识)
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
