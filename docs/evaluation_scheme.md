# MemScope 评测方案

> **版本**: 3.0 | **更新时间**: 2026-05-06
> **定位**: MemScope 是企业级 Memory 系统（非 RAG），评测方案围绕记忆的提取、存储、检索、更新、遗忘全生命周期设计

---

## 1. 评测目标

### 1.1 核心定位：Memory 系统 vs RAG 系统

MemScope 评测的核心目标是**证明其作为 Memory 系统的真实性能**，而非仅展示向量检索能力。

| 维度 | 传统 RAG 系统 | MemScope Memory 系统 |
|------|--------------|---------------------|
| 存储模型 | 扁平化文本切片 | 结构化记忆（事实/决策/偏好/知识） |
| 写入能力 | 仅 chunk 索引 | 事实提取 + 矛盾检测 + 记忆合并 |
| 查询能力 | 语义相似度匹配 | 统一召回（结构化 + 非结构化） |
| 更新机制 | 无 / 重新索引 | 时序感知覆写 + 历史保留 |
| 遗忘机制 | 无 | 基于遗忘曲线的主动遗忘 |

### 1.2 三大证明目标

依据赛题「挑战三：证明它的价值 (Prove it)」要求：

1. **真的"记住了"** — 在干扰信息中精准召回历史记忆，召回率 ≥ 85%
2. **理解了"变化"** — 正确处理矛盾信息和时序推理，矛盾检测率 ≥ 90%
3. **产生了"效能"** — 量化操作节省和延迟优化，操作节省率 ≥ 50%

### 1.3 评测设计原则

- **区分代码测试与性能评估**：代码测试（test/）验证功能正确性，性能评估（eval/）衡量真实指标
- **全量评测**：必须运行全部 240 条样本，禁止选取子集
- **规则判定**：使用关键词匹配 + 规则计算指标，不依赖 LLM-as-judge
- **结果可追溯**：每次评测输出 JSON + Markdown 报告，含完整执行轨迹

---

## 2. 评测数据集

### 2.1 数据集总览

共 **8 个数据集**，每个 30 条样本，合计 **240 条**。

| # | 数据集名称 | 文件名 | 样本数 | 覆盖方向 | 推理类型 |
|---|-----------|--------|--------|---------|---------|
| 1 | 飞书决策记忆 | `feishu_decision_memory.json` | 30 | 方向B：飞书决策记忆 | single_hop |
| 2 | 团队知识健康 | `feishu_knowledge_health.json` | 30 | 方向D：团队知识健康 | single_hop |
| 3 | 个人偏好记忆 | `feishu_preference_memory.json` | 30 | 方向C：个人偏好记忆 | single_hop / knowledge_update |
| 4 | CLI命令记忆 | `feishu_command_memory.json` | 30 | 方向A：CLI命令记忆 | single_hop |
| 5 | 长期记忆 | `feishu_long_term_memory.json` | 30 | 综合：跨方向长时序 | single_hop |
| 6 | 效能验证 | `feishu_efficiency.json` | 30 | 必测项：效能指标验证 | single_hop |
| 7 | 矛盾更新 | `feishu_contradiction_update.json` | 30 | 必测项：矛盾信息更新 | single_hop |
| 8 | 抗干扰 | `feishu_anti_interference.json` | 30 | 必测项：抗干扰测试 | single_hop |

### 2.2 四大业务方向

**方向A：CLI命令记忆（command_memory，30条）**
- 自动记录用户的高频命令模式、常用参数组合、项目路径偏好
- 子类别：高频命令识别、命令推荐、项目路径关联、上下文感知推荐、操作节省验证

**方向B：飞书决策记忆（decision_memory，30条）**
- 从对话/文档中自动提取决策、理由、反对意见、结论
- 子类别：中文决策提取、英文决策提取、决策搜索、决策卡片推送、决策生命周期

**方向C：个人偏好记忆（preference_memory，30条）**
- 通过观察用户行为，自动学习其偏好和规律
- 子类别：显式偏好提取、隐式偏好推断、偏好更新、上下文感知推荐、偏好冲突解决

**方向D：团队知识健康（knowledge_health，30条）**
- 允许团队注入需要长期记住的事项，设置遗忘曲线
- 子类别：知识新鲜度检测、遗忘预警、知识缺口检测、团队知识同步、关键知识遗忘

### 2.3 三项必测

**必测项1：抗干扰测试（anti_interference，30条）**
- 赛题要求：在输入大量无关对话/操作后，系统依然能精准捞取关键记忆
- 样本特点：在 setup.conversations[] 中注入大量噪声文本（食堂菜单、快递查询等），关键信息夹杂其中
- 子类别：噪声干扰、多轮连续噪声、高相似度干扰、时间跨度干扰、角色混淆干扰

