# 公开记忆评测基准分析：LONGMEMEVAL 与 LOCOMO

> 为 MemScope 评测数据集构建提供理论支撑
> 分析时间：2026-04-29

---

## 1. LONGMEMEVAL

### 1.1 论文信息

- **标题**: LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory
- **作者**: Di Wu (UCLA), Hongwei Wang, Wenhao Yu (Tencent AI Lab), Yuwei Zhang (UC San Diego), Kai-Wei Chang (UCLA), Dong Yu (Tencent AI Lab)
- **会议**: ICLR 2025
- **arXiv**: [2410.10813](https://arxiv.org/abs/2410.10813)
- **GitHub**: https://github.com/xiaowu0162/LongMemEval
- **数据集**: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned

### 1.2 数据集结构

每个评测样本的 JSON Schema：

```json
{
  "question_id": "string",          // 唯一ID，后缀 _abs 标记不可回答问题
  "question_type": "string",        // 问题类型（见下表）
  "question": "string",             // 问题文本
  "answer": "string",               // 标准答案（短语或评分标准）
  "question_date": "string",        // 提问日期
  "haystack_session_ids": ["..."],  // 历史会话ID列表（按时间排序）
  "haystack_dates": ["..."],        // 历史会话时间戳
  "haystack_sessions": [            // 会话列表
    [                               // 单个会话 = 多轮对话
      {"role": "user", "content": "...", "has_answer": true},
      {"role": "assistant", "content": "..."}
    ]
  ],
  "answer_session_ids": ["..."]     // 包含证据的会话ID
}
```

**数据集规模**: 500 个评测实例，分三个版本：
- `longmemeval_oracle.json` — 仅证据会话（oracle 检索设置）
- `longmemeval_s_cleaned.json` — ~115k tokens/问题（40-80 会话）
- `longmemeval_m_cleaned.json` — 500 会话（~1.5M tokens/问题）

### 1.3 评测能力分类

| 能力 | 问题类型 | 说明 |
|------|----------|------|
| 信息提取 (IE) | single-session-user | 从单会话中回忆用户提到的细节 |
| 信息提取 (IE) | single-session-assistant | 从单会话中回忆助手提供的信息 |
| 信息提取 (IE) | single-session-preference | 个性化响应中正确使用用户信息 |
| 多会话推理 (MR) | multi-session | 跨 2-6 个会话综合信息（聚合、比较） |
| 知识更新 (KU) | knowledge-update | 识别用户信息随时间的变化 |
| 时间推理 (TR) | temporal-reasoning | 关于时间戳和时间关系的推理 |
| 拒答 (ABS) | abstention (_abs后缀) | 识别不可回答的问题 |

### 1.4 数据集制作流程

1. **本体构建**: 164 个手工构建的用户属性（5类：人口统计、生活方式、情境上下文、生活事件、物品）
2. **背景生成**: Llama 3 70B Instruct 为每个属性生成详细用户传记段落
3. **问题创建**: LLM 提出种子 (问题, 答案) 对，人工专家筛选和改写（~1000候选/类型 → 最终500题，通过率~5%）
4. **证据分解**: 人工专家将每个答案分解为 1+ 个证据声明，可选时间戳
5. **证据会话构建**: Llama 3 70B 模拟用户-AI 聊天会话，用户**间接**提及证据（非显式）。~70%会话经人工编辑
6. **历史编排（大海捞针）**: 证据会话插入填充会话池（25% ShareGPT, 25% UltraChat, 50% 模拟）

### 1.5 评测指标

**主要指标 — QA 准确率**:
- 使用 LLM-as-judge（GPT-4o）
- 每种问题类型使用**独立的评估 prompt**
- 二值输出："yes"（正确）或 "no"（不正确）
- 与人工专家一致率 >97%

**次要指标 — 记忆召回（中间检索）**:
- **Recall@k**: 证据会话/轮次在 top-k 检索结果中的比例
- **NDCG@k**: 归一化折损累积增益

### 1.6 关键发现

1. 商用系统显著下降：ChatGPT 准确率下降 37%，Coze 下降 64%
2. 长上下文 LLM 在 LongMemEval_S 上下降 30-60%
3. 将会话分解为**轮次**（1用户+1助手）作为检索单元效果更好
4. 拼接提取的**用户事实**作为扩展键，Recall@k 提升 9.4%，QA 准确率提升 5.4%
5. 时间感知查询扩展，时间推理 Recall 提升 6.8-11.3%
6. Chain-of-Note + JSON 结构化格式效果最佳

---

## 2. LOCOMO

### 2.1 论文信息

- **标题**: Evaluating Very Long-Term Conversational Memory of LLM Agents
- **作者**: Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang
- **会议**: ACL Findings 2024
- **arXiv**: [2402.17753](https://arxiv.org/abs/2402.17753)
- **项目页**: https://snap-research.github.io/locomo/

### 2.2 数据集结构

LOCOMO 数据集的核心结构：

```json
{
  "conversation_id": "string",
  "sessions": [                    // 最多35个会话
    {
      "session_id": "string",
      "turns": [                   // 平均300轮/对话，~9K tokens
        {
          "role": "user" | "assistant",
          "content": "string",
          "timestamp": "string",
          "image": "string | null"  // 多模态支持
        }
      ]
    }
  ],
  "persona": {                     // 角色描述
    "user": "string",
    "assistant": "string"
  },
  "event_graph": {...},            // 时间事件图（对话的结构化表示）
  "questions": [                   // 1,813 个问题
    {
      "question": "string",
      "answer": "string",
      "category": "string",       // single-hop, multi-hop, temporal, adversarial
      "evidence": ["string"]      // 证据来源
    }
  ]
}
```

**数据集规模**: 10 个长对话，共 1,813 个问题

### 2.3 评测能力分类

| 类别 | 说明 |
|------|------|
| Single-hop | 单跳问题，答案在单个会话中 |
| Multi-hop | 多跳问题，需要跨多个会话综合信息 |
| Temporal | 时间推理问题，需要理解事件时间关系 |
| Adversarial | 对抗性问题，测试系统是否会编造不存在的信息 |

### 2.4 数据集制作流程

1. **角色设定**: 为每个 agent 创建详细的角色描述（persona）
2. **时间事件图**: 构建结构化的事件图，定义事件的时间关系和因果链
3. **LLM Agent 对话生成**: 使用 LLM-based agent 架构，基于角色和事件图生成对话
4. **多模态扩展**: Agent 具备分享和响应图片的能力
5. **人工验证**: 人工标注者验证和编辑对话的长程一致性和事件图锚定
6. **问题构建**: 基于对话内容构建四类问题（single-hop, multi-hop, temporal, adversarial）

### 2.5 评测指标

- **QA 准确率**: 基于答案匹配的准确率
- **事件摘要质量**: 自动生成的事件摘要与标准摘要的对比
- **多模态对话生成质量**: 包含图片引用的对话生成评估
- **人工评估**: 人工评分模型的长期记忆能力

### 2.6 关键发现

1. LLM 在理解长对话和把握长时间范围的时间/因果动态方面存在挑战
2. 长上下文 LLM 和 RAG 可以提供改进，但仍显著落后于人类表现
3. 对抗性问题对模型特别困难（容易被误导生成不存在的信息）

---

## 3. 对 MemScope 评测数据集构建的启示

### 3.1 数据集设计原则

| 原则 | LONGMEMEVAL 做法 | LOCOMO 做法 | MemScope 建议 |
|------|------------------|-------------|---------------|
| 样本独立性 | 每个问题独立 | 每个对话独立 | 每个评测样本独立，无事实关联 |
| 业务场景 | 通用对话 | 日常对话 | 企业办公/研发场景 |
| 时间跨度 | 多月跨度 | 35会话跨度 | 2年长时序 |
| 证据标注 | has_answer 标记 | evidence 字段 | 明确标注期望答案来源 |
| 难度梯度 | 7种问题类型 | 4种问题类别 | easy/medium/hard 三级 |

### 3.2 评测指标借鉴

| 指标 | 来源 | MemScope 应用 |
|------|------|---------------|
| 命中率 (Hit Rate) | LONGMEMEVAL Recall@k | 系统返回结果中包含正确答案的比例 |
| QA 准确率 | 两者均有 | 系统回答正确的比例 |
| 时间推理准确率 | LONGMEMEVAL TR | 时间相关问题的正确率 |
| 抗干扰准确率 | LOCOMO adversarial | 系统不被无关信息误导的比例 |
| 知识更新准确率 | LONGMEMEVAL KU | 信息更新后返回最新值的比例 |
| 操作节省率 | 赛题要求 | 使用前后操作步数/字符数对比 |
| 效率指标 | LONGMEMEVAL 延迟 | 写入/查询延迟 P50/P95/P99 |

### 3.3 制作流程建议

1. **场景设计**: 定义企业办公场景下的记忆类型（命令、决策、偏好、知识）
2. **样本生成**: 每个样本包含独立的业务场景，有明确的输入和期望输出
3. **时间分布**: 样本覆盖不同时间跨度（1天~2年）
4. **难度分层**: 每个数据集包含 easy/medium/hard 三级难度
5. **验证机制**: 每个样本的期望输出需经过规则验证

---

## 参考文献

1. Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. *ICLR 2025*. arXiv:2410.10813.
2. Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., & Fang, Y. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents. *ACL Findings 2024*. arXiv:2402.17753.
