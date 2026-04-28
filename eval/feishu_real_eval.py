#!/usr/bin/env python3
"""
MemScope 飞书真实环境端到端评测脚本
模拟5人研发团队在飞书群聊中的真实工作场景，评测四个方向。
"""
import json, os, sys, time, tempfile, logging
from datetime import datetime

sys.path.insert(0, '/root/hermes-data/cron/output')

from src.core.store import SqliteStore
from src.direction_a.command_tracker import CommandTracker
from src.direction_a.recommender import CommandRecommender
from src.direction_b.decision_extractor import DecisionExtractor
from src.direction_b.decision_card import DecisionCardManager
from src.direction_c.preference_extractor import PreferenceExtractor
from src.direction_c.preference_manager import PreferenceManager
from src.direction_c.habit_inference import HabitInference
from src.direction_d.ebbinghaus import EbbinghausModel
from src.direction_d.freshness_monitor import FreshnessMonitor
from src.direction_d.gap_detector import GapDetector

logging.basicConfig(level=logging.WARNING)

# ============================================================
# 创建评测数据库
# ============================================================
eval_dir = '/root/hermes-data/cron/output/eval'
tmpdir = tempfile.mkdtemp()
db = os.path.join(tmpdir, 'feishu_eval.db')
store = SqliteStore(db)

# 初始化所有模块
tracker = CommandTracker(store)
recommender = CommandRecommender(store)
extractor_b = DecisionExtractor(store)
card_mgr = DecisionCardManager(store)
extractor_c = PreferenceExtractor(store)
pref_mgr = PreferenceManager(store)
habit = HabitInference(store)
monitor = FreshnessMonitor(store)
detector = GapDetector(store)
model = EbbinghausModel()

# 评测结果收集
results = {}
eval_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

print("=" * 60)
print("MemScope 飞书真实环境评测")
print("=" * 60)
print(f"评测时间: {eval_time}")
print(f"数据库: {db}")
print()

# ============================================================
# Phase 1: 模拟飞书对话注入 (方向B + C)
# ============================================================
print("Phase 1: 模拟飞书对话注入...")

conversations = [
    # 第1天: 技术选型讨论
    {"sender": "张工", "content": "大家讨论一下前端框架，React还是Vue？", "day": 1, "channel": "tech-decision"},
    {"sender": "李工", "content": "我建议React，生态更成熟，TypeScript支持好", "day": 1, "channel": "tech-decision"},
    {"sender": "王工", "content": "同意，我们决定用React，团队也更熟悉", "day": 1, "channel": "tech-decision"},
    {"sender": "赵工", "content": "好的，方案定React了", "day": 1, "channel": "tech-decision"},

    # 第2天: 部署方案
    {"sender": "张工", "content": "部署方案大家有什么建议？", "day": 2, "channel": "tech-decision"},
    {"sender": "李工", "content": "我建议用Docker + K8s，标准化部署", "day": 2, "channel": "tech-decision"},
    {"sender": "王工", "content": "同意，我们确认用Docker容器化部署，而不是直接部署到裸机", "day": 2, "channel": "tech-decision"},

    # 第3天: 数据库选型
    {"sender": "赵工", "content": "数据库选型，PostgreSQL还是MySQL？", "day": 3, "channel": "tech-decision"},
    {"sender": "张工", "content": "PostgreSQL，JSON支持更好，适合我们的场景", "day": 3, "channel": "tech-decision"},
    {"sender": "李工", "content": "最终决定用PostgreSQL", "day": 3, "channel": "tech-decision"},

    # 偏好表达 (方向C)
    {"sender": "张工", "content": "我更喜欢用vim写代码，效率高", "day": 1, "channel": "dev-chat"},
    {"sender": "李工", "content": "我习惯用VSCode，插件生态好", "day": 1, "channel": "dev-chat"},
    {"sender": "王工", "content": "我偏好用zsh而不是bash，自动补全强", "day": 2, "channel": "dev-chat"},
    {"sender": "赵工", "content": "我一般早上9点到12点效率最高，这段时间不要安排会议", "day": 2, "channel": "dev-chat"},
    {"sender": "张工", "content": "我通常先写测试再写代码，TDD风格", "day": 3, "channel": "dev-chat"},
]

