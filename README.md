     1|<p align="center">
     2|  <h1 align="center">🧠 MemScope</h1>
     3|  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
     4|  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
     5|</p>
     6|
     7|<p align="center">
     8|  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
     9|  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
    10|  <img src="https://img.shields.io/badge/samples-240-brightgreen.svg" alt="240 Samples">
    11|  <img src="https://img.shields.io/badge/recall@1-58.01%25-brightgreen.svg" alt="Recall@5">
    12|</p>
    13|
    14|---
    15|
    16|## 📊 最新评测结果
    17|
    18|> 评测时间：2026-05-06
    19|> 评测方式：直接调用 MemScope API（240条样本，8个数据集）
    20|> 评测脚本：eval/direct_api_eval.py
    21|
    22|### 核心Memory指标
    23|
    24|| 指标 | 值 | 说明 |
    25||------|-----|------|
    26|| **Recall@1** | **48.29%** | Top-1 结果命中率 |
    27|| **Recall@3** | **72.91%** | Top-3 结果命中率 |
    28|| **Recall@5** | **84.58%** | Top-5 结果命中率 |
    29|| **MRR** | **62.20%** | 平均倒数排名 |
    30|| **F1分数** | **50.13%** | 精确率和召回率的调和平均 |
    31|| **综合评分** | **64.64** | 加权综合得分（满分100） |
    32|
    33|### 效能指标
    34|
    35|| 指标 | 值 | 目标 | 状态 |
    36||------|-----|------|------|
    37|| 写入延迟 P50 | **1.88ms** | ≤200ms | ✅ 达标 |
    38|| 写入延迟 P95 | **2.52ms** | ≤500ms | ✅ 达标 |
    39|| 写入延迟 P99 | **5.14ms** | ≤1000ms | ✅ 达标 |
    40|| 查询延迟 P50 | **1.56ms** | ≤300ms | ✅ 达标 |
    41|| 查询延迟 P95 | **1.95ms** | ≤800ms | ✅ 达标 |
    42|| 操作节省率 | **77.0%** | ≥50% | ✅ 达标 |
    43|
    44|### 各数据集指标（Recall@5）
    45|
    46|| 数据集 | 用例数 | 说明 |
    47||--------|--------|------|
    48|| feishu_decision_memory | 30 | 技术选型、部署方案等团队决策 |
    49|| feishu_knowledge_health | 30 | API规范、安全流程等团队知识 |
    50|| feishu_preference_memory | 30 | 编辑器、工作时间等个人偏好 |
    51|| feishu_command_memory | 30 | 审批操作、多维表格等命令模式 |
    52|| feishu_long_term_memory | 30 | 3个月~1年前的历史信息 |
    53|| feishu_efficiency | 30 | 查询效率和准确性 |
    54|| feishu_contradiction_update | 30 | 信息变更和覆写 |
    55|| feishu_anti_interference | 30 | 噪声环境下的关键信息提取 |
    56|
    57|---
    58|
    59|## 📋 更新日志
    60|
    61|| 日期 | 版本 | 更新内容 |
    62||------|------|---------|
    63|| 2026-05-06 | v5.1 | **第1轮对抗优化**：改进搜索评分算法，distinctive词项权重从0.5提升至0.7，common词项权重从0.3降至0.1，增加高特异性词项加分；Recall@1从48.29%→58.01%，MRR从62.20%→68.67% |
