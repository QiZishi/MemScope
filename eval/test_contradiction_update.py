"""
Contradiction Update Test Suite — 5 test cases.

Tests the enterprise memory engine's ability to handle contradictory
or updating information:
  1. Direct override
  2. Partial update
  3. Temporal contradiction (same fact, different times)
  4. Multi-entity contradiction
  5. Cancellation / retraction

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid

import pytest


# ── 1. Direct Override ─────────────────────────────────────────────────────
class TestDirectOverride:
    """Verify that a newer value overrides an older value for the same key."""

    TEST_ID = "contradiction_001"
    CATEGORY = "direct_override"

    def test_direct_override(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Write old value ----
        old = data_gen.make_conversation(
            user_msg="我的工位号是 A-305",
            assistant_msg="已记录，工位号：A-305。",
            timestamp="2026-04-01T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(old):
            store.insert_chunk(chunk)

        # ---- Write new value (contradiction) ----
        new = data_gen.make_conversation(
            user_msg="我搬到新工位了，现在是 B-201",
            assistant_msg="已更新，工位号：B-201。旧工位 A-305 已归档。",
            timestamp="2026-05-01T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(new):
            store.insert_chunk(chunk)

        # ---- Query: current value ----
        start = time.perf_counter()
        results = store.search_chunks("工位号", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        # Latest value should be B-201
        has_new = "B-201" in all_content
        # Old value A-305 should still exist in history
        has_old = "A-305" in all_content

        # Determine which is "newer" by checking timestamps
        timestamps = [r.get("createdAt", 0) for r in results]
        max_ts = max(timestamps) if timestamps else 0
        min_ts = min(timestamps) if timestamps else 0

        # The newest chunk should contain B-201
        newest_chunks = [r for r in results if r.get("createdAt", 0) == max_ts]
        newest_content = " ".join(r.get("content", "") for r in newest_chunks)
        latest_is_correct = "B-201" in newest_content

        result_data = {
            "latest_value_accuracy": {
                "value": 1.0 if has_new and latest_is_correct else 0.0,
                "target": 0.95,
                "passed": has_new and latest_is_correct,
            },
            "history_preserved": {
                "value": 1.0 if has_old else 0.0,
                "target": 0.90,
                "passed": has_old,
            },
            "chunks_found": {"value": len(results), "target": 2, "passed": len(results) >= 2},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_direct_override ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"New value B-201 found={has_new}, Old value A-305 preserved={has_old}",
            latency_ms=latency_ms,
        )

        assert has_new, "New value B-201 not found"
        if not passed:
            pytest.fail(
                f"Direct override failed: new={has_new}, old_preserved={has_old}, "
                f"latest_correct={latest_is_correct}"
            )


# ── 2. Partial Update ─────────────────────────────────────────────────────
class TestPartialUpdate:
    """Verify that partial updates (add/remove members) are correctly handled."""

    TEST_ID = "contradiction_002"
    CATEGORY = "partial_update"

    def test_partial_update(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Original team ----
        old = data_gen.make_conversation(
            user_msg="项目G的成员有张三、李四、王五",
            assistant_msg="已记录项目G成员：张三、李四、王五。",
            timestamp="2026-04-01T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(old):
            store.insert_chunk(chunk)

        # ---- Update (王五 leaves, 赵六 joins) ----
        new = data_gen.make_conversation(
            user_msg="王五退出项目G了，赵六加入了",
            assistant_msg="已更新，项目G成员变更为：张三、李四、赵六。",
            timestamp="2026-04-15T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(new):
            store.insert_chunk(chunk)

        # ---- Query ----
        start = time.perf_counter()
        results = store.search_chunks("项目G 成员", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        expected_members = ["张三", "李四", "赵六"]
        removed_members = ["王五"]

        # The LATEST result should contain the updated members
        latest_content = results[0].get("content", "") if results else ""

        # Check expected members are present in LATEST response
        member_recall = metrics.text_contains_keywords(latest_content, expected_members)

        # In the LATEST chunk, removed member should NOT appear
        has_removed = any(m in latest_content for m in removed_members)

        # Check history preserved (old message still in DB)
        history_preserved = "王五" in all_content

        result_data = {
            "correct_members_recall": {
                "value": round(member_recall, 4),
                "target": 0.95,
                "passed": member_recall >= 0.95,
            },
            "removed_member_not_in_latest": {
                "value": 0.0 if has_removed else 1.0,
                "target": 1.0,
                "passed": not has_removed,
            },
            "history_preserved": {
                "value": 1.0 if history_preserved else 0.0,
                "target": 0.90,
                "passed": history_preserved,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_partial_update ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Members recall={member_recall:.0%}, removed-leaked={has_removed}",
            latency_ms=latency_ms,
        )

        if not passed:
            pytest.fail(
                f"Partial update failed: member_recall={member_recall:.0%}, "
                f"removed_leaked={has_removed}"
            )


# ── 3. Temporal Contradiction ─────────────────────────────────────────────
class TestTemporalContradiction:
    """Verify that multiple updates over time yield correct latest + history."""

    TEST_ID = "contradiction_003"
    CATEGORY = "temporal_contradiction"

    def test_temporal_contradiction(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- 3 versions of the same fact ----
        versions = [
            ("每周二下午3点我们团队有周会", "已记录：团队周会，每周二 15:00。", "2026-03-01T10:00:00Z"),
            ("周会改到每周四上午10点了", "已更新：团队周会改为每周四 10:00。", "2026-04-01T10:00:00Z"),
            ("周会又改回周二下午了，但是改到4点", "已更新：团队周会改为每周二 16:00。", "2026-04-15T10:00:00Z"),
        ]
        for user, asst, ts in versions:
            conv = data_gen.make_conversation(user_msg=user, assistant_msg=asst, timestamp=ts)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Query 1: Current time ----
        start = time.perf_counter()
        results = store.search_chunks("团队周会 时间", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        # Latest should be "周二 16:00" or "周二下午" with "4点"
        has_latest = ("16:00" in all_content or "4点" in all_content or
                      "周二" in all_content and "16" in all_content)

        # History should contain old versions
        history_has_tue15 = "15:00" in all_content
        history_has_thu10 = "10:00" in all_content

        # Count version changes
        version_mentions = sum([
            "15:00" in all_content,
            "10:00" in all_content,
            ("16:00" in all_content or "4点" in all_content),
        ])

        # Check temporal ordering — newest chunks should have latest info
        timestamps = [(r.get("createdAt", 0), r.get("content", "")) for r in results]
        timestamps.sort(key=lambda x: x[0], reverse=True)
        newest_content = timestamps[0][1] if timestamps else ""
        latest_is_newest = "16:00" in newest_content or "4点" in newest_content

        result_data = {
            "latest_value_correct": {
                "value": 1.0 if has_latest else 0.0,
                "target": 0.95,
                "passed": has_latest,
            },
            "history_preserved": {
                "value": 1.0 if (history_has_tue15 and history_has_thu10) else 0.5,
                "target": 0.90,
                "passed": history_has_tue15 and history_has_thu10,
            },
            "version_count_accuracy": {
                "value": round(min(version_mentions, 3) / 3, 4),
                "target": 0.90,
                "passed": version_mentions >= 2,
            },
            "temporal_sort_accuracy": {
                "value": 1.0 if latest_is_newest else 0.0,
                "target": 0.90,
                "passed": latest_is_newest,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_temporal_contradiction ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Versions found: {version_mentions}/3. Latest correct: {latest_is_newest}",
            latency_ms=latency_ms,
        )

        if not passed:
            pytest.fail(
                f"Temporal contradiction failed: latest={has_latest}, "
                f"history={history_has_tue15 and history_has_thu10}, "
                f"versions={version_mentions}"
            )


# ── 4. Multi-entity Contradiction ────────────────────────────────────────
class TestMultiEntityContradiction:
    """Verify partial update on one entity doesn't corrupt another."""

    TEST_ID = "contradiction_004"
    CATEGORY = "multi_entity_contradiction"

    def test_multi_entity_contradiction(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Original: two projects ----
        original = data_gen.make_conversation(
            user_msg="项目H预算50万，项目I预算30万",
            assistant_msg="已记录：项目H预算50万，项目I预算30万。",
            timestamp="2026-04-01T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(original):
            store.insert_chunk(chunk)

        # ---- Update only Project H ----
        update = data_gen.make_conversation(
            user_msg="项目H的预算追加到70万了",
            assistant_msg="已更新项目H预算为70万。项目I预算不变。",
            timestamp="2026-04-10T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(update):
            store.insert_chunk(chunk)

        # ---- Query both ----
        start = time.perf_counter()
        results_h = store.search_chunks("项目H 预算", max_results=10)
        results_i = store.search_chunks("项目I 预算", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        content_h = " ".join(r.get("content", "") for r in results_h)
        content_i = " ".join(r.get("content", "") for r in results_i)

        # Project H should now be 70万
        h_correct = "70万" in content_h
        # Project I should still be 30万
        i_correct = "30万" in content_i

        result_data = {
            "project_h_updated": {
                "value": 1.0 if h_correct else 0.0,
                "target": 0.95,
                "passed": h_correct,
            },
            "project_i_preserved": {
                "value": 1.0 if i_correct else 0.0,
                "target": 0.95,
                "passed": i_correct,
            },
            "partial_update_fidelity": {
                "value": 1.0 if (h_correct and i_correct) else 0.0,
                "target": 0.95,
                "passed": h_correct and i_correct,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_multi_entity_contradiction ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Project H correct={h_correct}, Project I preserved={i_correct}",
            latency_ms=latency_ms,
        )

        if not passed:
            pytest.fail(
                f"Multi-entity contradiction failed: H_updated={h_correct}, I_preserved={i_correct}"
            )


# ── 5. Cancellation / Retraction ─────────────────────────────────────────
class TestCancellation:
    """Verify that cancelled events are properly handled."""

    TEST_ID = "contradiction_005"
    CATEGORY = "cancel_retraction"

    def test_cancellation(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Create event ----
        create = data_gen.make_conversation(
            user_msg="帮我约下周一和客户A的会议",
            assistant_msg="已记录，下周一与客户A的会议。",
            timestamp="2026-04-28T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(create):
            store.insert_chunk(chunk)

        # ---- Cancel event ----
        cancel = data_gen.make_conversation(
            user_msg="下周一和客户A的会议取消了",
            assistant_msg="已取消该会议记录。",
            timestamp="2026-04-29T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(cancel):
            store.insert_chunk(chunk)

        # ---- Query: what's scheduled? ----
        start = time.perf_counter()
        results = store.search_chunks("下周一 安排 会议", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        # The cancellation should be reflected
        has_cancellation = "取消" in all_content

        # Check that the event creation is still in history
        has_original = "客户A" in all_content

        # The most recent mention should indicate cancellation
        timestamps = [(r.get("createdAt", 0), r.get("content", "")) for r in results]
        timestamps.sort(key=lambda x: x[0], reverse=True)
        newest_content = timestamps[0][1] if timestamps else ""
        latest_indicates_cancel = "取消" in newest_content

        result_data = {
            "cancellation_detected": {
                "value": 1.0 if has_cancellation else 0.0,
                "target": 0.90,
                "passed": has_cancellation,
            },
            "cancellation_in_latest": {
                "value": 1.0 if latest_indicates_cancel else 0.0,
                "target": 0.90,
                "passed": latest_indicates_cancel,
            },
            "original_event_preserved": {
                "value": 1.0 if has_original else 0.0,
                "target": 0.85,
                "passed": has_original,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_cancellation ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Cancel detected={has_cancellation}, latest_cancel={latest_indicates_cancel}",
            latency_ms=latency_ms,
        )

        if not passed:
            pytest.fail(
                f"Cancellation test failed: detected={has_cancellation}, "
                f"latest={latest_indicates_cancel}"
            )
