<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-grade memory system built on Memos</b></p>
  <p align="center">4 memory dimensions: Command · Decision · Preference · Knowledge Health</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build Passing">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-135/135-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/score-97.5/100-gold.svg" alt="Score">
</p>

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🎯 **四大记忆维度** | 命令记忆 · 决策记忆 · 偏好记忆 · 知识健康度，覆盖企业协作完整场景 |
| 🔍 **混合检索引擎** | FTS5 全文搜索 + 向量搜索 + Pattern 模式匹配，RRF 融合 + MMR 多样性重排 + 时间衰减 |
| 📊 **艾宾浩斯遗忘曲线** | 按 8 种知识类型差异化衰减参数，SM-2 简化版复习间隔计算 |
| ⚡ **高性能** | 写入 P50=5.9ms，查询 P50=0.23ms，吞吐 1468 ops/sec |
| 🔧 **基于 Memos 二次开发** | 继承 Memos 的存储引擎和混合检索架构，扩展四大记忆方向 |

---

## 📁 项目结构

```
MemScope/
├── plugin.yaml                          # Hermes Agent 插件配置
│
├── src/                                 # 核心源码 (~9925 行, 41 个 Python 文件)
│   ├── __init__.py                      # MemScopeProvider 主入口 (595 行)
│   │
│   ├── core/                            # 存储层
│   │   ├── store.py                     # SQLite 存储引擎 (12+ 张表, 2002 行)
│   │   └── embedder.py                  # 嵌入封装 (OpenAI 兼容 API)
│   │
│   ├── recall/                          # 混合检索引擎
│   │   ├── engine.py                    # 三路混合检索 (FTS + Vector + Pattern)
│   │   ├── rrf.py                       # RRF 融合排序算法
│   │   ├── mmr.py                       # MMR 多样性重排
│   │   └── recency.py                   # 时间衰减评分
│   │
│   ├── ingest/                          # 摄取管线
│   │   ├── chunker.py                   # 语义分块器
│   │   ├── dedup.py                     # 去重引擎 (向量 + LLM 判断)
│   │   ├── summarizer.py               # LLM 摘要生成
│   │   └── task_processor.py           # 任务边界检测
│   │
│   ├── command_memory/                  # 🔹 命令记忆 (527 行)
│   │   ├── command_tracker.py           # 命令记录与频率统计
│   │   ├── pattern_analyzer.py          # 子命令模式分析
│   │   └── recommender.py              # 上下文感知推荐
│   │
│   ├── decision_memory/                 # 🔹 决策记忆 (487 行)
│   │   ├── decision_extractor.py        # 中英文决策信号提取
│   │   └── decision_card.py            # 决策卡片推送与生命周期
│   │
│   ├── preference_memory/               # 🔹 偏好记忆 (1790 行)
│   │   ├── preference_extractor.py      # 显式 + 隐式偏好提取
│   │   ├── preference_manager.py        # 偏好生命周期管理
│   │   └── habit_inference.py           # 习惯推断引擎
│   │
│   ├── knowledge_health/                # 🔹 知识健康度 (1021 行)
│   │   ├── ebbinghaus.py                # 艾宾浩斯遗忘曲线模型
│   │   ├── freshness_monitor.py         # 知识新鲜度监控
│   │   ├── gap_detector.py              # 知识缺口检测
│   │   └── knowledge_evaluator.py       # 5 维重要性评估
│   │
│   ├── shared/                          # 共享工具
│   │   └── llm_call.py                  # LLM 多级降级调用器
│   │
│   ├── skill/                           # 技能系统
│   ├── context_engine/                  # 上下文注入
│   └── viewer/                          # Web 查看器
│
├── eval/                                # 评测框架
│   ├── datasets/                        # 8 个数据集, 245 条用例
│   ├── test_*.py                        # 39 个评测测试
│   ├── run_ablation.py                  # 消融对比评测
│   ├── ablation_results.json            # 消融结果
│   └── eval_runner.py                   # 评测运行器
│
├── tests/                               # 单元测试
│   └── test_memscope.py                 # 96 个单元测试
│
├── demo/                                # 演示脚本
│   ├── demo_cli.py                      # CLI 演示
│   ├── demo_feishu.py                   # 飞书集成演示
│   └── demo_scenario.md                 # 演示场景说明
│
└── docs/                                # 设计文档
    ├── architecture_design.md           # 架构设计
    ├── memory_whitepaper.md             # 记忆系统白皮书
    ├── round_1_code_analysis.md         # 代码分析报告
    ├── bad_case_analysis.md             # Bad Case 分析
    └── evaluation_scheme.md             # 评测方案
```

