# MemScope 项目优化 — 结构化任务提示语

> 生成时间：2026-05-05
> 基于：docs/ 文件夹、REVIEW_REPORT.md、持久记忆中的项目目标

---

## 背景信息

### 项目定位
MemScope 是飞书 OpenClaw 大赛参赛作品，定位为"企业级长周期协作记忆引擎"，作为 Hermes Agent 的插件运行。

### 赛题三大挑战
1. **定义记忆** — 明确企业环境下有价值的个人/团队记忆场景
2. **构建记忆引擎** — 实现记忆的提取、存储、检索、更新和遗忘
3. **证明它的价值** — 通过评测证明系统"记住了"并"产生了实际效能"

### 四大方向
- **方向A**: CLI 高频命令与工作流记忆
- **方向B**: 飞书项目决策与上下文记忆
- **方向C**: 个人工作习惯与偏好记忆
- **方向D**: 团队知识断层与遗忘预警

### 核心评测指标（来自 evaluation_scheme_v2.md）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 命中率 Hit Rate | >= 85% | 搜索结果中包含目标信息的比例 |
| 精确率 Precision | >= 85% | 搜索结果中相关信息的比例 |
| 召回率 Recall | >= 90% | 目标信息被检索到的比例 |
| F1-Score | >= 87% | 精确率和召回率的调和平均 |
| 操作节省率 | >= 50% | 记忆推荐减少的操作步骤比例 |
| 字符节省率 | >= 60% | 记忆推荐减少的输入字符比例 |
| 时间节省率 | >= 40% | 记忆推荐节省的时间比例 |
| 写入延迟 P50 | <= 200ms | 记忆写入操作的中位延迟 |
| 查询延迟 P50 | <= 300ms | 记忆查询操作的中位延迟 |

### 已知关键问题（来自 REVIEW_REPORT.md 和深度审查）

| 问题 | 严重度 | 状态 |
|------|--------|------|
| 评测代码只统计 pass/fail，未计算 Hit Rate/Precision/Recall/F1 | Critical | 未解决 |
| eval_report_generator.py 与 real_evaluation.py 输出格式不匹配 | Major | 未解决 |
| 评测使用 MiniStore 而非真实 SqliteStore | Critical | 部分解决 |
| 数据集数量不一致（实际262条 vs 方案240条） | Major | 未解决 |
| 数据集难度分布不符合方案（Easy占比不足30%） | Major | 未解决 |
| demo_cli.py 使用 DemoStore 而非真实系统 | Major | 未解决 |
| 效能指标（操作节省率/字符节省率/时间节省率）未被测量 | Critical | 未解决 |
| anti_interference 全部 recall=0.0 却标记为 pass | Critical | 未解决 |

---

## 任务1：飞书 CLI 集成分析

### 任务目标
分析如何让 MemScope 作为 OpenClaw/Hermes Agent 的记忆插件并作用于飞书 CLI，以符合赛题要求。

### 具体要求

**1.1 阅读和分析**
- 阅读 https://github.com/larksuite/cli 仓库，理解飞书 CLI 的架构和功能
- 分析飞书 CLI 与 Hermes Agent 的集成方式
- 理解 OpenClaw 框架的插件机制

**1.2 集成方案设计**
- 分析 MemScope 如何注册为 Hermes Agent 的 memory_provider
- 设计 MemScope 在飞书 CLI 环境中的工作流程
- 分析 `prefetch()` / `sync_turn()` / `on_session_end()` 生命周期在飞书 CLI 中的触发时机
- 设计 CLI 终端和飞书端自由切换的实现方案

**1.3 输出文档**
- 将分析结果写入 `docs/feishu_cli_integration.md`
- 文档应包含：
  - 飞书 CLI 架构概述
  - Hermes Agent 插件机制分析
  - MemScope 集成方案（含架构图描述）
  - CLI/飞书端切换方案
  - 关键接口和代码路径说明