**必测项2：矛盾更新测试（contradiction_update，30条）**
- 赛题要求：先后输入两条冲突的指令，证明系统能理解时序，正确覆写记忆
- 样本特点：在 setup.conversations[] 中包含新旧两条冲突信息（如"工位A-305"→"工位B-201"）
- 子类别：直接覆盖型、部分更新型、时间线矛盾、多实体并发、撤回/取消型

**必测项3：效能验证（efficiency，30条）**
- 赛题要求：量化展示成果（使用前需要敲50个字符，使用后只需10个，提效80%）
- 子类别：写入延迟、查询延迟、内存占用、Token消耗效率、并发性能

**综合方向：长期记忆（long_term_memory，30条）**
- 跨越2年的长时间记忆能力测试（3个月~2年跨度）
- 子类别：3~6个月回忆、6~12个月回忆、1~2年回忆、跨年度信息更新

### 2.4 样本格式说明

每个数据集文件结构：

```json
{
  "dataset_name": "feishu_xxx",
  "version": "2.0",
  "total_cases": 30,
  "test_cases": [
    {
      "test_id": "feishu_xxx_001",
      "name": "样本名称",
      "difficulty": "easy | medium | hard",
      "category": "子类别名称",
      "reasoning_type": "single_hop | knowledge_update",
      "setup": {
        "conversations": [
          {
            "role": "user | assistant",
            "content": "对话内容文本",
            "timestamp": "ISO 8601 格式时间戳"
          }
        ]
      },
      "query": {
        "text": "查询文本（模拟用户实际提问）",
        "type": "search | recommend | health_check"
      },
      "expected": {
        "answer": "期望答案文本",
        "keywords": ["必须包含的关键词1", "关键词2"],
        "forbidden": ["禁止出现的关键词1"]
      }
    }
  ]
}
```

**关键字段说明**：

| 字段 | 说明 |
|------|------|
| `setup.conversations[]` | 多轮对话数组，Memory 系统需要从中提取并记忆事实 |
| `setup.conversations[].timestamp` | ISO 8601 时间戳，用于时间推理评测 |
| `query.text` | 查询文本，模拟用户实际提问 |
| `expected.keywords` | 关键词列表，用于计算 Recall 和 Precision |
| `expected.forbidden` | 禁止出现的关键词，用于计算噪声注入率 |

**样本独立性原则**：每个样本彼此独立，不共享公司名、人名、项目名等实体，避免样本间"记忆泄露"。

---

## 3. 评测维度与指标

### 3.1 检索指标

#### Recall@k（召回率@k）

```
Recall@k = 在 top-k 检索结果中命中的关键词数 / 总期望关键词数
```

- k 值：k=1, k=3, k=5
- 计算方式：逐关键词匹配（大小写不敏感），命中即跳出
- 目标：Recall@1 ≥ 60%, Recall@3 ≥ 75%, Recall@5 ≥ 85%

#### MRR（Mean Reciprocal Rank）

```
MRR = (1/|Q|) × Σ (1 / rank_i)
```

- 第一个包含正确关键词的结果的排名倒数的均值
- 目标：MRR ≥ 65%

#### Precision（精确率）

```
Precision = 返回结果中正确信息数 / 返回总信息数
```

- 结合 forbidden 关键词计算，返回结果中相关信息的比例
- 目标：Precision ≥ 40%

#### F1-Score

```
F1 = 2 × Precision × Recall / (Precision + Recall)
```

- 目标：F1 ≥ 50%

#### 命中率（Hit Rate）与噪声注入率

```
命中率 = 包含至少一个期望关键词的样本数 / 总样本数
噪声注入率 = 返回结果中包含 forbidden 关键词的条数 / 返回总条数
```

- 目标：命中率 ≥ 85%, 噪声注入率 ≤ 25%

### 3.2 Memory 能力指标

Memory 能力指标衡量 MemScope 区别于 RAG 系统的核心能力。

#### 事实提取 P/R/F1

```
Precision = 正确提取的事实数 / 总提取的事实数
Recall = 正确提取的事实数 / 应提取的总事实数
F1 = 2 × P × R / (P + R)
```

- 从原始对话文本中提取结构化事实（决策/偏好/知识）的准确性
- 测试方法：使用 `memory_performance_eval.py` 中的 30+ 组标注测试数据
- **当前结果**：P=90%, R=90%, F1=90%

#### 矛盾检测率

```
矛盾检测率 = 正确检测到的矛盾数 / 总矛盾数
```

