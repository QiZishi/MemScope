# 项目进度保存 — 2026-04-28 (更新)

## 已完成任务
- ✅ T1: Hermes Agent / OpenClaw 记忆架构分析
- ✅ T2: 记忆综述论文 arxiv:2604.01707 总结
- ✅ T3: 2026年3月以来记忆模块调研
- ✅ T4: memos源码深度分析 + 改进方案
- ✅ T5: 《Memory定义与架构白皮书》→ 飞书: https://feishu.cn/docx/H4PQdfk0doqgMWx7fG2cCvUGnTh
- ✅ T6: 评测方案设计 + 100个JSON测试用例（5维度×20个）
- ✅ T7: 代码框架编写 + 8个bug修复 → 25个pytest全部通过
- ✅ T8: 飞书阶段成果小结 → https://jcneyh7qlo8i.feishu.cn/docx/EqmFdONmDomLLPxnUFrckqhanKb
- ✅ T9: GitHub同步 → https://github.com/QiZishi/MemScope (3 commits)
- ✅ T10: 模型切换 → mimo-v2.5-pro

## 进行中
- 🔄 T11: 飞书真实评测（连接现有飞书环境测试记忆架构）
- 🔄 T12: 改进闭环（优化→测试→评估→github同步→发现问题→改进）

## 修复的Bug清单
1. freshness_monitor.py: 相对导入崩溃 → 改为绝对导入
2. gap_detector.py: 无回退查询逻辑 → 添加fallback
3. gap_detector.py: 缺少中文关键词 → 添加中文domain keywords
4. preference_manager.py: resolve_conflict()是桩函数 → 实现3条规则
5. habit_inference.py: 重复记录 → 添加去重逻辑
6. schema_v2.py: INSERT OR REPLACE产生重复 → 改用ON CONFLICT
7. conftest.py: make_team_chunks UNIQUE约束冲突 → 修复turnId生成
8. test_efficiency.py: 并发测试SQLite线程安全 → 添加write_lock

## 关键文件
- 企业记忆代码: /root/hermes-data/cron/output/enterprise_memory_code/
- 评测代码: /root/hermes-data/cron/output/evaluation_code/
- 评测数据集: /root/hermes-data/cron/output/evaluation_code/datasets/ (5个JSON, 100用例)
- Demo: /root/hermes-data/cron/output/demo/
- 白皮书: /root/hermes-data/cron/output/docs/memory_whitepaper.md