### 验收标准
- [ ] 文档已创建并写入 `docs/feishu_cli_integration.md`
- [ ] 文档包含飞书 CLI 架构分析
- [ ] 文档包含 MemScope 集成方案
- [ ] 文档包含 CLI/飞书端切换方案
- [ ] 方案与现有 `plugin.yaml` 和 `src/__init__.py` 的接口兼容

---

## 任务2：项目代码全面审阅与问题修复

### 任务目标
在 REVIEW_REPORT.md 和任务1产出的飞书 CLI 分析文件指导下，审阅当前项目的架构代码、评估代码、评测数据集，明确记载已解决和未解决的问题，并解决未解决的问题。

### 具体要求

**2.1 架构代码审阅（src/ 目录）**

审阅以下文件，检查是否符合赛题要求和架构设计文档：
- `src/__init__.py` — MemScopeProvider 主入口
- `src/core/store.py` — SQLite 存储层
- `src/recall/engine.py` — 混合检索引擎
- `src/command_memory/` — 方向A 实现
- `src/decision_memory/` — 方向B 实现
- `src/preference_memory/` — 方向C 实现
- `src/knowledge_health/` — 方向D 实现
- `src/feishu/` — 飞书 API 集成
- `plugin.yaml` — 插件配置

检查要点：
- [ ] MemScopeProvider 是否正确实现了 memory_provider 接口
- [ ] 是否实现了 `prefetch()` / `sync_turn()` / `on_session_end()` 生命周期
- [ ] 是否通过 `ctx.register_memory_provider()` 注册
- [ ] plugin.yaml 是否正确声明了 hooks 和配置
- [ ] 飞书集成代码是否使用真实 API（非 mock）

**2.2 评估代码审阅（eval/ 目录）**

审阅以下文件：
- `eval/real_evaluation.py` — 核心评测脚本
- `eval/feishu_real_eval.py` — 飞书环境评测
- `eval/run_ablation.py` — 消融对比评测
- `eval/eval_report_generator.py` — 报告生成器
- `eval/schema_v2.py` — 数据库 schema

检查要点：
- [ ] 评测是否使用真实 SqliteStore 而非 MiniStore
- [ ] 每个评估函数是否返回 `failed_checks` 字段
- [ ] pass/fail 判定是否基于实际指标值
- [ ] 是否计算了 Hit Rate、Precision、Recall、F1 等具体指标
- [ ] 效能指标（操作节省率/字符节省率/时间节省率）是否被测量
- [ ] 报告生成器是否与评测脚本输出格式匹配
- [ ] 每次评测是否自动产出 JSON 和 Markdown 报告

**2.3 评测数据集审阅（eval/datasets/ 目录）**

审阅 8 个 JSON 数据集文件：
- [ ] 样本数量是否符合方案（每集30条，共240条）
- [ ] 难度分布是否符合方案（Easy 30% / Medium 50% / Hard 20%）
- [ ] expected 字段结构是否统一
- [ ] 样本 ID 命名是否统一
- [ ] 长时序样本是否覆盖 3个月-2年 时间跨度
- [ ] 样本是否独立（无事实关联）

**2.4 问题记录与修复**

在 `REVIEW_REPORT.md` 中更新：
- 标记已解决的问题（附解决方式）
- 标记仍未解决的问题
- 新增发现的问题

对未解决的问题进行修复，包括但不限于：
- 修复评测代码，使其计算具体指标而非只统计 pass/fail
- 修复评估函数的 `failed_checks` 逻辑
- 统一数据集数量为 240 条
- 修复数据集难度分布
- 修复 eval_report_generator.py 的格式匹配问题

### 验收标准
- [ ] REVIEW_REPORT.md 已更新，包含已解决/未解决状态
- [ ] 所有 Critical 级问题已修复
- [ ] 所有 Major 级问题已修复或有明确的修复方案
- [ ] 评测代码使用真实 SqliteStore
- [ ] 评测代码计算具体指标（Hit Rate/Precision/Recall/F1）
- [ ] 数据集数量统一为 240 条
- [ ] 数据集难度分布符合方案