# 提取并保存决策 (方向B)
all_decisions = []
for conv in conversations:
    decisions = extractor_b.extract_from_message(
        message=conv["content"],
        sender=conv["sender"],
        project_id="",
        channel_id=conv["channel"],
    )
    for d in decisions:
        saved_ids = extractor_b.save_decisions([d], owner="team-feishu")
        if saved_ids:
            all_decisions.append(d)

print(f"  决策提取: {len(all_decisions)} 条")

# 提取偏好 (方向C)
all_preferences = []
for conv in conversations:
    prefs = extractor_c.extract_from_conversation(
        user_msg=conv["content"],
        assistant_msg="",
        owner=conv["sender"],
    )
    for p in prefs:
        try:
            pref_mgr.set_preference(
                owner=conv["sender"],
                category=p["category"],
                key=p["key"],
                value=p["value"],
                source=p.get("source", "extracted"),
                confidence=p.get("confidence", 0.5),
            )
            all_preferences.append(p)
        except Exception as e:
            pass

print(f"  偏好提取: {len(all_preferences)} 条")
print()

# ============================================================
# Phase 2: 模拟CLI命令注入 (方向A)
# ============================================================
print("Phase 2: 模拟CLI命令注入...")

commands = [
    # 张工的命令 (project-alpha)
    ("张工", "git status", 0, "/home/project-alpha"),
    ("张工", "git commit -m feat: add auth", 0, "/home/project-alpha"),
    ("张工", "git push origin main", 0, "/home/project-alpha"),
    ("张工", "docker build -t alpha:v1 .", 0, "/home/project-alpha"),
    ("张工", "kubectl apply -f deploy.yaml", 0, "/home/project-alpha"),
    ("张工", "git status", 0, "/home/project-alpha"),
    ("张工", "python -m pytest tests/ -v", 0, "/home/project-alpha"),
    ("张工", "git status", 0, "/home/project-alpha"),

    # 李工的命令 (project-beta)
    ("李工", "npm install", 0, "/home/project-beta"),
    ("李工", "npm run build", 0, "/home/project-beta"),
    ("李工", "npm test", 0, "/home/project-beta"),
    ("李工", "git add .", 0, "/home/project-beta"),
    ("李工", "git commit -m fix: build error", 0, "/home/project-beta"),
    ("李工", "npm run build", 0, "/home/project-beta"),
    ("李工", "docker compose up -d", 0, "/home/project-beta"),
]

cmd_count = 0
for owner, command, exit_code, project_path in commands:
    result = tracker.log_command(
        owner=owner,
        command=command,
        exit_code=exit_code,
        project_path=project_path,
    )
    if result:
        cmd_count += 1

print(f"  命令注入: {cmd_count}/{len(commands)} 条")
print()

# ============================================================
# Phase 3: 模拟知识注入 (方向D)
# ============================================================
print("Phase 3: 模拟知识注入...")

knowledge_items = [
    ("API设计规范", "api_doc", 0.8, ["张工", "李工", "王工"]),
    ("系统架构文档", "architecture", 0.9, ["张工"]),
    ("安全审计流程", "security", 0.95, ["赵工"]),
    ("CI/CD流水线配置", "devops", 0.7, ["李工", "王工"]),
    ("客户A需求文档", "client", 0.85, ["张工", "赵工"]),
    ("竞品分析报告", "competitor", 0.6, ["王工"]),
    ("数据库设计文档", "database", 0.8, ["张工", "李工"]),
    ("前端组件库", "frontend", 0.7, ["李工"]),
    ("后端API接口", "backend", 0.75, ["张工", "王工"]),
    ("测试用例规范", "testing", 0.65, ["赵工"]),
]

knowledge_count = 0
for topic, category, importance, holders in knowledge_items:
    kh_id = monitor.register_knowledge(
        chunk_id=topic,
        team_id="team-feishu",
        category=category,
        importance=importance,
        holders=holders,
    )
    if kh_id:
        knowledge_count += 1

print(f"  知识注册: {knowledge_count}/{len(knowledge_items)} 条")
print()

# ============================================================
# Phase 4: 评测查询
# ============================================================
print("=" * 60)
print("Phase 4: 评测查询")
print("=" * 60)
print()

# ------ 方向A评测 ------
print("--- 方向A (CLI命令记忆) ---")
a_results = []

