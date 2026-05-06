<p align="center">
  <h1 align="center">🧠 MemScope</h1>
  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/samples-240-brightgreen.svg" alt="240 Samples">
  <img src="https://img.shields.io/badge/recall@1-58.01%25-brightgreen.svg" alt="Recall@1">
  <img src="https://img.shields.io/badge/memory_f1-90%25-brightgreen.svg" alt="Memory F1">
</p>

---

## 📊 最新评测结果（v5.9）

> 评测时间：2026-05-06
> 评测方式：直接调用 MemScope API（240条样本，8个数据集）
> 性能评测脚本：eval/memory_performance_eval.py（用指标衡量，非通过率）

### Memory能力指标（核心创新）

| 能力 | 指标 | 值 | 说明 |
|------|------|-----|------|
| **事实提取** | Precision | **90.0%** | 从对话中提取决策/偏好/知识的准确率 |
| **事实提取** | Recall | **90.0%** | 不遗漏重要事实 |
| **事实提取** | F1 | **90.0%** | 精确率和召回率的调和平均 |
| **矛盾检测** | Detection Rate | **100%** | 新信息自动覆写旧信息（含跨类型检测） |
| **矛盾检测** | False Positives | **0** | 无误报 |
| **主动推荐** | Precision | **100%** | 推荐的记忆全部相关 |
| **主动推荐** | F1 | **76.9%** | 推荐的精确率和召回率平衡 |

### 检索指标（240样本）

| 指标 | 值 | 说明 |
|------|-----|------|
| **Recall@1** | **58.01%** | Top-1 结果命中率 |
| **Recall@3** | **77.84%** | Top-3 结果命中率 |
| **Recall@5** | **84.99%** | Top-5 结果命中率 |
| **MRR** | **68.67%** | 平均倒数排名 |
| **F1分数** | **50.29%** | 精确率和召回率的调和平均 |
| **综合评分** | **67.05** | 加权综合得分（满分100） |

### 效能指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 写入延迟 P50 | **1.88ms** | ≤200ms | ✅ 达标 |
| 查询延迟 P50 | **1.56ms** | ≤300ms | ✅ 达标 |
| 操作节省率 | **77.0%** | ≥50% | ✅ 达标 |

---

## 🧠 Memory系统能力（10项）

> 不只是RAG检索，而是完整的Memory生命周期

| # | 能力 | 说明 | API |
|---|------|------|-----|
| 1 | **事实提取** | 从对话中自动提取决策/偏好/知识 | `FactExtractor.extract_and_store()` |
| 2 | **矛盾检测** | 新信息自动覆写旧信息（含跨类型） | `extract_and_store(detect_contradictions=True)` |
| 3 | **统一召回** | 跨chunks+决策+偏好+知识搜索 | `MemoryManager.recall()` |
| 4 | **记忆一致性** | 矛盾后只返回最新信息 | 决策status=active/superseded/forgotten |
| 5 | **时序排序** | 后续信息优先于早期信息 | createdAt排序 |
| 6 | **记忆整合** | 多个相关记忆合并为高层知识 | `consolidate_memories()` |
| 7 | **健康监控** | freshness/consistency/coverage | `check_memory_health()` |
| 8 | **跨Agent共享** | Alice的记忆可共享给Bob | `share_memory()` / `get_shared_memories()` |
| 9 | **记忆遗忘** | 过时/被覆写记忆自动遗忘 | `auto_forget()` / `execute_forgetting()` |
| 10 | **主动推荐** | 基于上下文自动推送相关记忆 | `proactive_recommend()` / `prefetch()` |

### 端到端集成测试（9阶段）

| 阶段 | 说明 | 结果 |
|------|------|------|
| 摄入 | 对话自动提取事实 | ✅ |
| 矛盾 | 新信息覆写旧信息 | ✅ |
| 一致性 | 只返回最新值 | ✅ |
| 整合 | 多记忆合并为高层知识 | ✅ |
| 健康 | freshness/consistency/coverage | ✅ |
| 共享 | 跨Agent记忆传递 | ✅ |
| 遗忘 | 过时记忆自动遗忘 | ✅ |
| 推荐 | 基于上下文主动推荐 | ✅ |
| 预取 | 会话开始记忆简报 | ✅ |

---

## 📋 更新日志

### v5.9 (2026-05-06) — 性能优化
- **性能评测**: eval/memory_performance_eval.py — 用指标而非通过率衡量性能
  - 事实提取: Precision=90.0%, Recall=90.0%, F1=90.0%
  - 矛盾检测: Detection Rate=100%, False Positives=0
  - 主动推荐: Precision=100%, Recall=62.5%, F1=76.9%
- **关键优化**:
  - 偏好值清理: 'Python写代码'->'Python', 'Go语言'->'Go'
  - 跨类型矛盾检测: knowledge vs decision
  - 推荐相关性评分: min_relevance过滤噪声

### v5.8 (2026-05-06)
- **端到端集成测试**: eval/e2e_integration_test.py (9/9 100%)

### v5.7 (2026-05-06)
- **主动推荐系统**: proactive_recommend() / prefetch()

### v5.6 (2026-05-06)
- **记忆遗忘系统**: schedule_forgetting() / auto_forget() / execute_forgetting()

### v5.5 (2026-05-06)
- **跨Agent记忆共享**: share_memory() / get_shared_memories()
- **记忆健康监控**: check_memory_health()

### v5.4 (2026-05-06)
- **记忆整合系统**: consolidate_memories() — 决策时间线/偏好画像/知识图谱

### v5.3 (2026-05-06)
- **Memory生命周期系统**: FactExtractor + MemoryManager

