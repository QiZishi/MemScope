# MemScope 飞书真实环境评测报告

**评测时间**: 2026-04-29 00:18:12
**团队规模**: 5人 (张工、李工、王工、赵工、陈工)
**对话轮次**: 15
**CLI命令**: 15
**知识条目**: 10

---

## 📊 评测总分: 100/100

| 方向 | 得分 | 状态 |
|------|------|------|
| A - CLI命令记忆 | 100% | ✅ 通过 |
| B - 飞书决策记忆 | 100% | ✅ 通过 |
| C - 个人偏好 | 100% | ✅ 通过 |
| D - 团队知识健康 | 100% | ✅ 通过 |

---

## 方向A: CLI命令记忆

- ✅ **高频命令识别-张工**: top=git, freq=5
- ✅ **高频命令识别-李工**: top=npm, freq=4
- ✅ **项目路径关联**: top3=['git', 'python', 'kubectl'], git=✓, docker=✗
- ✅ **上下文推荐**: 推荐数=4
- **得分: 100%**

## 方向B: 飞书决策记忆

- ✅ **决策搜索-React**: 找到1条, 标题=，我们决定用React，团队也更熟悉
- ✅ **决策搜索-Docker**: 找到1条
- ✅ **决策搜索-PostgreSQL**: 找到1条
- ✅ **决策卡片推送**: 推送1张卡片
- ✅ **决策质量检查**: 总3条, 有效3条
- **得分: 100%**

## 方向C: 个人偏好

- ✅ **张工偏好提取**: 共3条偏好, vim偏好✓
    [style/habit_zh] = 先写测试再写代码
    [style/preference_zh] = vim写代码
    [tool/preference_zh] = PostgreSQL，JSON支持
- ✅ **李工偏好提取**: 共1条偏好
    [style/habit_zh] = 用VSCode
- ✅ **赵工偏好提取**: 共1条偏好
    [style/habit_zh] = 早上9点到12点效率最高
- ✅ **团队偏好统计**: 团队总偏好数: 5
- **得分: 100%**

## 方向D: 团队知识健康

- ✅ **知识健康摘要**: 总知识: 10, fresh=10, aging=0, stale=0, forgotten=0
    平均新鲜度: 1.0
- ✅ **知识缺口检测**: 检测到10个缺口
    [critical] infrastructure: infrastructure 领域知识不足: 0 条, 0 人掌握
    [high] architecture: architecture 领域知识不足: 1 条, 1 人掌握
    [high] security: security 领域知识不足: 1 条, 1 人掌握
- ✅ **单点故障识别**: 识别到2个单点故障
    [security] 安全审计流程: holders=1, risk=0.95
    [architecture] 系统架构文档: holders=1, risk=0.9
- ✅ **团队知识地图**: 覆盖率: 0.9, 单点领域: 4
- ✅ **艾宾浩斯模型**: R(1d,general)=0.9900, status(5d)=fresh
- **得分: 100%**

---

## 📋 数据摘要

### 方向A: 命令统计

**张工** 高频命令:
  - `git` (频率: 5, 项目: /home/project-alpha)
  - `python` (频率: 1, 项目: /home/project-alpha)
  - `kubectl` (频率: 1, 项目: /home/project-alpha)
  - `docker` (频率: 1, 项目: /home/project-alpha)

**李工** 高频命令:
  - `npm` (频率: 4, 项目: /home/project-beta)
  - `git` (频率: 2, 项目: /home/project-beta)
  - `docker` (频率: 1, 项目: /home/project-beta)

### 方向B: 决策清单

- **用PostgreSQL**: 用PostgreSQL
- **，我们确认用Docker容器化部署，而不是直接部署到裸机**: ，我们确认用Docker容器化部署，而不是直接部署到裸机
- **，我们决定用React，团队也更熟悉**: ，我们决定用React，团队也更熟悉

### 方向C: 偏好概览

**张工** (3条):
  - [style/habit_zh] = 先写测试再写代码 (置信度: 0.60)
  - [style/preference_zh] = vim写代码 (置信度: 0.80)
  - [tool/preference_zh] = PostgreSQL，JSON支持 (置信度: 0.70)

**李工** (1条):
  - [style/habit_zh] = 用VSCode (置信度: 0.60)

**赵工** (1条):
  - [style/habit_zh] = 早上9点到12点效率最高 (置信度: 0.60)

### 方向D: 知识健康

**团队**: team-feishu
**总知识**: 10
**状态分布**: fresh=10, aging=0, stale=0, forgotten=0
**平均新鲜度**: 1.0000
**高风险项**: 0

**单点故障列表**:
  - 安全审计流程 (类别: security, 持有人: ['赵工'], 风险: 0.9500)
  - 系统架构文档 (类别: architecture, 持有人: ['张工'], 风险: 0.9000)

**知识缺口**:
  - [critical] infrastructure: 领域 [infrastructure] 完全无知识覆盖，建议立即补充文档或引入专家
  - [high] architecture: 领域 [architecture] 仅有 1 人掌握，存在单点故障风险，建议知识共享
  - [high] security: 领域 [security] 仅有 1 人掌握，存在单点故障风险，建议知识共享
  - [high] frontend: 领域 [frontend] 仅有 1 人掌握，存在单点故障风险，建议知识共享
  - [high] testing: 领域 [testing] 仅有 1 人掌握，存在单点故障风险，建议知识共享
  - [medium] api_design: 领域 [api_design] 知识条目较少（2），建议持续积累
  - [medium] database: 领域 [database] 知识条目较少（1），建议持续积累
  - [medium] devops: 领域 [devops] 知识条目较少（1），建议持续积累
  - [medium] backend: 领域 [backend] 知识条目较少（2），建议持续积累
  - [medium] business: 领域 [business] 知识条目较少（2），建议持续积累

---

## 🔧 技术栈

- **存储**: SQLite (SqliteStore)
- **方向A**: CommandTracker + CommandRecommender
- **方向B**: DecisionExtractor + DecisionCardManager
- **方向C**: PreferenceExtractor + PreferenceManager + HabitInference
- **方向D**: EbbinghausModel + FreshnessMonitor + GapDetector