- 当新信息与已存储信息冲突时，系统能否正确识别并更新
- 判定规则：查询结果包含最新值关键词且不包含旧值关键词
- **当前结果**：100%

#### 推荐相关性

```
Relevance@k = top-k 推荐中相关条数 / k
```

- 当用户开始输入时，系统主动推荐的记忆与当前上下文的相关程度
- **当前结果**：推荐 F1=76.9%

### 3.3 效能指标

#### 写入/查询延迟

```
写入延迟 = insert_chunk() 调用的端到端耗时（毫秒）
查询延迟 = search_chunks() 调用的端到端耗时（毫秒）
```

- 统计量：P50（中位数）、P95、P99
- **当前结果**：写入 P50=1.88ms, 查询 P50=1.56ms
- 目标：写入 P50 ≤ 200ms, 查询 P50 ≤ 300ms

#### 操作节省率

```
操作节省率 = (无记忆操作步数 - 有记忆操作步数) / 无记忆操作步数 × 100%
```

- 对比 5 类典型任务在有/无记忆系统下的操作步数
- 有记忆系统均只需 1 步（直接查询），无记忆系统需 3~6 步
- **当前结果**：77%（目标 ≥ 50%）

---

## 4. 评测脚本说明

### 4.1 `direct_api_eval.py` — 240 样本检索评测

直接调用 MemScope API 进行全量检索评测。加载全部 8 个数据集（240 条），对每条执行：写入 setup.conversations → 查询 query.text → 匹配 expected.keywords。计算 Recall@k、MRR、Precision、F1、命中率、噪声注入率，测量搜索/写入延迟。

```bash
python3 eval/direct_api_eval.py
# 输出: eval/history/{timestamp}/eval_report.md + eval_results.json
```

### 4.2 `memory_performance_eval.py` — Memory 能力性能评测

评测 Memory 系统的核心能力：①事实提取（30+ 组标注数据的 P/R/F1）②矛盾检测（新旧信息冲突场景）③检索综合（调用检索指标逻辑）④主动推荐（Relevance@k）⑤遗忘正确性。

```bash
python3 eval/memory_performance_eval.py
# 输出: eval/history/performance_eval_{timestamp}.json
```

### 4.3 `memory_lifecycle_eval_v2.py` — 生命周期代码测试

测试 Memory 系统完整生命周期的 10 项能力：Fact Extraction、Contradiction Detection、Unified Recall、Memory Consistency、Temporal Ordering、Consolidation、Health Monitoring、Cross-Agent Sharing、Memory Forgetting、Proactive Recommendation。

```bash
python3 eval/memory_lifecycle_eval_v2.py
# 输出: eval/history/memory_lifecycle_{timestamp}.json
```

### 4.4 `e2e_integration_test.py` — 端到端集成测试

测试所有 Memory 能力在真实场景下的 8 阶段协作：①团队对话摄入 ②矛盾检测与解决 ③记忆合并 ④健康度监控 ⑤跨Agent共享 ⑥过期记忆遗忘 ⑦主动推荐 ⑧会话预加载 briefing。

```bash
python3 eval/e2e_integration_test.py
# 输出: eval/history/e2e_integration_{timestamp}.json
```

### 4.5 `efficiency_eval.py` — 效能评测

测量系统级效能指标：①写入延迟（连续写入100条，P50/P95/P99）②查询延迟（多组查询各3次，P50/P95/P99）③操作节省率（5类典型任务对比）。

```bash
python3 eval/efficiency_eval.py
```

### 4.6 脚本关系总览

| 脚本 | 评测类型 | 评测内容 | 输出 |
|------|---------|---------|------|
| `direct_api_eval.py` | 检索评测 | 240条全量检索指标 | eval_report.md + JSON |
| `memory_performance_eval.py` | 能力评测 | 事实/矛盾/推荐/遗忘 | performance_eval JSON |
| `memory_lifecycle_eval_v2.py` | 生命周期 | 10项Memory能力 | lifecycle JSON |
| `e2e_integration_test.py` | 集成测试 | 8阶段全流程协作 | integration JSON |
| `efficiency_eval.py` | 效能评测 | 延迟/操作节省率 | 效能报告 |

---

## 5. 评测流程

### 5.1 完整评测流程