---

## 任务3：评测代码全面运行与优化

### 任务目标
完成任务2后，全面运行整个项目的评测代码，根据评测结果和规定的评测指标及方案，分析评测代码是否有误、是否错误地将系统评测按照代码测试的方式进行，优化评测代码直到其符合规定的评测方案。

### 具体要求

**3.1 运行评测代码**
```bash
# 运行主评测脚本
python3 eval/real_evaluation.py

# 运行飞书环境评测
python3 eval/feishu_real_eval.py

# 运行消融对比评测
python3 eval/run_ablation.py
```

**3.2 评测结果分析**

检查评测结果是否符合以下要求：
- [ ] 评测结果包含具体指标（Hit Rate/Precision/Recall/F1），而非只有 pass/fail 统计
- [ ] 评测结果包含效能指标（操作节省率/字符节省率/时间节省率）
- [ ] 评测结果包含延迟指标（P50/P95/P99）
- [ ] 评测报告包含综合得分和评级（优秀/及格/不及格）
- [ ] 评测报告包含各维度得分和加权得分

**3.3 评测代码优化**

如果评测代码仍按"代码测试"方式进行（只统计 pass/fail），需要重构为"性能评估"方式：

每个评估函数应返回：
```python
{
    "hit_rate": float,  # 命中率
    "precision": float,  # 精确率
    "recall": float,  # 召回率
    "f1_score": float,  # F1-Score
    "passed_checks": list,  # 通过的检查项
    "failed_checks": list,  # 失败的检查项
    # ... 其他维度特定指标
}
```

主评测流程应计算：
```python
{
    "overall_hit_rate": float,  # 总体命中率
    "overall_precision": float,  # 总体精确率
    "overall_recall": float,  # 总体召回率
    "overall_f1": float,  # 总体 F1
    "dimension_scores": {  # 各维度得分
        "anti_interference": {"score": float, "weight": float, "weighted_score": float},
        ...
    },
    "efficiency_metrics": {  # 效能指标
        "write_latency_p50_ms": float,
        "query_latency_p50_ms": float,
        "operation_saving_rate": float,
        "character_saving_rate": float,
        "time_saving_rate": float
    }
}
```

**3.4 评测报告生成**

确保 `eval/eval_report_generator.py` 能正确读取评测结果并生成 Markdown 报告，报告应包含：
- 执行摘要（总分、评级）
- 各维度得分（含加权得分）
- 核心指标详情（Hit Rate/Precision/Recall/F1）
- 效能指标详情
- 基准对标（与 LongMemEval/LOCOMO 对比）
- 改进建议

### 验收标准
- [ ] 评测代码运行成功，无报错
- [ ] 评测结果包含具体指标（Hit Rate/Precision/Recall/F1）
- [ ] 评测结果包含效能指标
- [ ] 评测报告自动生成（JSON + Markdown）
- [ ] 报告格式符合 evaluation_scheme_v2.md 的规范
- [ ] 综合得分基于维度加权计算

---

## 任务4：Demo 脚本审阅与修复

### 任务目标
运行 demo 文件夹里的代码，分析其是否实现了赛题的对应要求，如果没有，需要改正。

### 具体要求

**4.1 运行 Demo 脚本**
```bash
# CLI 演示
python3 demo/demo_cli.py

# 飞书 API 演示
python3 demo/demo_feishu.py
```

**4.2 审阅要点**

检查 demo 脚本是否满足以下赛题要求：

**demo_cli.py**:
- [ ] 是否使用真实 MemScope 系统（SqliteStore + 四大方向模块）
- [ ] 是否演示了方向A（CLI命令记忆）的完整流程
- [ ] 是否演示了方向C（个人偏好记忆）的完整流程
- [ ] 是否演示了方向D（团队知识健康）的完整流程
- [ ] 演示结果是否与真实系统行为一致

