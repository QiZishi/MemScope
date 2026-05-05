# MemScope 优化历史

> 记录每轮对抗优化循环的详细过程

---

## 第 1 轮优化（2026-05-06）

### 初始状态
- 综合得分：33.59 / 100
- 评级：不及格

### 评测结果

| 维度 | 得分 | 权重 | 状态 |
|------|------|------|------|
| anti_interference | 4.2 | 15% | ❌ 严重不足 |
| command_memory | 86.7 | 10% | ✅ 优秀 |
| contradiction_update | 3.3 | 15% | ❌ 严重不足 |
| decision_memory | 41.7 | 15% | ❌ 不及格 |
| efficiency | 0.0 | 15% | ❌ 未测试 |
| knowledge_health | 97.9 | 10% | ✅ 优秀 |
| long_term_memory | 56.7 | 5% | ❌ 不及格 |
| preference_memory | 32.8 | 15% | ❌ 严重不足 |

### 问题分析

1. **搜索结果为空**：anti_interference 和 contradiction_update 的 chunks_found=0
2. **FTS5索引未同步**：insert_chunk 函数没有正确同步 FTS5 索引
3. **UNIQUE约束冲突**：insert_conversation 函数使用相同的 turnId 导致数据被覆盖
4. **中文分词不足**：查询被当作完整字符串搜索，未拆分成词组

### 优化内容

1. **修复 FTS5 索引同步**：
   - 将 FTS5 表从 content-table 模式改为 standalone 模式
   - 修改 insert_chunk 函数，同步插入 FTS5 表

2. **修复 UNIQUE 约束冲突**：
   - 修改 insert_conversation 函数，为每条消息使用唯一的 turnId

3. **改进中文分词逻辑**：
   - 使用多种策略拆分查询：3+字符片段、2字符bigrams、完整查询
   - 去重并保留顺序

### 优化后结果

- 综合得分：54.94 / 100（+21.35）
- 评级：不及格

| 维度 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| anti_interference | 4.2 | 60.4 | +56.2 |
| command_memory | 86.7 | 86.7 | 0 |
| contradiction_update | 3.3 | 80.0 | +76.7 |
| decision_memory | 41.7 | 41.7 | 0 |
| efficiency | 0.0 | 0.0 | 0 |
| knowledge_health | 97.9 | 97.9 | 0 |
| long_term_memory | 56.7 | 85.0 | +28.3 |
| preference_memory | 32.8 | 32.8 | 0 |

### 下轮优化方案

1. **修复效率测试**：efficiency 维度得分为 0，需要检查评测代码
2. **优化决策提取**：decision_memory 得分较低，需要改进提取算法
3. **优化偏好提取**：preference_memory 得分较低，需要改进提取算法
4. **提升评测难度**：增加噪声数量、提高噪声相似度

---

## 第 2 轮优化（待执行）