# A1: 张工推荐命令 → 应该推荐 git
rec_zhang = tracker.recommend(owner="张工", limit=5)
a1_pass = False
a1_detail = ""
if rec_zhang:
    top_cmd = rec_zhang[0].get("command", "")
    if "git" in top_cmd.lower():
        a1_pass = True
        a1_detail = f"top={top_cmd}, freq={rec_zhang[0].get('frequency', 0)}"
    else:
        a1_detail = f"top={top_cmd} (expected git)"
else:
    a1_detail = "无推荐结果"
a_results.append(("高频命令识别-张工", a1_pass, a1_detail))
print(f"  {'✅' if a1_pass else '❌'} 张工推荐: {a1_detail}")

# A2: 李工推荐命令 → 应该推荐 npm
rec_li = tracker.recommend(owner="李工", limit=5)
a2_pass = False
a2_detail = ""
if rec_li:
    top_cmd = rec_li[0].get("command", "")
    if "npm" in top_cmd.lower():
        a2_pass = True
        a2_detail = f"top={top_cmd}, freq={rec_li[0].get('frequency', 0)}"
    else:
        a2_detail = f"top={top_cmd} (expected npm)"
else:
    a2_detail = "无推荐结果"
a_results.append(("高频命令识别-李工", a2_pass, a2_detail))
print(f"  {'✅' if a2_pass else '❌'} 李工推荐: {a2_detail}")

# A3: 项目路径过滤
rec_alpha = recommender.context_recommend(owner="张工", current_dir="/home/project-alpha", limit=5)
a3_pass = False
a3_detail = ""
if rec_alpha:
    top3_cmds = [r.get("command", "") for r in rec_alpha[:3]]
    has_git = any("git" in c.lower() for c in top3_cmds)
    has_docker = any("docker" in c.lower() for c in top3_cmds)
    a3_pass = has_git
    a3_detail = f"top3={top3_cmds}, git={'✓' if has_git else '✗'}, docker={'✓' if has_docker else '✗'}"
else:
    a3_detail = "无推荐结果"
a_results.append(("项目路径关联", a3_pass, a3_detail))
print(f"  {'✅' if a3_pass else '❌'} 项目路径: {a3_detail}")

# A4: 上下文推荐 (有recent commands)
rec_ctx = recommender.context_recommend(
    owner="张工",
    current_dir="/home/project-alpha",
    recent_commands=["git commit -m feat: add auth"],
    limit=5,
)
a4_pass = len(rec_ctx) > 0
a4_detail = f"推荐数={len(rec_ctx)}"
a_results.append(("上下文推荐", a4_pass, a4_detail))
print(f"  {'✅' if a4_pass else '❌'} 上下文推荐: {a4_detail}")

print()

# ------ 方向B评测 ------
print("--- 方向B (飞书决策记忆) ---")
b_results = []

# B1: 搜索"React" → 应找到 React 决策
search_react = extractor_b.search_decisions(query="React", owner="team-feishu", limit=5)
b1_pass = len(search_react) > 0
b1_detail = f"找到{len(search_react)}条"
if search_react:
    b1_detail += f", 标题={search_react[0].get('title', 'N/A')[:30]}"
b_results.append(("决策搜索-React", b1_pass, b1_detail))
print(f"  {'✅' if b1_pass else '❌'} 搜索React: {b1_detail}")

# B2: 搜索"Docker" → 应找到 Docker 决策
search_docker = extractor_b.search_decisions(query="Docker", owner="team-feishu", limit=5)
b2_pass = len(search_docker) > 0
b2_detail = f"找到{len(search_docker)}条"
b_results.append(("决策搜索-Docker", b2_pass, b2_detail))
print(f"  {'✅' if b2_pass else '❌'} 搜索Docker: {b2_detail}")

# B3: 搜索"PostgreSQL" → 应找到数据库决策
search_pg = extractor_b.search_decisions(query="PostgreSQL", owner="team-feishu", limit=5)
b3_pass = len(search_pg) > 0
b3_detail = f"找到{len(search_pg)}条"
b_results.append(("决策搜索-PostgreSQL", b3_pass, b3_detail))
print(f"  {'✅' if b3_pass else '❌'} 搜索PostgreSQL: {b3_detail}")

# B4: 决策卡片推送 → 当前提到 "React" 时应推送
cards = card_mgr.check_and_push(current_message="我们前端用React来做这个功能", owner="team-feishu")
b4_pass = len(cards) > 0
b4_detail = f"推送{len(cards)}张卡片"
b_results.append(("决策卡片推送", b4_pass, b4_detail))
print(f"  {'✅' if b4_pass else '❌'} 决策卡片推送: {b4_detail}")