**demo_feishu.py**:
- [ ] 是否使用真实飞书 API（非模拟）
- [ ] 是否演示了方向B（飞书决策记忆）的完整流程
- [ ] 是否演示了飞书消息 → 记忆提取 → 存储 → 检索 → 推送的完整流程
- [ ] 是否支持 CLI 终端和飞书端自由切换
- [ ] 是否有飞书互动卡片推送（决策卡片、知识健康预警）

**4.3 问题修复**

如果 demo 脚本不满足要求，需要修复：

**demo_cli.py 修复**:
- 将 DemoStore 替换为真实 SqliteStore
- 使用真实的 command_memory、preference_memory、knowledge_health 模块
- 确保演示结果与真实系统一致

**demo_feishu.py 修复**:
- 确保真实 API 调用代码可用（非注释状态）
- 实现 CLI/飞书端切换机制
- 实现飞书互动卡片推送

### 验收标准
- [ ] demo_cli.py 使用真实 MemScope 系统
- [ ] demo_cli.py 演示了方向A/C/D 的完整流程
- [ ] demo_feishu.py 使用真实飞书 API（当环境变量存在时）
- [ ] demo_feishu.py 演示了方向B 的完整流程
- [ ] demo 脚本支持 CLI/飞书端切换
- [ ] demo 脚本运行成功，输出符合预期

---

## 任务5：MemScope 性能优化

### 任务目标
根据评测结果，优化现有 MemScope 代码，提升其在评测指标上的性能。

### 具体要求

**5.1 分析评测结果**

分析任务3产出的评测报告，识别性能瓶颈：
- 哪些维度得分低于目标值？
- 哪些指标未达标？
- 性能瓶颈在哪个环节（提取/存储/检索/更新）？

**5.2 针对性优化**

根据评测结果，针对不同维度进行优化：

**方向A（CLI命令记忆）优化**:
- 优化命令模式识别算法
- 优化上下文感知推荐算法
- 提升字符节省率

**方向B（飞书决策记忆）优化**:
- 优化决策提取算法（中英文）
- 优化决策卡片推送相关性
- 提升命中率和精确率

**方向C（个人偏好记忆）优化**:
- 优化偏好提取算法（显式+隐式）
- 优化偏好冲突解决机制
- 提升偏好准确率

**方向D（团队知识健康）优化**:
- 优化遗忘曲线模型参数
- 优化知识缺口检测算法
- 提升预警及时性

**检索引擎优化**:
- 优化 FTS5 全文搜索（CJK 分词）
- 优化向量检索
- 优化 RRF 融合和 MMR 重排
- 提升查询延迟

**5.3 优化验证**

每次优化后重新运行评测，验证优化效果：
```bash
python3 eval/real_evaluation.py
```

对比优化前后的指标变化，确保：
- 核心指标（Hit Rate/Precision/Recall/F1）有所提升
- 效能指标（延迟）未退化
- 综合得分有所提升

### 验收标准
- [ ] 识别了性能瓶颈和优化方向
- [ ] 针对性优化了低分维度
- [ ] 优化后重新运行评测
- [ ] 核心指标有所提升
- [ ] 效能指标未退化
- [ ] 综合得分有所提升

---

## 任务6：对抗优化循环（核心任务）

### 任务目标
建立"代码优化 → 性能评测 → 结果分析 → 方案设计 → GitHub 推送"的闭环循环，通过对抗优化方式持续提升 MemScope 性能。**循环不少于 10 轮**。

### 核心理念

**对抗优化**：每轮循环不仅要提升 MemScope 自身性能，也要提升评测任务难度。通过"矛与盾"的对抗式迭代，推动系统能力持续提升。

