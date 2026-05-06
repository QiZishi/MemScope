File unchanged since last read. The content from the earlier read_file result in this conversation is still current — refer to that instead of re-reading.




### v5.9 (2026-05-06) — 性能优化
- **性能评测**: eval/memory_performance_eval.py — 用指标而非通过率衡量性能
  - 事实提取: Precision=90.0%, Recall=90.0%, F1=90.0%
  - 矛盾检测: Detection Rate=100%, False Positives=0
  - 主动推荐: Precision=100%, Recall=62.5%, F1=76.9%
  - 全量检索: Recall@1=58.0%, MRR=68.7%, Composite=67.0
- **关键优化**:
  - 偏好值清理: 'Python写代码'->'Python', 'Go语言'->'Go'
  - 跨类型矛盾检测: knowledge vs decision
  - 推荐相关性评分: min_relevance过滤噪声

### v5.8 (2026-05-06)
- **端到端集成测试**: eval/e2e_integration_test.py (9/9 100%)
  - 完整9阶段测试: 摄入→矛盾→一致性→整合→健康→共享→遗忘→推荐→预取
  - 模拟真实团队协作场景（Day1决策→Day5变更→整合→共享→遗忘）

### v5.7 (2026-05-06)
- **主动推荐系统**: proactive_recommend() / prefetch()
  - 基于对话上下文自动识别话题并推荐相关记忆
  - 会话开始时prefetch()返回记忆简报（决策/偏好/知识/整合摘要）
  - 搜索决策+偏好+知识+整合chunk四种记忆类型
- Memory生命周期评测: 20/20 -> 22/22 (100%)
- 检索指标: 综合评分67.05（无退化）

### v5.6 (2026-05-06)
- **记忆遗忘系统**: schedule_forgetting() / auto_forget() / execute_forgetting()
  - 被覆写决策自动遗忘（superseded -> forgotten）
  - 低新鲜度知识自动调度遗忘
  - 长期未访问chunks自动调度遗忘
  - force参数跳过时限检查
- Memory生命周期评测: 19/19 -> 20/20 (100%)
- 检索指标: 综合评分67.05（无退化）

### v5.5 (2026-05-06)
- **跨Agent记忆共享**: share_memory() / get_shared_memories()
- **记忆健康监控**: check_memory_health() — freshness/consistency/coverage
- **重要性评分**: log_memory_access() / get_memory_importance()
- Memory生命周期评测: 17/17 -> 19/19 (100%)
- 检索指标: 综合评分67.05（无退化）

### v5.4 (2026-05-06)
- **🆕 记忆整合系统**：多个相关记忆合并为高层知识
  - 决策时间线：同一主题的多次决策合并为时间线（MySQL -> PostgreSQL）
  - 偏好画像：同类偏好合并为用户画像（framework: Vue, language: Python）
  - 知识图谱：相关知识合并为图谱节点（database: PostgreSQL, infra: AWS）
- **Memory生命周期评测升级**: 16/16 -> 17/17 (100%)
- **检索指标**: Recall@1=58.01%, MRR=68.67%, 综合评分67.05（无退化）

### v5.3 (2026-05-06)
- **🆕 Memory生命周期系统**：构建完整的记忆引擎（不只是RAG）
  - `src/core/fact_extractor.py`：FactExtractor + MemoryManager
  - 自动事实提取：从对话中提取决策、偏好、知识
  - 矛盾检测：新信息自动覆写旧信息（决策/偏好/知识）
  - 统一召回：跨chunks+决策+偏好+知识的统一搜索
  - 时序排序：后续信息优先于早期信息
- **评测**: Memory生命周期评测 16/16 (100%)
- **检索指标**: Recall@1=58.01%, MRR=68.67%, 综合评分67.05

