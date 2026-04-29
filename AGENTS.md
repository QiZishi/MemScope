# MemScope 开发指南

> 本文件定义了 MemScope 项目的开发规范和约束，所有开发工作必须遵守。

## 赛题要求

**必读文件**：[.hermes/competition_requirements.md](.hermes/competition_requirements.md)

在开发 MemScope 的任何功能前，必须先阅读赛题要求文档，确保：
1. 所有功能开发对齐赛题的三大挑战（定义记忆、构建引擎、证明价值）
2. 评测数据集覆盖赛题要求的三种测试（抗干扰、矛盾更新、效能验证）
3. 最终交付物包含白皮书、可运行 Demo、评测报告

## 核心原则

### 代码测试 vs 评估（严格区分）

- **代码测试**（test/ 目录）：用 pytest + mock 检验代码是否有 bug
  - 代码测试结果 **禁止** 出现在 README 或任何对外文档中
  - 代码测试仅用于开发阶段的质量保障

- **评估**（eval/ 目录）：用真实系统 + 评测数据集衡量实际性能
  - 评估结果是对外展示性能的 **唯一数据来源**
  - 所有评估数据必须来自 `eval/real_evaluation.py` 的实际运行结果
  - **禁止编造任何评估数字**

### 数据真实性

- 所有对外展示的数字必须有实际运行记录可追溯
- 未执行的评估标注为"待测试"，不得编造数字
- 评估结果必须包含 200 条完整评测数据集的全部结果，不得选取部分数据集

## 目录结构

```
MemScope/
├── .hermes/                           # 开发配置
│   └── competition_requirements.md    # 赛题要求（必读）
│
├── src/                               # 核心源码
│   ├── core/                          # 存储层
│   ├── recall/                        # 检索引擎
│   ├── ingest/                        # 摄取管线
│   ├── command_memory/                # 方向A: CLI命令记忆
│   ├── decision_memory/               # 方向B: 飞书决策记忆
│   ├── preference_memory/             # 方向C: 个人偏好记忆
│   └── knowledge_health/              # 方向D: 团队知识健康
│
├── test/                              # 代码测试（检验bug）
│   ├── conftest.py
│   ├── eval_runner.py
│   └── test_*.py
│
├── eval/                              # 评测（衡量性能）
│   ├── datasets/                      # 200条评测数据集
│   ├── real_evaluation.py             # 真实系统评测脚本
│   └── ...
│
├── demo/                              # 演示脚本
├── docs/                              # 设计文档
└── README.md                          # 项目说明（仅展示真实评估数据）
```

## 开发检查清单

在提交任何代码变更前，确认：

- [ ] 运行 `python3 -m pytest test/ -v` 确保代码测试通过
- [ ] 运行 `python3 eval/real_evaluation.py` 确保评估结果不退化
- [ ] README 中的数据全部来自真实评估结果
- [ ] 没有在 README 中展示代码测试通过率