---

## 🏗️ 技术架构

### 核心模块

```
┌─────────────────────────────────────────────────────────┐
│                MemScopeProvider (__init__.py)             │
│              主入口 / 14 个 Plugin Tools                   │
└────┬──────┬──────┬──────┬──────┬──────┬──────┬──────────┘
     │      │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼      ▼
  recall  ingest  cmd   dec   pref   kh    skill
  engine  memory  mem   mem   mem  health
     │      │      │      │      │      │
     └──────┴──────┴──────┴──────┴──────┘
                    │
                    ▼
            ┌──────────────┐     ┌──────────────┐
            │ SqliteStore  │◄────│ RealEmbedder │
            │ (12+ 张表)    │     │ (151 行)     │
            └──────────────┘     └──────────────┘
                    ▲
                    │
            ┌──────────────┐
            │  LLMCaller   │
            │ (218 行)      │
            └──────────────┘
```

### 数据流

```
用户对话 → Chunker (分块) → Summarizer (摘要) → DedupEngine (去重)
    → SqliteStore (存储) → Embedder (向量化)
    → RecallEngine: FTS + Vector + Pattern → RRF 融合 → MMR 重排 → 时间衰减
    → 返回 Top-K 结果
```

### 与 Memos 的关系

| 维度 | 来源 |
|------|------|
| 存储引擎 `SqliteStore` | 继承自 Memos，扩展了 command_history、decisions、user_preferences、knowledge_health 等表 |
| 检索引擎 `RecallEngine` | 继承自 Memos 的 FTS + Vector 基础，新增 Pattern 搜索 |
| 摄取管线 `ingest/` | 继承自 Memos 的 Chunker、Summarizer、TaskProcessor |
| **四大记忆方向** | MemScope 全新开发，Memos 无此能力 |

---

## 📊 评测结果

> 数据来源：`eval_results.json`（评测时间：2026-04-29）

### 总分：97.5 / 100 ⭐ Excellent

### 维度得分

| 维度 | 权重 | 得分 | 加权分 | 测试数 | 通过数 |
|------|------|------|--------|--------|--------|
| 🛡️ 抗干扰 (Anti-Interference) | 25% | 90.0 | 22.5 | 5 | 4 |
| 🔄 矛盾更新 (Contradiction Update) | 25% | 100.0 | 25.0 | 5 | 5 |
| ⚡ 效率 (Efficiency) | 20% | 100.0 | 20.0 | 6 | 6 |
| 🎯 方向 C - 偏好记忆 | 15% | 100.0 | 15.0 | 4 | 4 |
| 📋 方向 D - 决策记忆 | 15% | 100.0 | 15.0 | 5 | 5 |
| **总计** | **100%** | — | **97.5** | **25** | **24** |

### 性能指标

| 指标 | P50 | P95 | P99 |
|------|-----|-----|-----|
| 写入延迟 | 5.90ms | 6.56ms | 6.80ms |
| 查询延迟 | 0.23ms | 0.30ms | — |
| 并发吞吐 | 1468 ops/sec | — | — |
| 内存占用 (200条) | 0.01MB | — | — |

### 消融对比实验

