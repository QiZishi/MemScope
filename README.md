     1|     1|<p align="center">
     2|     2|  <h1 align="center">🧠 MemScope</h1>
     3|     3|  <p align="center"><b>Enterprise-level Long-term Collaboration Memory System</b></p>
     4|     4|  <p align="center">企业级长周期协作记忆引擎 — 飞书 OpenClaw 大赛参赛作品</p>
     5|     5|</p>
     6|     6|
     7|     7|<p align="center">
     8|     8|  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
     9|     9|  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
    10|    10|  <img src="https://img.shields.io/badge/samples-240-brightgreen.svg" alt="240 Samples">
    11|    11|  <img src="https://img.shields.io/badge/recall@1-58.01%25-brightgreen.svg" alt="Recall@5">
    12|    12|</p>
    13|    13|
    14|    14|---
    15|    15|
    16|    16|## 📊 最新评测结果
    17|    17|
    18|    18|> 评测时间：2026-05-06
    19|    19|> 评测方式：直接调用 MemScope API（240条样本，8个数据集）
    20|    20|> 评测脚本：eval/direct_api_eval.py
    21|    21|
    22|    22|### 核心Memory指标
    23|    23|
    24|    24|| 指标 | 值 | 说明 |
    25|    25||------|-----|------|
    26|    26|| **Recall@1** | **48.29%** | Top-1 结果命中率 |
    27|    27|| **Recall@3** | **72.91%** | Top-3 结果命中率 |
    28|    28|| **Recall@5** | **84.58%** | Top-5 结果命中率 |
    29|    29|| **MRR** | **62.20%** | 平均倒数排名 |
    30|    30|| **F1分数** | **50.13%** | 精确率和召回率的调和平均 |
    31|    31|| **综合评分** | **64.64** | 加权综合得分（满分100） |
    32|    32|
    33|    33|### 效能指标
    34|    34|
    35|    35|| 指标 | 值 | 目标 | 状态 |
    36|    36||------|-----|------|------|
    37|    37|| 写入延迟 P50 | **1.88ms** | ≤200ms | ✅ 达标 |
    38|    38|| 写入延迟 P95 | **2.52ms** | ≤500ms | ✅ 达标 |
    39|    39|| 写入延迟 P99 | **5.14ms** | ≤1000ms | ✅ 达标 |
    40|    40|| 查询延迟 P50 | **1.56ms** | ≤300ms | ✅ 达标 |
    41|    41|| 查询延迟 P95 | **1.95ms** | ≤800ms | ✅ 达标 |
    42|    42|| 操作节省率 | **77.0%** | ≥50% | ✅ 达标 |
    43|    43|
    44|    44|### 各数据集指标（Recall@5）
    45|    45|
    46|    46|| 数据集 | 用例数 | 说明 |
    47|    47||--------|--------|------|
    48|    48|| feishu_decision_memory | 30 | 技术选型、部署方案等团队决策 |
    49|    49|| feishu_knowledge_health | 30 | API规范、安全流程等团队知识 |
    50|    50|| feishu_preference_memory | 30 | 编辑器、工作时间等个人偏好 |
    51|    51|| feishu_command_memory | 30 | 审批操作、多维表格等命令模式 |
    52|    52|| feishu_long_term_memory | 30 | 3个月~1年前的历史信息 |
    53|    53|| feishu_efficiency | 30 | 查询效率和准确性 |
    54|    54|| feishu_contradiction_update | 30 | 信息变更和覆写 |
    55|    55|| feishu_anti_interference | 30 | 噪声环境下的关键信息提取 |
    56|    56|
    57|    57|---
    58|    58|
    59|    59|## 📋 更新日志
    60|    60|
    61|    61|| 日期 | 版本 | 更新内容 |
    62|    62||------|------|---------|
    63|    63|| 2026-05-06 | v5.2 | **第2轮对抗优化**：新增memory生命周期评测脚本（memory_lifecycle_eval.py），测试决策/偏好/知识的创建→更新→检索→矛盾解决全流程；实现记忆时间衰减机制（search_chunks中增加createdAt衰减因子，半衰期7天，生产环境启用）；验证memory CRUD能力100%通过 |