```
┌─────────────────────────────────────────────────────────────────┐
│                    对抗优化循环（每轮）                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ 代码优化  │ →  │ 性能评测  │ →  │ 结果分析  │ →  │ 方案设计  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       ↑                                              │         │
│       │              ┌──────────┐                    │         │
│       │              │ GitHub   │ ←──────────────────┘         │
│       │              │ 推送更新  │                              │
│       │              └──────────┘                              │
│       │                     │                                  │
│       └─────────────────────┘                                  │
│                                                                 │
│  同步进行：提升评测难度（增加噪声、增加干扰、增加时序跨度等）      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 具体要求

**6.1 评测结果存储规范**

每次评测的结果必须存放到带时间戳的文件夹中，便于回顾历史评测结果：

```
eval/history/
├── 2026-05-05_143022/          # 评测时间戳文件夹
│   ├── eval_results.json       # 评测结果 JSON
│   ├── eval_report.md          # 评测报告 Markdown
│   ├── run_log.txt             # 运行日志
│   ├── trace_data.json         # 运行轨迹数据（含每个样本的执行详情）
│   └── dataset_snapshot/       # 当前数据集快照
│       ├── anti_interference.json
│       ├── contradiction_update.json
│       └── ...
├── 2026-05-05_180530/
│   └── ...
└── latest -> 2026-05-05_180530/  # 符号链接到最新评测
```

**评测脚本需支持**：
```bash
# 运行评测并自动创建时间戳文件夹
python3 eval/real_evaluation.py --save-history

# 输出示例：
# 评测结果已保存到: eval/history/2026-05-05_143022/
# 评测报告已生成: eval/history/2026-05-05_143022/eval_report.md
```

**trace_data.json 格式**：
```json
{
    "evaluation_id": "eval-20260505-143022",
    "timestamp": "2026-05-05T14:30:22Z",
    "system_version": "MemScope v2.3.0",
    "total_cases": 240,
    "overall_metrics": {
        "hit_rate": 0.82,
        "precision": 0.78,
        "recall": 0.85,
        "f1_score": 0.81,
        "overall_score": 76.5,
        "grade": "及格"
    },
    "dimension_scores": {...},
    "efficiency_metrics": {...},
    "case_traces": [
        {
            "test_id": "anti_interference_001",
            "setup_actions": ["insert_conversation(target)", "insert_conversation(noise_1)", ...],
            "query_action": "search_chunks(query)",
            "search_results": [...],
            "metrics": {
                "hit_rate": 1.0,
                "precision": 0.75,
                "recall": 1.0,
                "f1_score": 0.86
            },
            "latency_ms": 12.5,
            "status": "pass"
        },
        ...
    ]
}
```

**6.2 单轮循环流程**

每轮循环包含以下步骤：

**步骤1：代码优化**
- 分析上一轮评测结果（第一轮则分析任务3的结果）
- 识别性能瓶颈和优化方向
- 实施代码优化
- 优化内容包括：
  - MemScope 核心代码优化（src/）
  - 评测代码优化（eval/）
  - 评测数据集优化（eval/datasets/）

**步骤2：性能评测**
```bash
python3 eval/real_evaluation.py --save-history
```
- 运行全量评测（240条样本）
- 评测结果自动保存到 `eval/history/{timestamp}/`
- 确保评测结果包含具体指标（Hit Rate/Precision/Recall/F1）

**步骤3：结果分析与方案设计**
- 分析评测结果 JSON 和 trace_data.json
- 对比历史评测结果，识别改进和退步
- 分析失败样本的 trace，找出失败原因
- 设计下一轮优化方案
- 优化方案应包含：
  - 优化目标（具体指标和目标值）
  - 优化策略（具体代码修改方案）
  - 预期效果

**步骤4：README 更新与 GitHub 推送**
- 更新 README.md：
  - 更新日志（新增本轮优化记录）
  - 更新评测结果（使用最新评测数据）
  - 更新优化进展
- 推送到 GitHub：
```bash
cd ~/MemScope
git add -A
git commit -m "优化轮次 N: [优化内容摘要]"
git push origin main
```

**步骤5：评测难度提升**
- 根据当前评测结果，提升评测难度：
  - **抗干扰测试**：增加噪声数量、提高噪声相似度
  - **矛盾更新测试**：增加矛盾复杂度、增加多实体并发
  - **效能测试**：增加并发量、增加数据量
  - **命令记忆**：增加用户数、增加命令复杂度
  - **决策记忆**：增加决策信号词变体、增加多语言混合
  - **偏好记忆**：增加隐式偏好场景、增加偏好冲突
  - **知识健康**：增加知识领域、增加时间跨度
  - **长时序记忆**：增加时间跨度到2年、增加干扰项

**难度提升策略**：
```python
# 每轮循环后，根据评测结果调整数据集难度
def upgrade_dataset_difficulty(current_results, round_number):
    """
    根据当前评测结果和轮次，提升数据集难度
    
    策略：
    1. 对于得分 > 90% 的维度：大幅增加难度
    2. 对于得分 70-90% 的维度：适度增加难度
    3. 对于得分 < 70% 的维度：保持或微调难度
    """
    for dimension in dimensions:
        score = current_results[dimension]["score"]
        if score > 90:
            # 大幅增加难度：增加噪声、增加干扰、增加复杂度
            add_hard_samples(dimension, count=5)
            increase_noise_level(dimension, factor=2)
        elif score > 70:
            # 适度增加难度
            add_medium_samples(dimension, count=3)
            increase_noise_level(dimension, factor=1.5)
        else:
            # 保持或微调
            pass
