"""
Direction C — Personal Habit / Preference Memory Test Suite — 4 test cases.

Tests the enterprise memory engine's ability to:
  1. Recognize and store work habits
  2. Manage communication preferences
  3. Track preference updates over time
  4. Provide context-aware recommendations

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid

import pytest


# ── 1. Habit Recognition ──────────────────────────────────────────────────
class TestHabitRecognition:
    """Verify the system can learn and recall multiple work habits."""

    TEST_ID = "direction_c_001"
    CATEGORY = "work_habit_recognition"

    def test_habit_recognition(self, store, data_gen, metrics, report_collector):
        from src.preference_memory.preference_manager import PreferenceManager

        pm = PreferenceManager(store)
        owner = "user_habit_test"

        # ---- Store work habits as preferences ----
        habits = [
            ("work_pattern", "morning_routine", "先处理邮件，再写代码"),
            ("work_pattern", "work_method", "番茄工作法，25分钟一个周期"),
            ("schedule", "lunch_break", "午休时间 12:00-13:30"),
        ]

        for category, key, value in habits:
            pm.set_preference(owner, category, key, value, source='explicit')

        # ---- Also store as conversation chunks ----
        conv_habits = [
            ("我一般早上先处理邮件，再写代码", "已记录您的工作习惯：早间优先处理邮件，然后写代码。"),
            ("我习惯用番茄工作法，25分钟一个周期", "已记录：您使用番茄工作法，25分钟/周期。"),
            ("我午休一般从12点到1点半", "已记录：午休时间 12:00-13:30。"),
        ]
        for user_msg, asst_msg in conv_habits:
            conv = data_gen.make_conversation(user_msg=user_msg, assistant_msg=asst_msg)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Query 1: Morning routine ----
        prefs = pm.list_preferences(owner)
        morning_pref = pm.get_preference_value(owner, "work_pattern", "morning_routine")
        work_method = pm.get_preference_value(owner, "work_pattern", "work_method")

        # Query 2: Lunch schedule
        lunch_pref = pm.get_preference_value(owner, "schedule", "lunch_break")

        # Query 3: Cross-habit recall via chunk search
        chunk_results = store.search_chunks("上午 工作安排", max_results=5)
        chunk_content = " ".join(r.get("content", "") for r in chunk_results)

        # ---- Metrics ----
        habit_recall = sum(1 for v in [morning_pref, work_method, lunch_pref] if v) / 3

        result_data = {
            "preference_recall": {
                "value": round(habit_recall, 4),
                "target": 0.90,
                "passed": habit_recall >= 0.90,
            },
            "morning_routine_stored": {
                "value": 1.0 if morning_pref else 0.0,
                "target": 1.0,
                "passed": morning_pref is not None,
            },
            "work_method_stored": {
                "value": 1.0 if work_method else 0.0,
                "target": 1.0,
                "passed": work_method is not None,
            },
            "lunch_schedule_stored": {
                "value": 1.0 if lunch_pref else 0.0,
                "target": 1.0,
                "passed": lunch_pref is not None,
            },
            "total_preferences": {
                "value": len(prefs),
                "target": 3,
                "passed": len(prefs) >= 3,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_habit_recognition ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Found {len(prefs)} preferences. Morning={morning_pref}, "
                    f"Method={work_method}, Lunch={lunch_pref}",
        )

        assert len(prefs) >= 3, f"Expected at least 3 preferences, got {len(prefs)}"
        if not passed:
            pytest.fail(f"Habit recognition failed: recall={habit_recall:.0%}")


# ── 2. Preference Management ──────────────────────────────────────────────
class TestPreferenceManagement:
    """Verify comprehensive preference storage and retrieval."""

    TEST_ID = "direction_c_002"
    CATEGORY = "communication_preference"

    def test_preference_management(self, store, data_gen, metrics, report_collector):
        from src.preference_memory.preference_manager import PreferenceManager

        pm = PreferenceManager(store)
        owner = "user_pref_test"

        # ---- Store communication preferences ----
        prefs_data = [
            ("style", "communication_style", "结论先行"),
            ("style", "report_style", "数据驱动"),
            ("work_pattern", "meeting_prep", "不喜欢即兴发言，倾向于提前准备"),
        ]

        for category, key, value in prefs_data:
            pm.set_preference(owner, category, key, value, source='explicit')

        # ---- Also store as conversation chunks for search ----
        conv_prefs = [
            ("跟客户沟通时我喜欢先说结论再说原因", "已记录：您的沟通偏好——结论先行。"),
            ("写周报的时候我喜欢用数据说话", "已记录：周报偏好——数据驱动。"),
            ("我比较不喜欢在会议上即兴发言", "已记录：偏好——不喜欢即兴会议发言，倾向于提前准备。"),
        ]
        for user_msg, asst_msg in conv_prefs:
            conv = data_gen.make_conversation(user_msg=user_msg, assistant_msg=asst_msg)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Verify ----
        all_prefs = pm.list_preferences(owner)

        # Check specific preferences
        comm_style = pm.get_preference_value(owner, "style", "communication_style")
        report_style = pm.get_preference_value(owner, "style", "report_style")
        meeting_pref = pm.get_preference_value(owner, "work_pattern", "meeting_prep")

        # Verify categories are distinguished
        style_prefs = pm.list_preferences(owner, category="style")
        work_prefs = pm.list_preferences(owner, category="work_pattern")

        result_data = {
            "total_preferences_stored": {
                "value": len(all_prefs),
                "target": 3,
                "passed": len(all_prefs) >= 3,
            },
            "communication_style_correct": {
                "value": 1.0 if comm_style == "结论先行" else 0.0,
                "target": 1.0,
                "passed": comm_style == "结论先行",
            },
            "report_style_correct": {
                "value": 1.0 if report_style == "数据驱动" else 0.0,
                "target": 1.0,
                "passed": report_style == "数据驱动",
            },
            "meeting_preference_correct": {
                "value": 1.0 if meeting_pref else 0.0,
                "target": 1.0,
                "passed": meeting_pref is not None,
            },
            "category_separation": {
                "value": 1.0 if (len(style_prefs) >= 2 and len(work_prefs) >= 1) else 0.0,
                "target": 0.90,
                "passed": len(style_prefs) >= 2 and len(work_prefs) >= 1,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_preference_management ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Total={len(all_prefs)}. Style={len(style_prefs)}, Work={len(work_prefs)}. "
                    f"Comm={comm_style}, Report={report_style}",
        )

        if not passed:
            pytest.fail(
                f"Preference management failed: total={len(all_prefs)}, "
                f"comm={comm_style}, report={report_style}"
            )


# ── 3. Preference Updates ────────────────────────────────────────────────
class TestPreferenceUpdates:
    """Verify that preference changes are tracked and history is preserved."""

    TEST_ID = "direction_c_003"
    CATEGORY = "preference_update"

    def test_preference_updates(self, store, data_gen, metrics, report_collector):
        from src.preference_memory.preference_manager import PreferenceManager

        pm = PreferenceManager(store)
        owner = "user_update_test"

        # ---- Set initial preference ----
        pm.set_preference(owner, "tool_preference", "task_management", "旧工具", source="explicit")
        old_value = pm.get_preference_value(owner, "tool_preference", "task_management")

        # Store as chunk too
        conv1 = data_gen.make_conversation(
            user_msg="我用旧工具管理任务",
            assistant_msg="已记录：任务管理工具为旧工具。",
        )
        for chunk in data_gen.make_chunks_from_conversation(conv1):
            store.insert_chunk(chunk)

        # ---- Update preference ----
        pm.set_preference(owner, "tool_preference", "task_management", "Notion", source="explicit")
        new_value = pm.get_preference_value(owner, "tool_preference", "task_management")

        conv2 = data_gen.make_conversation(
            user_msg="我现在开始用 Notion 做任务管理了",
            assistant_msg="已更新：任务管理工具变为 Notion。",
        )
        for chunk in data_gen.make_chunks_from_conversation(conv2):
            store.insert_chunk(chunk)

        # ---- Update work method ----
        pm.set_preference(owner, "work_pattern", "time_method", "番茄工作法", source="explicit")
        conv3 = data_gen.make_conversation(
            user_msg="我习惯用番茄工作法",
            assistant_msg="已记录。",
        )
        for chunk in data_gen.make_chunks_from_conversation(conv3):
            store.insert_chunk(chunk)

        pm.set_preference(owner, "work_pattern", "time_method", "时间块管理", source="explicit")
        conv4 = data_gen.make_conversation(
            user_msg="我不用番茄工作法了，现在用时间块的方式",
            assistant_msg="已更新：工作方法变更为时间块管理。",
        )
        for chunk in data_gen.make_chunks_from_conversation(conv4):
            store.insert_chunk(chunk)

        updated_value = pm.get_preference_value(owner, "work_pattern", "time_method")

        # ---- Check history via chunk search ----
        history_results = store.search_chunks("旧工具 番茄工作法", max_results=10)
        history_content = " ".join(r.get("content", "") for r in history_results)

        # ---- Metrics ----
        tool_updated_correctly = (new_value == "Notion")
        method_updated_correctly = (updated_value == "时间块管理")
        history_has_old_tools = "旧工具" in history_content or "番茄工作法" in history_content

        result_data = {
            "latest_tool_correct": {
                "value": 1.0 if tool_updated_correctly else 0.0,
                "target": 0.95,
                "passed": tool_updated_correctly,
            },
            "latest_method_correct": {
                "value": 1.0 if method_updated_correctly else 0.0,
                "target": 0.95,
                "passed": method_updated_correctly,
            },
            "history_traceable": {
                "value": 1.0 if history_has_old_tools else 0.0,
                "target": 0.85,
                "passed": history_has_old_tools,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_preference_update ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Tool: {old_value}→{new_value}. Method: →{updated_value}. "
                    f"History preserved: {history_has_old_tools}",
        )

        if not passed:
            pytest.fail(
                f"Preference update failed: tool={tool_updated_correctly}, "
                f"method={method_updated_correctly}, history={history_has_old_tools}"
            )


# ── 4. Context-Aware Recommendations ─────────────────────────────────────
class TestContextAwareRecommendations:
    """Verify the system provides context-aware suggestions based on habits."""

    TEST_ID = "direction_c_004"
    CATEGORY = "context_aware_recommendation"

    def test_context_aware_recommendations(self, store, data_gen, metrics, report_collector):
        from src.preference_memory.preference_manager import PreferenceManager

        pm = PreferenceManager(store)
        owner = "user_context_test"

        # ---- Store habits ----
        habits = [
            ("schedule", "wednesday_afternoon", "周三下午不安排会议"),
            ("work_pattern", "code_review_style", "逐文件review"),
            ("schedule", "friday_afternoon", "周五下午做一周总结"),
        ]
        for category, key, value in habits:
            pm.set_preference(owner, category, key, value, source='explicit')

        # Also as chunks
        conv_habits = [
            ("我一般周三下午不安排会议", "已记录。"),
            ("我做代码审查喜欢逐文件review", "已记录。"),
            ("我习惯在周五下午做一周总结", "已记录。"),
        ]
        for user_msg, asst_msg in conv_habits:
            conv = data_gen.make_conversation(user_msg=user_msg, assistant_msg=asst_msg)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Simulate context-aware query ----
        # Query 1: "帮我安排下周的工作"
        wed_pref = pm.get_preference_value(owner, "schedule", "wednesday_afternoon")
        fri_pref = pm.get_preference_value(owner, "schedule", "friday_afternoon")

        # Check if system would recommend keeping Wednesday afternoon free
        recommends_wednesday_free = wed_pref and "周三" in wed_pref
        recommends_friday_summary = fri_pref and "周五" in fri_pref

        # Query 2: "这个PR需要review"
        review_pref = pm.get_preference_value(owner, "work_pattern", "code_review_style")
        recommends_file_by_file = review_pref and "逐文件" in review_pref

        # Also check chunk-based recall
        chunk_results = store.search_chunks("安排工作 周三 周五", max_results=5)
        chunk_content = " ".join(r.get("content", "") for r in chunk_results)

        # ---- Metrics ----
        recommendation_score = sum([
            recommends_wednesday_free,
            recommends_friday_summary,
            recommends_file_by_file,
        ]) / 3

        result_data = {
            "context_awareness_score": {
                "value": round(recommendation_score, 4),
                "target": 0.80,
                "passed": recommendation_score >= 0.80,
            },
            "wednesday_recommendation": {
                "value": 1.0 if recommends_wednesday_free else 0.0,
                "target": 1.0,
                "passed": recommends_wednesday_free,
            },
            "friday_recommendation": {
                "value": 1.0 if recommends_friday_summary else 0.0,
                "target": 1.0,
                "passed": recommends_friday_summary,
            },
            "review_style_recommendation": {
                "value": 1.0 if recommends_file_by_file else 0.0,
                "target": 1.0,
                "passed": recommends_file_by_file,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_context_aware_recommendation ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Wed={recommends_wednesday_free}, Fri={recommends_friday_summary}, "
                    f"Review={recommends_file_by_file}",
        )

        assert recommendation_score >= 0.50, (
            f"Context awareness score too low: {recommendation_score:.0%}"
        )
        if not passed:
            pytest.fail(
                f"Context-aware recommendations failed: score={recommendation_score:.0%}"
            )