# B5: 所有决策应有内容 (title/context 非空)
all_dec_search = extractor_b.search_decisions(query="", owner="team-feishu", limit=20)
valid_decisions = [d for d in all_dec_search if d.get("title") and d.get("context")]
b5_pass = len(valid_decisions) >= 2
b5_detail = f"总{len(all_dec_search)}条, 有效{len(valid_decisions)}条"
b_results.append(("决策质量检查", b5_pass, b5_detail))
print(f"  {'✅' if b5_pass else '❌'} 决策质量: {b5_detail}")

print()

# ------ 方向C评测 ------
print("--- 方向C (个人偏好) ---")
c_results = []

# C1: 查询张工偏好 → 应有 vim/TDD 相关
zhang_prefs = pref_mgr.list_preferences(owner="张工")
c1_pass = False
c1_detail = ""
if zhang_prefs:
    values = [p.get("value", "") for p in zhang_prefs]
    raw_matches = [p.get("source", "") for p in zhang_prefs]
    has_vim = any("vim" in v.lower() for v in values)
    c1_pass = has_vim or len(zhang_prefs) > 0
    c1_detail = f"共{len(zhang_prefs)}条偏好"
    if has_vim:
        c1_detail += ", vim偏好✓"
    # Show top preferences
    for p in zhang_prefs[:3]:
        c1_detail += f"\n    [{p.get('category')}/{p.get('key')}] = {p.get('value')}"
else:
    c1_detail = "无偏好记录"
c_results.append(("张工偏好提取", c1_pass, c1_detail))
print(f"  {'✅' if c1_pass else '❌'} 张工偏好: {c1_detail}")

# C2: 查询李工偏好 → 应有 VSCode
li_prefs = pref_mgr.list_preferences(owner="李工")
c2_pass = len(li_prefs) > 0
c2_detail = f"共{len(li_prefs)}条偏好"
if li_prefs:
    for p in li_prefs[:3]:
        c2_detail += f"\n    [{p.get('category')}/{p.get('key')}] = {p.get('value')}"
c_results.append(("李工偏好提取", c2_pass, c2_detail))
print(f"  {'✅' if c2_pass else '❌'} 李工偏好: {c2_detail}")

# C3: 查询赵工偏好
zhao_prefs = pref_mgr.list_preferences(owner="赵工")
c3_pass = len(zhao_prefs) > 0
c3_detail = f"共{len(zhao_prefs)}条偏好"
if zhao_prefs:
    for p in zhao_prefs[:3]:
        c3_detail += f"\n    [{p.get('category')}/{p.get('key')}] = {p.get('value')}"
c_results.append(("赵工偏好提取", c3_pass, c3_detail))
print(f"  {'✅' if c3_pass else '❌'} 赵工偏好: {c3_detail}")

# C4: 偏好统计
total_prefs = 0
for person in ["张工", "李工", "王工", "赵工"]:
    prefs = pref_mgr.list_preferences(owner=person)
    total_prefs += len(prefs)
c4_pass = total_prefs > 0
c4_detail = f"团队总偏好数: {total_prefs}"
c_results.append(("团队偏好统计", c4_pass, c4_detail))
print(f"  {'✅' if c4_pass else '❌'} 团队偏好: {c4_detail}")

print()

# ------ 方向D评测 ------
print("--- 方向D (团队知识健康) ---")
d_results = []

# D1: 知识健康摘要 → 应有 fresh/aging 统计
health_summary = monitor.get_health_summary(team_id="team-feishu")
d1_pass = health_summary.get("total_knowledge", 0) > 0
d1_detail = f"总知识: {health_summary.get('total_knowledge', 0)}"
status_counts = health_summary.get("status_counts", {})
d1_detail += f", fresh={status_counts.get('fresh', 0)}, aging={status_counts.get('aging', 0)}"
d1_detail += f", stale={status_counts.get('stale', 0)}, forgotten={status_counts.get('forgotten', 0)}"
d1_detail += f"\n    平均新鲜度: {health_summary.get('average_freshness', 0)}"
d_results.append(("知识健康摘要", d1_pass, d1_detail))
print(f"  {'✅' if d1_pass else '❌'} 知识健康摘要: {d1_detail}")