```

**6.3 循环执行要求**

**循环次数**：不少于 10 轮

**每轮产出**：
1. 代码优化提交（git commit）
2. 评测结果文件夹（`eval/history/{timestamp}/`）
3. 优化方案文档（追加到 `docs/optimization_history.md`）
4. README 更新
5. GitHub 推送

**循环终止条件**（满足任一即可）：
- 达到 10 轮循环
- 所有核心指标均达到目标值（Hit Rate >= 85%, Precision >= 85%, Recall >= 90%, F1 >= 87%）
- 综合得分连续 3 轮无显著提升（< 1%）

**6.4 优化历史文档**

创建 `docs/optimization_history.md`，记录每轮优化：

```markdown
# MemScope 优化历史

## 第 1 轮优化（2026-05-05）

### 评测结果
- 综合得分：65.3 / 100
- Hit Rate: 72%
- Precision: 68%
- Recall: 75%
- F1: 71%

### 优化内容
- 修复评测代码，计算具体指标
- 替换 MiniStore 为真实 SqliteStore

### 失败分析
- anti_interference: 搜索结果为空，FTS5 索引未同步
- decision_memory: 决策提取遗漏中文信号词

### 下轮优化方案
- 修复 FTS5 索引同步问题
- 优化决策提取的中文信号词列表

### 评测难度调整
- 抗干扰测试：噪声数量从 4 条增加到 8 条

---

