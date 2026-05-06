File unchanged since last read. The content from the earlier read_file result in this conversation is still current — refer to that instead of re-reading.
### v5.3 (2026-05-06)
- **🆕 Memory生命周期系统**：构建完整的记忆引擎（不只是RAG）
  - `src/core/fact_extractor.py`：FactExtractor + MemoryManager
  - 自动事实提取：从对话中提取决策、偏好、知识
  - 矛盾检测：新信息自动覆写旧信息（决策/偏好/知识）
  - 统一召回：跨chunks+决策+偏好+知识的统一搜索
  - 时序排序：后续信息优先于早期信息
- **评测**: Memory生命周期评测 16/16 (100%)
- **检索指标**: Recall@1=58.01%, MRR=68.67%, 综合评分67.05