### v5.1 (2026-05-06)
- **搜索评分算法优化**: distinctive/common词项分类

### v5.0 (2026-05-06)
- **评测体系全面调整**: 240条样本/多轮对话格式/Recall@k/MRR

---

## Overview

MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。

### 四大记忆能力（赛题方向）

| 能力模块 | 核心功能 | 子模块 |
|----------|---------|--------|
| **command_memory** CLI命令记忆 | 高频命令统计、项目路径关联、上下文感知推荐 | command_tracker, pattern_analyzer, recommender |
| **decision_memory** 飞书决策记忆 | 中英文决策提取、历史决策卡片推送 | decision_extractor, decision_card |
| **preference_memory** 个人偏好记忆 | 偏好提取(显式+隐式)、行为模式推断、冲突解决 | preference_extractor, preference_manager, habit_inference |
| **knowledge_health** 团队知识健康 | 艾宾浩斯遗忘曲线、知识缺口检测、遗忘预警 | ebbinghaus, freshness_monitor, gap_detector, knowledge_evaluator |

---

## 🏗️ 项目结构

```
MemScope/
├── src/                          # 核心源码
│   ├── core/
│   │   ├── store.py              # SQLite存储层（FTS5全文索引 + LIKE回退）
│   │   └── fact_extractor.py     # Memory核心：FactExtractor + MemoryManager
│   ├── recall/engine.py          # 混合检索引擎（FTS + Pattern + RRF融合）
│   ├── command_memory/           # 方向A: CLI命令记忆
│   ├── decision_memory/          # 方向B: 飞书决策记忆
│   ├── preference_memory/        # 方向C: 个人偏好记忆
│   ├── knowledge_health/         # 方向D: 团队知识健康
│   ├── feishu/                   # 飞书API集成
│   ├── ingest/                   # 摄取管线（分块/去重/摘要）
│   └── context_engine/           # 上下文自动注入
├── eval/                         # 评测体系
│   ├── direct_api_eval.py        # 核心检索能力评测（240条样本）
│   ├── memory_performance_eval.py # Memory能力性能评测（P/R/F1指标）
│   ├── memory_lifecycle_eval_v2.py # Memory生命周期评测（代码测试）
│   ├── e2e_integration_test.py   # 端到端集成测试（9阶段）
│   ├── efficiency_eval.py        # 效能指标评测
│   ├── ablation_eval.py          # 消融对比评测
│   └── datasets/                 # 评测数据集（8个×30条=240条）
├── demo/                         # 演示脚本
├── docs/                         # 文档
└── test/                         # 代码测试（pytest）
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- SQLite 3.35+（支持FTS5）

### 安装

```bash
git clone https://github.com/QiZishi/MemScope.git
cd MemScope
pip install -r requirements.txt
```

### 运行评测

```bash
# 核心检索能力评测（240条样本）
python3 eval/direct_api_eval.py

# Memory能力性能评测（P/R/F1指标）
python3 eval/memory_performance_eval.py

# Memory生命周期评测（代码测试）
python3 eval/memory_lifecycle_eval_v2.py

# 端到端集成测试
python3 eval/e2e_integration_test.py

# 效能指标评测
python3 eval/efficiency_eval.py
```

---

## 📊 评测体系

### 评测数据集

8个数据集，每个30条样本，共240条，覆盖四大记忆方向 + 三个赛题必测项：

| 数据集 | 权重 | 样本结构 | 推理类型 |
|--------|------|----------|----------|
| anti_interference | 15% | 多轮对话 + 噪声干扰 | single_hop, adversarial |
| contradiction_update | 15% | 信息变更 + 时序覆写 | knowledge_update, temporal |
| efficiency | 15% | 查询效率 + 准确性 | single_hop |
| command_memory | 10% | 操作模式识别 | single_hop, multi_hop |
| decision_memory | 15% | 团队决策提取 | single_hop, multi_hop, temporal |
| preference_memory | 15% | 个人偏好记忆 | single_hop, adversarial, knowledge_update |
| knowledge_health | 10% | 团队知识健康 | single_hop |
| long_term_memory | 5% | 长时序记忆 | temporal, multi_hop |

### 评测指标

| 指标 | 说明 | 来源 |
|------|------|------|
| Recall@k | Top-k 结果命中率 | LongMemEval |
| MRR | 平均倒数排名 | 信息检索标准 |
| Precision | 返回结果中相关比例 | 赛题要求 |
| F1 | P和R的调和平均 | 赛题要求 |
| 延迟 P50/P95/P99 | 写入和查询延迟 | 赛题要求 |
| 操作节省率 | 有/无记忆的操作步数对比 | 赛题要求 |

---

## 🔧 技术架构

### Memory生命周期

```
对话输入 → 事实提取(FactExtractor) → 矛盾检测 → 结构化存储
                                              ↓
              记忆整合(consolidate) ← 多轮积累 ←┘
                    ↓
    主动推荐(proactive_recommend) → 上下文注入
                    ↓
    记忆遗忘(auto_forget) → 过时记忆清理
```

### 检索流程

```
查询 → 词项提取 → 词项分类(distinctive/common) → FTS5搜索 → 评分排序 → 结果
                      ↓
              中文2-3字切分 + 英文单词 + 数字
                      ↓
         FTS5: (distinctive1 OR distinctive2) AND (common1 OR common2)
                      ↓
         评分: distinctive覆盖(70%) + common覆盖(10%) + 邻近度(15%) + 精确匹配(5%)
```

### 存储架构

- **SQLite** + **FTS5** 全文索引
- 零外部依赖，纯本地运行
- 支持 private/shared/all 三级可见性

---

## 参考文献

1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.
3. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统.

---

## License

MIT