| 2026-05-06 | v5.1 | **第1轮对抗优化**：改进搜索评分算法，distinctive词项权重从0.5提升至0.7，common词项权重从0.3降至0.1，增加高特异性词项加分；Recall@1从48.29%→58.01%，MRR从62.20%→68.67% |
    64|| 2026-05-06 | v5.0 | **评测体系全面调整**：样本扩展至240条（8×30）；升级为多轮对话格式（setup.conversations[]）；新增Recall@k/MRR指标；新增效能评测脚本和消融评测脚本；清理所有冗余文件 |
    65|    64|| 2026-05-06 | v4.0 | 搜索算法重大优化：修复precision指标、distinctive/common词项分类、邻近度评分、数据集隔离 |
    66|    65|| 2026-05-06 | v3.1 | 评测数据集重构：贴合飞书业务场景，修复中文分词 |
    67|    66|| 2026-05-06 | v3.0 | 评测体系重构：删除虚假本地评测，实现真正memory指标计算 |
    68|    67|| 2026-05-06 | v2.4 | 第1轮对抗优化：修复FTS5索引同步、UNIQUE约束冲突 |
    69|    68|| 2026-05-05 | v2.3 | README重构：基于深度审查更新 |
    70|    69|| 2026-05-05 | v2.2 | 评测体系全面修复 + 飞书真实集成 |
    71|    70|| 2026-04-29 | v2.1 | 评测体系重构：8个数据集扩展至240条 |
    72|    71|| 2026-04-28 | v2.0 | MemScope v2.0 完成：四大记忆模块全部实现 |
    73|    72|| 2026-04-27 | v1.0 | 初始版本 |
    74|    73|
    75|    74|---
    76|    75|
    77|    76|## Overview
    78|    77|
    79|    78|MemScope 是一个面向企业场景的 AI Agent 长周期协作记忆引擎，基于 [memos-local-hermes-plugin](https://github.com/damxin/memos-local-hermes-plugin) 二次开发，作为 Hermes Agent 的插件运行。
    80|    79|
    81|    80|### 四大记忆能力
    82|    81|
    83|    82|| 能力模块 | 核心功能 | 子模块 |
    84|    83||----------|---------|--------|
    85|    84|| **command_memory** CLI命令记忆 | 高频命令统计、项目路径关联、上下文感知推荐 | command_tracker, pattern_analyzer, recommender |
    86|    85|| **decision_memory** 飞书决策记忆 | 中英文决策提取、历史决策卡片推送 | decision_extractor, decision_card |
    87|    86|| **preference_memory** 个人偏好记忆 | 偏好提取(显式+隐式)、行为模式推断、冲突解决 | preference_extractor, preference_manager, habit_inference |
    88|    87|| **knowledge_health** 团队知识健康 | 艾宾浩斯遗忘曲线、知识缺口检测、遗忘预警 | ebbinghaus, freshness_monitor, gap_detector, knowledge_evaluator |
    89|    88|
    90|    89|---
    91|    90|
    92|    91|## 🏗️ 项目结构
    93|    92|
    94|    93|```
    95|    94|MemScope/
    96|    95|├── src/                          # 核心源码
    97|    96|│   ├── core/store.py             # SQLite存储层（FTS5全文索引 + LIKE回退）
    98|    97|│   ├── recall/engine.py          # 混合检索引擎（FTS + Pattern + RRF融合）
    99|    98|│   ├── command_memory/           # 方向A: CLI命令记忆
   100|    99|│   ├── decision_memory/          # 方向B: 飞书决策记忆
   101|   100|│   ├── preference_memory/        # 方向C: 个人偏好记忆
   102|   101|│   ├── knowledge_health/         # 方向D: 团队知识健康
   103|   102|│   ├── feishu/                   # 飞书API集成
   104|   103|│   ├── ingest/                   # 摄取管线（分块/去重/摘要）
   105|   104|│   └── context_engine/           # 上下文自动注入
   106|   105|├── eval/                         # 评测体系
   107|   106|│   ├── direct_api_eval.py        # 核心检索能力评测（240条样本）
   108|   107|│   ├── efficiency_eval.py        # 效能指标评测（延迟/吞吐/操作节省率）
   109|   108|│   ├── ablation_eval.py          # 消融对比评测
   110|   109|│   └── datasets/                 # 评测数据集（8个×30条=240条）
   111|   110|├── demo/                         # 演示脚本
   112|   111|├── docs/                         # 文档
   113|   112|│   ├── evaluation_scheme_v2.md   # 评测方案
   114|   113|│   ├── evaluation_benchmark_analysis.md  # LongMemEval/LOCOMO基准分析
   115|   114|│   ├── memory_whitepaper.md      # 记忆系统白皮书
   116|   115|│   └── memos_analysis.md         # MemOS架构分析
   117|   116|└── test/                         # 代码测试（pytest）
   118|   117|```
   119|   118|
   120|   119|---
   121|   120|
   122|   121|## 🚀 快速开始
   123|   122|
   124|   123|### 环境要求
   125|   124|
   126|   125|- Python 3.8+
   127|   126|- SQLite 3.35+（支持FTS5）
   128|   127|
   129|   128|### 安装
   130|   129|
   131|   130|```bash
   132|   131|git clone https://github.com/QiZishi/MemScope.git
   133|   132|cd MemScope
   134|   133|pip install -r requirements.txt
   135|   134|```
   136|   135|
   137|   136|### 运行评测
   138|   137|
   139|   138|```bash
   140|   139|# 核心检索能力评测（240条样本）
   141|   140|python3 eval/direct_api_eval.py
   142|   141|
   143|   142|# 效能指标评测
   144|   143|python3 eval/efficiency_eval.py
   145|   144|
   146|   145|# 消融对比评测
   147|   146|python3 eval/ablation_eval.py
   148|   147|```
   149|   148|
   150|   149|---
   151|   150|
   152|   151|## 📊 评测体系
   153|   152|
   154|   153|### 评测数据集
   155|   154|
   156|   155|8个数据集，每个30条样本，共240条，覆盖四大记忆方向 + 三个赛题必测项：
   157|   156|
   158|   157|| 数据集 | 权重 | 样本结构 | 推理类型 |
   159|   158||--------|------|----------|----------|
   160|   159|| anti_interference | 15% | 多轮对话 + 噪声干扰 | single_hop, adversarial |
   161|   160|| contradiction_update | 15% | 信息变更 + 时序覆写 | knowledge_update, temporal |
   162|   161|| efficiency | 15% | 查询效率 + 准确性 | single_hop |
   163|   162|| command_memory | 10% | 操作模式识别 | single_hop, multi_hop |
   164|   163|| decision_memory | 15% | 团队决策提取 | single_hop, multi_hop, temporal |
   165|   164|| preference_memory | 15% | 个人偏好记忆 | single_hop, adversarial, knowledge_update |
   166|   165|| knowledge_health | 10% | 团队知识健康 | single_hop |
   167|   166|| long_term_memory | 5% | 长时序记忆 | temporal, multi_hop |
   168|   167|
   169|   168|### 评测指标
   170|   169|
   171|   170|| 指标 | 说明 | 来源 |
   172|   171||------|------|------|
   173|   172|| Recall@k | Top-k 结果命中率 | LongMemEval |
   174|   173|| MRR | 平均倒数排名 | 信息检索标准 |
   175|   174|| Precision | 返回结果中相关比例 | 赛题要求 |
   176|   175|| F1 | P和R的调和平均 | 赛题要求 |
   177|   176|| 延迟 P50/P95/P99 | 写入和查询延迟 | 赛题要求 |
   178|   177|| 操作节省率 | 有/无记忆的操作步数对比 | 赛题要求 |
   179|   178|
   180|   179|### 样本格式
   181|   180|
   182|   181|每个样本采用多轮对话格式：
   183|   182|
   184|   183|```json
   185|   184|{
   186|   185|  "test_id": "feishu_dec_001",
   187|   186|  "name": "前端框架选型决策",
   188|   187|  "difficulty": "easy",
   189|   188|  "reasoning_type": "single_hop",
   190|   189|  "setup": {
   191|   190|    "conversations": [
   192|   191|      {"role": "user", "content": "前端框架选React还是Vue？", "timestamp": "2026-01-15T10:00:00"},
   193|   192|      {"role": "assistant", "content": "建议React，生态更成熟", "timestamp": "2026-01-15T10:01:00"},
   194|   193|      {"role": "user", "content": "好的，方案定React了", "timestamp": "2026-01-15T10:02:00"}
   195|   194|    ]
   196|   195|  },
   197|   196|  "query": {"text": "前端框架选了什么？", "type": "search"},
   198|   197|  "expected": {"answer": "React", "keywords": ["React"], "forbidden": ["Vue"]}
   199|   198|}
   200|   199|```
   201|   200|
   202|   201|---
   203|   202|
   204|   203|## 🔧 技术架构
   205|   204|
   206|   205|### 检索流程
   207|   206|
   208|   207|```
   209|   208|查询 → 词项提取 → 词项分类(distinctive/common) → FTS5搜索 → 评分排序 → 结果
   210|   209|                      ↓
   211|   210|              中文2-3字切分 + 英文单词 + 数字
   212|   211|                      ↓
   213|   212|         distinctive: 英文/数字/3+字中文
   214|   213|         common: "什么"/"方案"等高频词
   215|   214|                      ↓
   216|   215|         FTS5: (distinctive1 OR distinctive2) AND (common1 OR common2)
   217|   216|                      ↓
   218|   217|         评分: distinctive覆盖(50%) + common覆盖(30%) + 邻近度(15%) + 精确匹配(5%)
   219|   218|```
   220|   219|
   221|   220|### 存储架构
   222|   221|
   223|   222|- **SQLite** + **FTS5** 全文索引
   224|   223|- 零外部依赖，纯本地运行
   225|   224|- 支持 private/shared/all 三级可见性
   226|   225|
   227|   226|---
   228|   227|
   229|   228|## 参考文献
   230|   229|
   231|   230|1. Wu, D., et al. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*.
   232|   231|2. Maharana, A., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*.
   233|   232|3. 飞书 OpenClaw 赛道-企业级长程协作 Memory 系统.
   234|   233|
   235|   234|---
   236|   235|
   237|   236|## License
   238|   237|
   239|   238|MIT
   240|   239|