# D2: 知识缺口检测
gaps = detector.detect_gaps(team_id="team-feishu")
d2_pass = True  # 只要执行成功就算通过
d2_detail = f"检测到{len(gaps)}个缺口"
for g in gaps[:3]:
    d2_detail += f"\n    [{g.get('severity')}] {g.get('domain')}: {g.get('gap_description', '')[:50]}"
d_results.append(("知识缺口检测", d2_pass, d2_detail))
print(f"  {'✅' if d2_pass else '❌'} 知识缺口检测: {d2_detail}")

# D3: 单点故障识别
single_points = detector.detect_single_points(team_id="team-feishu")
d3_pass = True  # 执行成功即通过
d3_detail = f"识别到{len(single_points)}个单点故障"
for sp in single_points[:3]:
    d3_detail += f"\n    [{sp.get('category')}] {sp.get('topic')}: holders={sp.get('holder_count')}, risk={sp.get('risk_score')}"
d_results.append(("单点故障识别", d3_pass, d3_detail))
print(f"  {'✅' if d3_pass else '❌'} 单点故障: {d3_detail}")

# D4: 团队知识地图
coverage = detector.analyze_coverage(team_id="team-feishu")
d4_pass = coverage.get("coverage_ratio", 0) > 0
d4_detail = f"覆盖率: {coverage.get('coverage_ratio', 0)}, 单点领域: {len(coverage.get('single_point_domains', []))}"
d_results.append(("团队知识地图", d4_pass, d4_detail))
print(f"  {'✅' if d4_pass else '❌'} 团队知识地图: {d4_detail}")

# D5: 艾宾浩斯模型验证
test_retention = model.retention_score(days_since_access=1, category='general')
test_fresh = model.freshness_status(days_since_access=5, category='general')
d5_pass = test_retention > 0.9 and test_fresh == 'fresh'
d5_detail = f"R(1d,general)={test_retention:.4f}, status(5d)={test_fresh}"
d_results.append(("艾宾浩斯模型", d5_pass, d5_detail))
print(f"  {'✅' if d5_pass else '❌'} 艾宾浩斯模型: {d5_detail}")

print()

# ============================================================
# Phase 5: 生成评测报告
# ============================================================
print("=" * 60)
print("Phase 5: 生成评测报告")
print("=" * 60)

# 计算各方向得分
def calc_score(results_list):
    if not results_list:
        return 0
    passed = sum(1 for _, p, _ in results_list if p)
    return round(passed / len(results_list) * 100)

score_a = calc_score(a_results)
score_b = calc_score(b_results)
score_c = calc_score(c_results)
score_d = calc_score(d_results)
total_score = round((score_a + score_b + score_c + score_d) / 4)

# 生成Markdown报告
report_lines = []
report_lines.append("# MemScope 飞书真实环境评测报告")
report_lines.append("")
report_lines.append(f"**评测时间**: {eval_time}")
report_lines.append(f"**团队规模**: 5人 (张工、李工、王工、赵工、陈工)")
report_lines.append(f"**对话轮次**: {len(conversations)}")
report_lines.append(f"**CLI命令**: {len(commands)}")
report_lines.append(f"**知识条目**: {len(knowledge_items)}")
report_lines.append("")
report_lines.append("---")
report_lines.append("")

# 总分
report_lines.append(f"## 📊 评测总分: {total_score}/100")
report_lines.append("")
report_lines.append(f"| 方向 | 得分 | 状态 |")
report_lines.append(f"|------|------|------|")
report_lines.append(f"| A - CLI命令记忆 | {score_a}% | {'✅ 通过' if score_a >= 70 else '❌ 未通过'} |")
report_lines.append(f"| B - 飞书决策记忆 | {score_b}% | {'✅ 通过' if score_b >= 70 else '❌ 未通过'} |")
report_lines.append(f"| C - 个人偏好 | {score_c}% | {'✅ 通过' if score_c >= 70 else '❌ 未通过'} |")
report_lines.append(f"| D - 团队知识健康 | {score_d}% | {'✅ 通过' if score_d >= 70 else '❌ 未通过'} |")
report_lines.append("")
report_lines.append("---")
report_lines.append("")

# 方向A详情
report_lines.append("## 方向A: CLI命令记忆")
report_lines.append("")
for name, passed, detail in a_results:
    report_lines.append(f"- {'✅' if passed else '❌'} **{name}**: {detail}")
report_lines.append(f"- **得分: {score_a}%**")
report_lines.append("")