```
第一步：环境准备
├── 确保 SQLite 数据库已初始化
├── 确保 src/ 目录下所有模块可正常 import
└── 清空历史测试数据（避免污染）

第二步：运行检索评测（python3 eval/direct_api_eval.py）
├── 加载 8 个数据集 × 30 条 = 240 条样本
├── 逐样本：写入 → 查询 → 匹配关键词 → 计算指标
└── 输出 eval_report.md + eval_results.json

第三步：运行 Memory 能力评测（python3 eval/memory_performance_eval.py）
├── 测试事实提取 P/R/F1
├── 测试矛盾检测率
├── 测试推荐相关性
└── 输出 performance_eval JSON

第四步：运行生命周期测试（python3 eval/memory_lifecycle_eval_v2.py）
├── 测试 10 项 Memory 能力
└── 输出 memory_lifecycle JSON

第五步：运行端到端集成测试（python3 eval/e2e_integration_test.py）
├── 测试 8 阶段全流程协作
└── 输出 e2e_integration JSON

第六步：运行效能评测（python3 eval/efficiency_eval.py）
├── 测量写入/查询延迟 P50/P95/P99
├── 计算操作节省率
└── 输出效能报告

第七步：汇总报告
├── 汇总各脚本输出的评测结果
├── 生成综合评测报告（Markdown + JSON）
└── 对标目标值，标注达标/未达标
```

### 5.2 评测结果汇总表

| 指标类别 | 指标名称 | 目标值 | 当前值 | 状态 |
|---------|---------|--------|--------|------|
| 检索指标 | Recall@1 | ≥ 60% | 58.01% | 接近 |
| 检索指标 | Recall@3 | ≥ 75% | 77.84% | ✅ |
| 检索指标 | Recall@5 | ≥ 85% | 84.99% | 接近 |
| 检索指标 | MRR | ≥ 65% | 68.67% | ✅ |
| 检索指标 | 命中率 | ≥ 85% | 84.99% | 接近 |
| 检索指标 | 综合评分 | ≥ 65 | 67.05 | ✅ |
| Memory能力 | 事实提取 F1 | ≥ 85% | 90% | ✅ |
| Memory能力 | 矛盾检测率 | ≥ 90% | 100% | ✅ |
| Memory能力 | 推荐 F1 | ≥ 70% | 76.9% | ✅ |
| 效能指标 | 写入延迟 P50 | ≤ 200ms | 1.88ms | ✅ |
| 效能指标 | 查询延迟 P50 | ≤ 300ms | 1.56ms | ✅ |
| 效能指标 | 操作节省率 | ≥ 50% | 77% | ✅ |

### 5.3 各数据集检索指标明细

| 数据集 | R@1 | R@3 | R@5 | MRR | Precision | F1 |
|--------|-----|-----|-----|-----|-----------|-----|
| decision_memory | 78.33% | 78.33% | 91.67% | 81.50% | 42.00% | 52.88% |
| knowledge_health | 30.00% | 60.00% | 80.00% | 46.39% | 28.78% | 38.75% |
| preference_memory | 36.67% | 60.00% | 70.00% | 49.22% | 20.78% | 30.40% |
| command_memory | 73.56% | 93.28% | 93.28% | 83.42% | 47.89% | 57.42% |
| long_term_memory | 55.00% | 82.22% | 84.44% | 68.61% | 48.83% | 57.61% |
| efficiency | 58.33% | 85.00% | 88.33% | 71.78% | 41.22% | 50.73% |
| contradiction_update | 36.67% | 65.00% | 73.33% | 51.25% | 42.67% | 49.81% |
| anti_interference | 95.56% | 98.89% | 98.89% | 97.22% | 52.94% | 64.70% |

### 5.4 评测注意事项

1. **独立实例**：每个样本使用独立的存储实例，避免数据污染
2. **全量运行**：必须运行全部 240 条，禁止选取子集
3. **结果持久化**：每次评测自动生成 JSON 报告存入 `eval/history/`
4. **可复现性**：相同环境多次运行结果应保持一致

---

## 6. 与学术基准对标

| 维度 | LONGMEMEVAL (ICLR 2025) | LOCOMO (ACL 2024) | MemScope |
|------|------------------------|-------------------|----------|
| 样本数 | 500 | 1,813 | 240 |
| 会话跨度 | 40-500 会话 | 35 会话 | 2 年时间跨度 |
| 评测方式 | LLM-as-judge | 人工+自动 | 规则评测（无 LLM 依赖） |
| 问题类型 | 7 种 | 4 种 | 8 维度 × 子类别 |
| 业务场景 | 通用对话 | 日常对话 | 企业办公/研发 |
| 核心指标 | QA 准确率 | QA 准确率 | 检索 + Memory能力 + 效能 |
| 结构化能力 | 无 | 无 | 事实提取/矛盾检测/记忆合并 |

---

## 参考文献

1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*. arXiv:2410.10813.
2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*. arXiv:2402.17753.
3. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统（公开版）.