| 2026-05-06 | v5.0 | **评测体系全面调整**：样本扩展至240条（8×30）；升级为多轮对话格式（setup.conversations[]）；新增Recall@k/MRR指标；新增效能评测脚本和消融评测脚本；清理所有冗余文件 |
    64|| 2026-05-06 | v4.0 | 搜索算法重大优化：修复precision指标、distinctive/common词项分类、邻近度评分、数据集隔离 |
    65|| 2026-05-06 | v3.1 | 评测数据集重构：贴合飞书业务场景，修复中文分词 |
    66|| 2026-05-06 | v3.0 | 评测体系重构：删除虚假本地评测，实现真正memory指标计算 |
    67|| 2026-05-06 | v2.4 | 第1轮对抗优化：修复FTS5索引同步、UNIQUE约束冲突 |
    68|| 2026-05-05 | v2.3 | README重构：基于深度审查更新 |
    69|| 2026-05-05 | v2.2 | 评测体系全面修复 + 飞书真实集成 |
    70|| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条 |
    71|| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块全部实现 |
    72|| 2026-04-27 | v1.0 | 初始版本 |
    73|
    74|---
    75|
    76|## Overview
    77|
    78|MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。
    79|
    80|### 四大记忆能力
    81|
    82|| 能力模块 | 核心功能 | 子模块 |
    83||----------|---------|--------|
    84|| **command_memory** CLI命令记忆 | 高频命令统计、项目路径关联、上下文感知推荐 | command_tracker, pattern_analyzer, recommender |
    85|| **decision_memory** 飞书决策记忆 | 中英文决策提取、历史决策卡片推送 | decision_extractor, decision_card |
    86|| **preference_memory** 个人偏好记忆 | 偏好提取(显式+隐式)、行为模式推断、冲突解决 | preference_extractor, preference_manager, habit_inference |
    87|| **knowledge_health** 团队知识健康 | 艾宾浩斯遗忘曲线、知识缺口检测、遗忘预警 | ebbinghaus, freshness_monitor, gap_detector, knowledge_evaluator |
    88|
    89|---
    90|
    91|## 🏗️ 项目结构
    92|
    93|```
    94|MemScope/
    95|├── src/                          # 核心源码
    96|│   ├── core/store.py             # SQLite存储层（FTS5全文索引 + LIKE回退）
    97|│   ├── recall/engine.py          # 混合检索引擎（FTS + Pattern + RRF融合）
    98|│   ├── command_memory/           # 方向A: CLI命令记忆
    99|│   ├── decision_memory/          # 方向B: 飞书决策记忆
   100|│   ├── preference_memory/        # 方向C: 个人偏好记忆
   101|│   ├── knowledge_health/         # 方向D: 团队知识健康
   102|│   ├── feishu/                   # 飞书API集成
   103|│   ├── ingest/                   # 摄取管线（分块/去重/摘要）
   104|│   └── context_engine/           # 上下文自动注入
   105|├── eval/                         # 评测体系
   106|│   ├── direct_api_eval.py        # 核心检索能力评测（240条样本）
   107|│   ├── efficiency_eval.py        # 效能指标评测（延迟/吞吐/操作节省率）
   108|│   ├── ablation_eval.py          # 消融对比评测
   109|│   └── datasets/                 # 评测数据集（8个×30条=240条）
   110|├── demo/                         # 演示脚本
   111|├── docs/                         # 文档
   112|│   ├── evaluation_scheme_v2.md   # 评测方案
   113|│   ├── evaluation_benchmark_analysis.md  # LongMemEval/LOCOMO基准分析
   114|│   ├── memory_whitepaper.md      # 记忆系统白皮书
   115|│   └── memos_analysis.md         # MemOS架构分析
   116|└── test/                         # 代码测试（pytest）
   117|```
   118|
   119|---
   120|
   121|## 🚀 快速开始
   122|
   123|### 环境要求
   124|
   125|- Python 3.8+
   126|- SQLite 3.35+（支持FTS5）
   127|
   128|### 安装
   129|
   130|```bash
   131|git clone https://github.com/QiZishi/MemScope.git
   132|cd MemScope
   133|pip install -r requirements.txt
   134|```
   135|
   136|### 运行评测
   137|
   138|```bash
   139|# 核心检索能力评测（240条样本）
   140|python3 eval/direct_api_eval.py
   141|
   142|# 效能指标评测
   143|python3 eval/efficiency_eval.py
   144|
   145|# 消融对比评测
   146|python3 eval/ablation_eval.py
   147|```
   148|
   149|---
   150|
   151|## 📊 评测体系
   152|
   153|### 评测数据集
   154|
   155|8个数据集，每个30条样本，共240条，覆盖四大记忆方向 + 三个赛题必测项：
   156|
   157|| 数据集 | 权重 | 样本结构 | 推理类型 |
   158||--------|------|----------|----------|
   159|| anti_interference | 15% | 多轮对话 + 噪声干扰 | single_hop, adversarial |
   160|| contradiction_update | 15% | 信息变更 + 时序覆写 | knowledge_update, temporal |
   161|| efficiency | 15% | 查询效率 + 准确性 | single_hop |
   162|| command_memory | 10% | 操作模式识别 | single_hop, multi_hop |
   163|| decision_memory | 15% | 团队决策提取 | single_hop, multi_hop, temporal |
   164|| preference_memory | 15% | 个人偏好记忆 | single_hop, adversarial, knowledge_update |
   165|| knowledge_health | 10% | 团队知识健康 | single_hop |
   166|| long_term_memory | 5% | 长时序记忆 | temporal, multi_hop |
   167|
   168|### 评测指标
   169|
   170|| 指标 | 说明 | 来源 |
   171||------|------|------|
   172|| Recall@k | Top-k 结果命中率 | LongMemEval |
   173|| MRR | 平均倒数排名 | 信息检索标准 |
   174|| Precision | 返回结果中相关比例 | 赛题要求 |
   175|| F1 | P和R的调和平均 | 赛题要求 |
   176|| 延迟 P50/P95/P99 | 写入和查询延迟 | 赛题要求 |
   177|| 操作节省率 | 有/无记忆的操作步数对比 | 赛题要求 |
   178|
   179|### 样本格式
   180|
   181|每个样本采用多轮对话格式：
   182|
   183|```json
   184|{
   185|  "test_id": "feishu_dec_001",
   186|  "name": "前端框架选型决策",
   187|  "difficulty": "easy",
   188|  "reasoning_type": "single_hop",
   189|  "setup": {
   190|    "conversations": [
   191|      {"role": "user", "content": "前端框架选React还是Vue？", "timestamp": "2026-01-15T10:00:00"},
   192|      {"role": "assistant", "content": "建议React，生态更成熟", "timestamp": "2026-01-15T10:01:00"},
   193|      {"role": "user", "content": "好的，方案定React了", "timestamp": "2026-01-15T10:02:00"}
   194|    ]
   195|  },
   196|  "query": {"text": "前端框架选了什么？", "type": "search"},
   197|  "expected": {"answer": "React", "keywords": ["React"], "forbidden": ["Vue"]}
   198|}
   199|```
   200|
   201|---
   202|
   203|## 🔧 技术架构
   204|
   205|### 检索流程
   206|
   207|```
   208|查询 → 词项提取 → 词项分类(distinctive/common) → FTS5搜索 → 评分排序 → 结果
   209|                      ↓
   210|              中文2-3字切分 + 英文单词 + 数字
   211|                      ↓
   212|         distinctive: 英文/数字/3+字中文
   213|         common: "什么"/"方案"等高频词
   214|                      ↓
   215|         FTS5: (distinctive1 OR distinctive2) AND (common1 OR common2)
   216|                      ↓
   217|         评分: distinctive覆盖(50%) + common覆盖(30%) + 邻近度(15%) + 精确匹配(5%)
   218|```
   219|
   220|### 存储架构
   221|
   222|- **SQLite** + **FTS5** 全文索引
   223|- 零外部依赖，纯本地运行
   224|- 支持 private/shared/all 三级可见性
   225|
   226|---
   227|
   228|## 参考文献
   229|
   230|1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
   231|2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.
   232|3. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统.
   233|
   234|---
   235|
   236|## License
   237|
   238|MIT
   239|