| 配置 | 加权得分 | Direction A | Direction B | Direction C | Direction D |
|------|---------|-------------|-------------|-------------|-------------|
| ❌ 无记忆 | 30.0% | 0% | 0% | 0% | 0% |
| 📦 原生 Memos | 67.5% | 0% | 0% | 7/7 ✅ | 7/8 ✅ |
| 🧠 **MemScope** | **94.5%** | 4/5 ✅ | 6/6 ✅ | 7/7 ✅ | 7/8 ✅ |

> MemScope 相比原生 Memos 提升 **+27%**，Command Memory 和 Decision Memory 从零到完整覆盖。

---

## 📦 评测数据集

8 个数据集，共 **245 个测试用例**：

| 数据集 | 用例数 | 描述 |
|--------|--------|------|
| `command_memory.json` | 35 | CLI 命令记录、频率统计、上下文关联、多跳推理、实体追踪 |
| `decision_memory.json` | 35 | 决策提取、存储、搜索、长时序回忆、多跳推理 |
| `preference_memory.json` | 35 | 偏好提取、推断、冲突解决、衰减、演进、跨维度关联 |
| `knowledge_health.json` | 35 | 新鲜度、遗忘曲线、知识缺口、单点故障、版本管理 |
| `long_term_memory.json` | 30 | 3 个月时间跨度下的记忆保持、覆盖废弃、重复强化 |
| `anti_interference.json` | 25 | 单轮/多轮/相似主题/时序/角色混淆噪声下的召回能力 |
| `contradiction_update.json` | 25 | 直接覆盖、部分更新、时序矛盾、多实体矛盾、撤回 |
| `efficiency.json` | 25 | 写入/查询延迟、内存占用、Token 效率、并发、压力测试 |

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- SQLite 3.38+ (FTS5 支持)

### 安装

```bash
git clone https://github.com/your-org/MemScope.git
cd MemScope
pip install -r requirements.txt  # 如果有的话
```

### 运行单元测试

```bash
python3 -m pytest tests/ -v
```

### 运行评测

```bash
# 完整评测
python3 -m pytest eval/ -v

# 消融对比评测
python3 eval/run_ablation.py
```

### 作为插件使用

```yaml
# plugin.yaml 配置 Hermes Agent 插件
# 提供 14 个 Tools：memory_search, command_log, decision_record, preference_set 等
```

---

## 🔧 技术改进记录 (Round 1)

> 详见：`docs/round_1_code_analysis.md`

### 代码分析发现

对 `src/` 41 个 Python 文件 (~9925 行) 进行深度分析，识别出以下关键问题：

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 🔴 P0 | `SqliteStore` God Class (2002 行, 80+ 方法) | 可维护性 |
| 🔴 P0 | 向量搜索全表扫描 O(n) | 性能瓶颈 |
| 🔴 P0 | `search_chunks` 用 LIKE 而非 FTS5 | 检索质量 |
| 🟡 P1 | N+1 查询 (recall/engine.py) | 查询效率 |
| 🟡 P1 | cosine_similarity 跨模块重复 | 代码质量 |
| 🟡 P1 | Embedder 缓存用 hash() 碰撞风险 | 正确性 |

### 改进建议

1. **拆分 SqliteStore** → ChunkStore, CommandStore, DecisionStore 等子模块
2. **向量搜索改用 ANN 索引** (FAISS / sqlite-vss)
3. **统一 FTS 检索入口**
4. **批量查询替代 N+1**
5. **提取共享工具函数** (cosine_similarity, _parse_metadata)

---

## 🗺️ Roadmap

- [ ] 拆分 SqliteStore God Class 为子模块
- [ ] 向量搜索从全表扫描迁移到 ANN 索引 (FAISS / sqlite-vss)
- [ ] LLM 调用复用 aiohttp.ClientSession + asyncio.gather 并行
- [ ] 添加批量写入 (batch_insert) 和事务支持
- [ ] 结构化日志和性能监控
- [ ] 扩展评测数据集至 500+ 用例
- [ ] 支持多 Agent 协作记忆共享

---

## 📄 License

[Apache License 2.0](LICENSE)