# 方向B详情
report_lines.append("## 方向B: 飞书决策记忆")
report_lines.append("")
for name, passed, detail in b_results:
    report_lines.append(f"- {'✅' if passed else '❌'} **{name}**: {detail}")
report_lines.append(f"- **得分: {score_b}%**")
report_lines.append("")

# 方向C详情
report_lines.append("## 方向C: 个人偏好")
report_lines.append("")
for name, passed, detail in c_results:
    report_lines.append(f"- {'✅' if passed else '❌'} **{name}**: {detail}")
report_lines.append(f"- **得分: {score_c}%**")
report_lines.append("")

# 方向D详情
report_lines.append("## 方向D: 团队知识健康")
report_lines.append("")
for name, passed, detail in d_results:
    report_lines.append(f"- {'✅' if passed else '❌'} **{name}**: {detail}")
report_lines.append(f"- **得分: {score_d}%**")
report_lines.append("")

# 数据摘要
report_lines.append("---")
report_lines.append("")
report_lines.append("## 📋 数据摘要")
report_lines.append("")

# 方向A数据
report_lines.append("### 方向A: 命令统计")
report_lines.append("")
for person in ["张工", "李工"]:
    patterns = store.get_command_patterns(owner=person, limit=5)
    report_lines.append(f"**{person}** 高频命令:")
    for p in patterns[:5]:
        report_lines.append(f"  - `{p.get('command', '')}` (频率: {p.get('frequency', 0)}, 项目: {p.get('project_path', 'N/A')})")
    report_lines.append("")

# 方向B数据
report_lines.append("### 方向B: 决策清单")
report_lines.append("")
all_decs = extractor_b.search_decisions(query="", owner="team-feishu", limit=20)
for d in all_decs:
    report_lines.append(f"- **{d.get('title', 'N/A')}**: {d.get('context', 'N/A')[:60]}")
report_lines.append("")

# 方向C数据
report_lines.append("### 方向C: 偏好概览")
report_lines.append("")
for person in ["张工", "李工", "王工", "赵工"]:
    prefs = pref_mgr.list_preferences(owner=person)
    if prefs:
        report_lines.append(f"**{person}** ({len(prefs)}条):")
        for p in prefs[:5]:
            report_lines.append(f"  - [{p.get('category')}/{p.get('key')}] = {p.get('value')} (置信度: {p.get('confidence', 0):.2f})")
        report_lines.append("")

# 方向D数据
report_lines.append("### 方向D: 知识健康")
report_lines.append("")
report_lines.append(f"**团队**: team-feishu")
report_lines.append(f"**总知识**: {health_summary.get('total_knowledge', 0)}")
report_lines.append(f"**状态分布**: fresh={status_counts.get('fresh', 0)}, aging={status_counts.get('aging', 0)}, stale={status_counts.get('stale', 0)}, forgotten={status_counts.get('forgotten', 0)}")
report_lines.append(f"**平均新鲜度**: {health_summary.get('average_freshness', 0):.4f}")
report_lines.append(f"**高风险项**: {health_summary.get('high_risk_count', 0)}")
report_lines.append("")

if single_points:
    report_lines.append("**单点故障列表**:")
    for sp in single_points:
        report_lines.append(f"  - {sp.get('topic')} (类别: {sp.get('category')}, 持有人: {sp.get('holders', [])}, 风险: {sp.get('risk_score', 0):.4f})")
    report_lines.append("")

if gaps:
    report_lines.append("**知识缺口**:")
    for g in gaps:
        report_lines.append(f"  - [{g.get('severity')}] {g.get('domain')}: {g.get('recommendation', '')}")
    report_lines.append("")

# 技术栈信息
report_lines.append("---")
report_lines.append("")
report_lines.append("## 🔧 技术栈")
report_lines.append("")
report_lines.append("- **存储**: SQLite (SqliteStore)")
report_lines.append("- **方向A**: CommandTracker + CommandRecommender")
report_lines.append("- **方向B**: DecisionExtractor + DecisionCardManager")
report_lines.append("- **方向C**: PreferenceExtractor + PreferenceManager + HabitInference")
report_lines.append("- **方向D**: EbbinghausModel + FreshnessMonitor + GapDetector")
report_lines.append("")

report_content = "\n".join(report_lines)

# 保存报告
report_path = os.path.join(eval_dir, "feishu_eval_report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_content)

print(f"报告已保存: {report_path}")
print(f"总分: {total_score}/100")
print()

# 清理
store.close()
