# 🧠 企业级长期协作记忆系统 — 演示指南

> **Feishu OpenClaw 大赛参赛作品**  
> Enterprise-level Long-term Collaboration Memory System

---

## 📋 系统概述

本系统在 Hermes Agent 的 memos-local-hermes-plugin 基础上，扩展了四大企业级能力：

| 方向 | 名称 | 工具 |
|------|------|------|
| **方向 C** | 个人工作习惯 / 偏好记忆 | `preference_set`, `preference_get`, `preference_list`, `habit_patterns` |
| **方向 D** | 团队知识健康 / 遗忘预警 | `knowledge_health`, `knowledge_gaps`, `knowledge_alerts`, `team_knowledge_map` |
| **扩展** | 知识新鲜度监控 | `knowledge_freshness` |

### 核心技术特性

- **混合搜索**: RRF + MMR + 时间衰减
- **偏好生命周期**: 显式声明 > 行为推断，带置信度衰减
- **习惯推断引擎**: 时间模式、工具频率、主题聚类、工作流序列挖掘
- **知识健康监控**: 新鲜 → 老化 → 过期 → 被遗忘 四阶段生命周期
- **团队覆盖分析**: 10 大知识领域检测 + 单点故障识别

---

## 🚀 快速开始

### 环境要求

```bash
python3 >= 3.8
# 无需额外依赖，仅使用标准库 (sqlite3, json, time, uuid 等)
```

### 运行 CLI 演示

```bash
cd /root/hermes-data/cron/output/demo/
python3 demo_cli.py
```

演示将自动执行以下流程：
1. 🗄️  初始化 SQLite 数据库和 Schema v2
2. 📝  演示 **preference_set** — 设置用户偏好
3. 🔍  演示 **preference_get** — 查询单个偏好
4. 📋  演示 **preference_list** — 列出所有偏好
5. 🧩  演示 **habit_patterns** — 习惯推断分析
6. 🩺  演示 **knowledge_health** — 知识健康状态检查
7. 🔎  演示 **knowledge_gaps** — 团队知识缺口检测
8. ⚠️  演示 **knowledge_alerts** — 知识预警推送
9. 🗺️  演示 **team_knowledge_map** — 团队知识地图
10. 🌊  演示 **knowledge_freshness** — 新鲜度监控

### 运行飞书集成演示

```bash
python3 demo_feishu.py
```

> ⚠️ 飞书演示需要配置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 环境变量。  
> 在未配置时，将以模拟模式运行，展示完整的集成流程。

---

## 📁 文件结构

```
demo/
├── README.md            # 本文件 — 演示说明
├── demo_cli.py          # CLI 演示脚本（核心演示）
├── demo_feishu.py       # 飞书 API 集成演示
└── demo_scenario.md     # 详细场景演练（中文）
```

---

## 🎯 演示场景

### 场景一：个人偏好记忆（方向 C）

**角色**: 张三 — 后端工程师  
**场景**: 记录和推断个人工作偏好

```python
# 显式设置偏好
preference_set("zhangsan", "tool_preference", "ide", "VSCode")
preference_set("zhangsan", "schedule", "deep_work_time", "09:00-12:00")

# 系统自动推断行为模式
habit_patterns("zhangsan")  
# → 发现：最活跃时段 09:00-12:00，常用工具 terminal，高频主题 "kubernetes"
```

### 场景二：团队知识健康（方向 D）

**角色**: 技术负责人  
**场景**: 监控团队知识覆盖率和遗忘风险

```python
# 分析团队知识覆盖
team_knowledge_map("eng-team")
# → 发现：security 领域覆盖仅 20%，devops 领域存在单点故障

# 获取知识预警
knowledge_alerts("eng-team")
# → 告警：3 条过期 API 文档，1 条被遗忘的架构决策

# 检测知识缺口
knowledge_gaps("eng-team", domain="security")
# → 建议：安排安全知识转移会议
```

---

## 🔧 集成说明

本系统以 Hermes Agent 插件形式运行，通过以下 Hook 接入工作流：

- `on_session_start` — 加载用户偏好和行为模式
- `pre_llm_call` — 注入相关记忆上下文
- `post_llm_call` — 提取新知识并更新记忆
- `on_session_end` — 触发习惯推断和健康检查

### 与飞书集成

详见 `demo_feishu.py`，展示了从飞书消息接收 → 记忆提取 → 存储 → 检索 → 预警推送的完整链路。

---

## 📊 数据库 Schema

新增四张表（Schema v2）：

| 表名 | 用途 | 方向 |
|------|------|------|
| `user_preferences` | 用户偏好存储 | C |
| `behavior_patterns` | 行为模式记录 | C |
| `knowledge_health` | 知识新鲜度追踪 | D |
| `team_knowledge_map` | 团队领域覆盖分析 | D |

---

## 🏆 亮点总结

1. **完整记忆生命周期**: 从创建 → 使用 → 衰减 → 归档的全链路管理
2. **智能偏好推断**: 基于行为数据自动发现工作习惯，置信度动态调整
3. **团队级知识治理**: 10 大领域自动覆盖分析 + 单点故障预警
4. **零依赖部署**: 纯 Python 标准库实现，SQLite 存储，即插即用
5. **飞书原生集成**: 消息触发 → 记忆更新 → 预警推送的自动化闭环

---

*Built for Feishu OpenClaw Competition — 2025*
