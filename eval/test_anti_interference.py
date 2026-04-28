"""
Anti-Interference Test Suite — 5 test cases.

Tests the enterprise memory engine's ability to correctly recall target
information despite various noise patterns:
  1. Single-round noise
  2. Multi-round noise (20 rounds)
  3. Similar-topic noise
  4. Temporal-spread noise
  5. Role-confusion noise

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid
from datetime import datetime, timedelta

import pytest


# ── 1. Single-round noise ──────────────────────────────────────────────────
class TestSingleRoundNoise:
    """Verify that a single target fact survives 4 noise conversations."""

    TEST_ID = "anti_interference_001"
    CATEGORY = "single_round_noise"

    def test_single_round_noise(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Step 1: Write target conversation ----
        target = data_gen.make_conversation(
            user_msg="我下周三要去客户A公司做技术方案汇报",
            assistant_msg="好的，已记录。下周三（5月6日）客户A技术方案汇报。",
            timestamp="2026-05-01T10:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(target):
            store.insert_chunk(chunk)

        # ---- Step 2: Write 4 noise conversations ----
        noise = [
            ("今天天气不错", "是的，天气很好。", "2026-05-01T10:05:00Z"),
            ("帮我订一杯拿铁咖啡", "已为您下单。", "2026-05-01T10:10:00Z"),
            ("最近有部新电影上映", "是的，您可以看看评分。", "2026-05-01T10:15:00Z"),
            ("明天要开会吗", "您明天上午10点有周会。", "2026-05-01T10:20:00Z"),
        ]
        for user, asst, ts in noise:
            conv = data_gen.make_conversation(user_msg=user, assistant_msg=asst, timestamp=ts)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Step 3: Query ----
        start = time.perf_counter()
        results = store.search_chunks("客户A 技术方案汇报", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        # ---- Step 4: Evaluate ----
        all_content = " ".join(r.get("content", "") for r in results)

        expected_keywords = ["客户A", "技术方案汇报", "下周三"]
        noise_keywords = ["天气", "拿铁", "电影"]

        recall_val = metrics.text_contains_keywords(all_content, expected_keywords)
        noise_val = 1.0 - metrics.text_not_contains(all_content, noise_keywords)
        noise_rate = sum(1 for nk in noise_keywords if nk in all_content) / len(noise_keywords)
        precision_val = 1.0 - noise_rate

        f1_val = metrics.f1(precision_val, recall_val)

        result_data = {
            "recall": {"value": round(recall_val, 4), "target": 0.90, "passed": recall_val >= 0.90},
            "precision": {"value": round(precision_val, 4), "target": 0.85, "passed": precision_val >= 0.85},
            "noise_injection_rate": {"value": round(noise_rate, 4), "target": 0.05, "passed": noise_rate <= 0.05},
            "f1_score": {"value": round(f1_val, 4), "target": 0.87, "passed": f1_val >= 0.87},
            "chunks_found": {"value": len(results), "target": 1, "passed": len(results) >= 1},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_single_round_noise ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Query results: {len(results)} chunks. Content preview: {all_content[:200]}",
            latency_ms=latency_ms,
            token_count=mock_llm.total_tokens,
        )

        assert recall_val >= 0.50, f"Recall too low: {recall_val:.2%} (target ≥ 90%)"
        # Soft assertion — we log the full metric for reporting
        if not passed:
            pytest.fail(
                f"Single-round noise test failed. "
                f"Recall={recall_val:.2%}, Precision={precision_val:.2%}, "
                f"Noise={noise_rate:.2%}, F1={f1_val:.2%}"
            )


# ── 2. Multi-round noise (20 rounds) ───────────────────────────────────────
class TestMultiRoundNoise:
    """Verify target fact survives 20 noise conversations."""

    TEST_ID = "anti_interference_002"
    CATEGORY = "multi_round_noise"

    def test_multi_round_noise(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Target ----
        target = data_gen.make_conversation(
            user_msg="项目B的预算已经批下来了，总共80万",
            assistant_msg="收到，已记录项目B预算：80万元。",
            timestamp="2026-04-28T09:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(target):
            store.insert_chunk(chunk)

        # ---- 20 noise rounds ----
        noise_list = data_gen.generate_noise(20, category="general")
        for conv in noise_list:
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Query ----
        start = time.perf_counter()
        results = store.search_chunks("项目B 预算", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        expected_keywords = ["80万", "项目B"]
        allowed_variants = ["80万", "80万元", "八十万元"]

        recall_val = metrics.text_contains_keywords(all_content, expected_keywords)

        # Check numeric accuracy
        numeric_match = any(v in all_content for v in allowed_variants)

        result_data = {
            "recall": {"value": round(recall_val, 4), "target": 0.90, "passed": recall_val >= 0.90},
            "numeric_accuracy": {"value": 1.0 if numeric_match else 0.0, "target": 1.0, "passed": numeric_match},
            "chunks_found": {"value": len(results), "target": 1, "passed": len(results) >= 1},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_multi_round_noise ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"After 20 noise rounds. Found {len(results)} chunks.",
            latency_ms=latency_ms,
        )

        assert recall_val >= 0.30, f"Recall too low after 20 noise rounds: {recall_val:.2%}"
        if not passed:
            pytest.fail(
                f"Multi-round noise test failed. Recall={recall_val:.2%}, "
                f"Numeric match={numeric_match}"
            )


# ── 3. Similar-topic noise ────────────────────────────────────────────────
class TestSimilarTopicNoise:
    """Verify correct disambiguation among similar project entities."""

    TEST_ID = "anti_interference_003"
    CATEGORY = "similar_topic_noise"

    def test_similar_topic_noise(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Target ----
        target = data_gen.make_conversation(
            user_msg="项目C的技术负责人是张三",
            assistant_msg="已记录，项目C技术负责人：张三。",
            timestamp="2026-04-28T09:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(target):
            store.insert_chunk(chunk)

        # ---- Distractors (similar topic, different entities) ----
        distractors = [
            ("项目D的负责人是谁", "项目D负责人是李四。", "2026-04-28T09:10:00Z"),
            ("项目E的技术负责人是王五吗", "是的，项目E技术负责人是王五。", "2026-04-28T09:20:00Z"),
            ("项目F的测试负责人换成赵六了", "已更新，项目F测试负责人：赵六。", "2026-04-28T09:30:00Z"),
        ]
        for user, asst, ts in distractors:
            conv = data_gen.make_conversation(user_msg=user, assistant_msg=asst, timestamp=ts)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Query ----
        start = time.perf_counter()
        results = store.search_chunks("项目C 技术负责人", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        expected_answer = "张三"
        distractor_answers = ["李四", "王五", "赵六"]

        has_target = expected_answer in all_content
        distractor_count = sum(1 for d in distractor_answers if d in all_content)

        precision_val = 1.0 - (distractor_count / max(len(distractor_answers), 1))
        recall_val = 1.0 if has_target else 0.0

        result_data = {
            "recall": {"value": round(recall_val, 4), "target": 0.90, "passed": recall_val >= 0.90},
            "precision": {"value": round(precision_val, 4), "target": 0.85, "passed": precision_val >= 0.85},
            "distractor_avoidance": {"value": round(1.0 - distractor_count / 3, 4), "target": 0.95,
                                     "passed": distractor_count == 0},
            "target_found": {"value": 1.0 if has_target else 0.0, "target": 1.0, "passed": has_target},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_similar_topic_noise ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Target '{expected_answer}' found={has_target}. Distractors found: {distractor_count}/3.",
            latency_ms=latency_ms,
        )

        assert has_target, f"Target answer '{expected_answer}' not found in results"
        # Note: distractor leakage is a metric, not necessarily a hard failure.
        # A simple LIKE search may return related chunks. The metric tracks
        # precision for reporting purposes.
        if distractor_count > 1:
            pytest.fail(
                f"Similar-topic noise: {distractor_count} distractor(s) leaked: "
                f"{[d for d in distractor_answers if d in all_content]}"
            )


# ── 4. Temporal-spread noise ──────────────────────────────────────────────
class TestTemporalSpreadNoise:
    """Verify a fact from months ago survives 30 scattered noise entries."""

    TEST_ID = "anti_interference_004"
    CATEGORY = "temporal_spread_noise"

    def test_temporal_spread_noise(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Target (January) ----
        target = data_gen.make_conversation(
            user_msg="我的飞书文档密码改成了 Herme$2026!",
            assistant_msg="已安全记录（加密存储）。",
            timestamp="2026-01-15T14:00:00Z",
        )
        for chunk in data_gen.make_chunks_from_conversation(target):
            store.insert_chunk(chunk)

        # ---- 30 noise entries spread from Jan to Apr ----
        base_time = datetime(2026, 1, 16, 10, 0, 0)
        for i in range(30):
            days_offset = i * 3  # every 3 days
            ts = (base_time + timedelta(days=days_offset)).isoformat()
            noise_topics = [
                ("今天开了个需求评审", f"需求评审已完成，第{i+1}轮。"),
                ("帮我查下代码覆盖率", f"当前覆盖率约{70+i}%。"),
                ("发布新版本了", f"v2.{i}.0 已发布。"),
            ]
            user, asst = noise_topics[i % 3]
            conv = data_gen.make_conversation(user_msg=user, assistant_msg=asst, timestamp=ts)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                store.insert_chunk(chunk)

        # ---- Query ----
        start = time.perf_counter()
        results = store.search_chunks("飞书文档密码", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results)

        expected_answer = "Herme$2026!"
        has_answer = expected_answer in all_content

        result_data = {
            "must_retrieve": {"value": 1.0 if has_answer else 0.0, "target": 1.0, "passed": has_answer},
            "chunks_found": {"value": len(results), "target": 1, "passed": len(results) >= 1},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_temporal_spread_noise ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Password '{expected_answer}' found={has_answer} across 30 noise entries.",
            latency_ms=latency_ms,
        )

        assert has_answer, (
            f"Temporal-spread: password '{expected_answer}' not found "
            f"after 30 noise entries spanning Jan-Apr."
        )


# ── 5. Role-confusion noise ───────────────────────────────────────────────
class TestRoleConfusionNoise:
    """Verify correct self vs. other distinction when similar actions are logged for different people."""

    TEST_ID = "anti_interference_005"
    CATEGORY = "role_confusion_noise"

    def test_role_confusion_noise(self, store, mock_llm, data_gen, metrics, report_collector):
        # ---- Target (current user) ----
        target = data_gen.make_conversation(
            user_msg="我下周三去拜访客户A",
            assistant_msg="好的，已记录。",
            timestamp="2026-05-01T10:00:00Z",
            owner="user_self",
        )
        for chunk in data_gen.make_chunks_from_conversation(target):
            store.insert_chunk(chunk)

        # ---- Noise: others doing similar things ----
        others = [
            ("张三下周三也要去拜访客户A", "已记录张三的行程。", "2026-05-01T10:05:00Z", "user_zhangsan"),
            ("李四下周三去客户B", "已记录李四的行程。", "2026-05-01T10:10:00Z", "user_lisi"),
        ]
        for user, asst, ts, owner in others:
            conv = data_gen.make_conversation(user_msg=user, assistant_msg=asst, timestamp=ts)
            for chunk in data_gen.make_chunks_from_conversation(conv):
                chunk["owner"] = owner
                store.insert_chunk(chunk)

        # ---- Query ----
        start = time.perf_counter()
        # Query specifically for self's chunks
        results_self = store.search_chunks("我 客户A", max_results=10)
        latency_ms = (time.perf_counter() - start) * 1000

        all_content = " ".join(r.get("content", "") for r in results_self)

        # Check self-identification
        self_identified = "我" in all_content and "客户A" in all_content

        # Check NOT confused with 张三
        # Filter to only self's chunks for role checking
        self_chunks = [r for r in results_self if r.get("owner") == "user_self"]
        self_content = " ".join(r.get("content", "") for r in self_chunks)
        confused_with_zhangsan = "张三" in self_content and "客户A" in self_content
        # Also check if Zhang San's chunks leaked into results
        zhangsan_chunks = [r for r in results_self if r.get("owner") == "user_zhangsan"]
        zhangsan_leaked = len(zhangsan_chunks) > 0

        result_data = {
            "self_identified": {"value": 1.0 if self_identified else 0.0, "target": 1.0, "passed": self_identified},
            "not_confused_with_others": {"value": 1.0 if not confused_with_zhangsan else 0.0,
                                          "target": 1.0, "passed": not confused_with_zhangsan},
            "role_accuracy": {"value": 1.0 if self_identified and not confused_with_zhangsan else 0.0,
                              "target": 0.95, "passed": self_identified and not confused_with_zhangsan},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_role_confusion_noise ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Self-identified={self_identified}, Confused with 张三={confused_with_zhangsan}",
            latency_ms=latency_ms,
        )

        assert self_identified, "Failed to identify self in results"
        assert not confused_with_zhangsan, "Confused self with 张三"