## 第 2 轮优化（2026-05-06）
...
```

### 验收标准

**每轮循环验收**：
- [ ] 代码优化已提交（git commit）
- [ ] 评测结果已保存到 `eval/history/{timestamp}/`
- [ ] 评测结果包含具体指标（Hit Rate/Precision/Recall/F1）
- [ ] 优化方案已记录到 `docs/optimization_history.md`
- [ ] README 已更新
- [ ] GitHub 已推送
- [ ] 评测难度已提升（数据集有变化）

**整体循环验收**：
- [ ] 完成不少于 10 轮循环
- [ ] 每轮评测结果可追溯（`eval/history/` 文件夹完整）
- [ ] 核心指标有显著提升
- [ ] 评测难度有显著提升
- [ ] 优化历史文档完整

---

## 执行顺序

```
任务1（飞书CLI分析）→ 任务2（审阅与修复）→ 任务3（评测运行与优化）→ 任务4（Demo修复）→ 任务5（性能优化）→ 任务6（对抗优化循环 × 10轮）
```

**注意**：
- 任务1 和任务2 可以部分并行
- 任务3 依赖任务2 的修复结果
- 任务4 依赖任务2 的架构修复
- 任务5 依赖任务3 的评测结果
- 任务6 依赖任务5 的初始优化，然后进入循环

---

## 交付物清单

| 任务 | 交付物 | 路径 |
|------|--------|------|
| 任务1 | 飞书 CLI 集成分析文档 | `docs/feishu_cli_integration.md` |
| 任务2 | 更新后的审查报告 | `REVIEW_REPORT.md` |
| 任务2 | 修复后的评测代码 | `eval/*.py` |
| 任务2 | 修复后的评测数据集 | `eval/datasets/*.json` |
| 任务3 | 评测结果 JSON | `eval/real_eval_results.json` |
| 任务3 | 评测报告 Markdown | `eval/eval_report.md` |
| 任务4 | 修复后的 Demo 脚本 | `demo/*.py` |
| 任务5 | 优化后的核心代码 | `src/**/*.py` |
| 任务5 | 优化后的评测结果 | `eval/real_eval_results.json` |
| **任务6** | **评测历史文件夹** | **`eval/history/{timestamp}/`** |
| **任务6** | **优化历史文档** | **`docs/optimization_history.md`** |
| **任务6** | **最终优化后的代码** | **`src/**/*.py`** |
| **任务6** | **最终评测数据集** | **`eval/datasets/*.json`** |
| **任务6** | **README 更新记录** | **`README.md`** |

---

## 关键约束

1. **性能评估 ≠ 代码测试**：评测代码必须计算具体指标（Hit Rate/Precision/Recall/F1），而非只统计 pass/fail
2. **数据真实性**：所有对外展示的数字必须有实际运行记录可追溯，禁止编造
3. **全量评测**：必须运行全部 240 条样本，不得选取部分
4. **独立执行**：每个样本使用独立的存储实例，避免数据污染
5. **真实系统**：评测必须使用真实 MemScope 系统（SqliteStore），而非 mock/简化实现
6. **文件清理**：每次优化必须删除冗余无用文件，不堆积无用文件到项目中
7. **README 同步**：每次优化必须更新 README，确保与代码实际情况一致
8. **对抗优化**：每轮循环不仅要提升系统性能，也要提升评测难度
9. **历史可追溯**：所有评测结果必须保存到 `eval/history/` 文件夹，支持历史回溯
10. **Git 记录**：每轮优化必须有 git commit，commit message 包含优化内容摘要

---

## 评测难度提升参考

### 各维度难度提升策略

| 维度 | 当前难度 | 提升策略 |
|------|----------|----------|
| 抗干扰 | 4条噪声 | 增加到 8/16/32 条噪声，提高噪声相似度 |
| 矛盾更新 | 直接覆盖 | 增加部分更新、时间线矛盾、多实体并发 |
| 效率 | 基础延迟测试 | 增加并发量、增加数据量级 |
| 命令记忆 | 单用户 | 增加多用户交叉、增加命令复杂度 |
| 决策记忆 | 基础信号词 | 增加信号词变体、增加多语言混合 |
| 偏好记忆 | 显式偏好 | 增加隐式偏好、增加偏好冲突 |
| 知识健康 | 基础新鲜度 | 增加知识领域、增加时间跨度 |
| 长时序 | 3-6个月 | 扩展到 1年、2年，增加干扰项 |

### 难度提升量化目标

| 轮次 | 噪声数量 | 时间跨度 | 用户数 | 领域数 |
|------|----------|----------|--------|--------|
| 1-3  | 4-8 条   | 6个月    | 2-3    | 5      |
| 4-6  | 8-16 条  | 1年      | 3-5    | 8      |
| 7-10 | 16-32 条 | 2年      | 5-10   | 10     |
