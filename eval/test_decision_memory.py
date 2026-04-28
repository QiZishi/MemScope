"""
Direction B — Decision Memory Test Suite — 4 test cases.

Tests the enterprise memory engine's ability to:
  1. Extract decisions from messages accurately
  2. Search decisions by keywords
  3. Push relevant decision cards
  4. Track decision lifecycle (record → overturn)

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid

import pytest


# ── 1. Decision Extraction ────────────────────────────────────────────────
class TestDecisionExtraction:
    """Verify the system can extract structured decisions from messages."""

    TEST_ID = "direction_b_001"
    CATEGORY = "decision_extraction"

    def test_decision_extraction(self, store, data_gen, metrics, report_collector):
        from decision_memory.decision_extractor import DecisionExtractor

        extractor = DecisionExtractor(store)

        # ---- Test messages with decision signals ----
        test_messages = [
            {
                "message": "经过讨论，我们决定采用React作为前端框架，因为团队React经验更丰富",
                "sender": "张明",
                "project_id": "proj_frontend",
                "channel_id": "ch_tech",
                "expected_contains": "React",
                "expected_rationale": "经验",
            },
            {
                "message": "最终确认使用PostgreSQL作为主数据库，原因是它支持JSON类型，更适合我们的场景",
                "sender": "李华",
                "project_id": "proj_backend",
                "channel_id": "ch_tech",
                "expected_contains": "PostgreSQL",
                "expected_rationale": "JSON",
            },
            {
                "message": "我们采用微服务架构，而不是单体架构。优点是可独立部署和扩展",
                "sender": "王芳",
                "project_id": "proj_arch",
                "channel_id": "ch_arch",
                "expected_contains": "微服务",
                "expected_rationale": "独立部署",
            },
            {
                "message": "同意使用Docker Compose做本地开发环境，否决了Vagrant方案",
                "sender": "赵刚",
                "project_id": "proj_devops",
                "channel_id": "ch_devops",
                "expected_contains": "Docker Compose",
                "expected_rationale": "",
            },
        ]

        extracted_count = 0
        correct_extractions = 0
        rationale_found = 0

        for tm in test_messages:
            decisions = extractor.extract_from_message(
                message=tm["message"],
                sender=tm["sender"],
                project_id=tm["project_id"],
                channel_id=tm["channel_id"],
            )
            if decisions:
                extracted_count += 1
                dec = decisions[0]
                decision_text = dec.get("decision", "")
                rationale_text = dec.get("rationale", "")

                if tm["expected_contains"] in decision_text or tm["expected_contains"] in dec.get("title", ""):
                    correct_extractions += 1

                if tm["expected_rationale"] and tm["expected_rationale"] in rationale_text:
                    rationale_found += 1
                elif not tm["expected_rationale"]:
                    rationale_found += 1  # No rationale expected, counts as OK

        # ---- Test conversation extraction ----
        conversation = [
            {"sender": "陈刚", "content": "前端框架大家建议用什么？React还是Vue？", "timestamp_ms": 1000},
            {"sender": "赵丽", "content": "我建议用React，生态更成熟", "timestamp_ms": 2000},
            {"sender": "陈刚", "content": "好的，那我们就定React了", "timestamp_ms": 3000},
        ]
        conv_decisions = extractor.extract_from_conversation(
            messages=conversation, project_id="proj_conv_test"
        )

        # ---- Metrics ----
        extraction_rate = extracted_count / len(test_messages) if test_messages else 0
        accuracy_rate = correct_extractions / len(test_messages) if test_messages else 0
        rationale_rate = rationale_found / len(test_messages) if test_messages else 0

        result_data = {
            "extraction_rate": {
                "value": round(extraction_rate, 4),
                "target": 0.75,
                "passed": extraction_rate >= 0.75,
            },
            "extraction_accuracy": {
                "value": round(accuracy_rate, 4),
                "target": 0.70,
                "passed": accuracy_rate >= 0.70,
            },
            "rationale_recall": {
                "value": round(rationale_rate, 4),
                "target": 0.60,
                "passed": rationale_rate >= 0.60,
            },
            "conversation_extraction": {
                "value": len(conv_decisions),
                "target": 1,
                "passed": len(conv_decisions) >= 1,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_decision_extraction ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Extracted {extracted_count}/{len(test_messages)} decisions, "
                    f"correct={correct_extractions}, rationale={rationale_found}, "
                    f"conv_decisions={len(conv_decisions)}",
        )

        assert extracted_count >= 3, f"Expected at least 3 extractions, got {extracted_count}"
        if not passed:
            pytest.fail(f"Decision extraction failed: rate={extraction_rate:.0%}, accuracy={accuracy_rate:.0%}")


# ── 2. Decision Search ────────────────────────────────────────────────────
class TestDecisionSearch:
    """Verify the system can store and search decisions by keywords."""

    TEST_ID = "direction_b_002"
    CATEGORY = "decision_search"

    def test_decision_search(self, store, data_gen, metrics, report_collector):
        from decision_memory.decision_extractor import DecisionExtractor

        extractor = DecisionExtractor(store)
        owner = "user_dec_search"

        # ---- Store decisions directly ----
        decisions_to_store = [
            {
                "title": "采用React前端框架",
                "decision": "经过团队讨论，决定使用React作为前端框架",
                "rationale": "团队React经验丰富，生态成熟",
                "project_id": "proj_frontend",
                "alternatives": json.dumps(["Vue", "Angular"]),
            },
            {
                "title": "使用PostgreSQL数据库",
                "decision": "确认使用PostgreSQL作为主数据库",
                "rationale": "支持JSON类型，性能优秀",
                "project_id": "proj_backend",
                "alternatives": json.dumps(["MySQL", "MongoDB"]),
            },
            {
                "title": "部署方案选择K8s",
                "decision": "采用Kubernetes进行容器编排部署",
                "rationale": "自动扩缩容，服务发现",
                "project_id": "proj_devops",
                "alternatives": json.dumps(["Docker Swarm", "Nomad"]),
            },
            {
                "title": "API设计采用RESTful",
                "decision": "API设计采用RESTful风格",
                "rationale": "团队熟悉，工具链完善",
                "project_id": "proj_backend",
                "alternatives": json.dumps(["GraphQL", "gRPC"]),
            },
        ]

        saved_ids = []
        for dec in decisions_to_store:
            did = store.insert_decision(
                owner=owner,
                title=dec["title"],
                project=dec.get("project_id"),
                context=dec["decision"],
                chosen=dec["rationale"],
                alternatives=dec.get("alternatives"),
                tags=json.dumps({"status": "active"}, ensure_ascii=False),
            )
            if did:
                saved_ids.append(did)

        # ---- Search by various keywords ----
        search_tests = [
            ("React", 1),
            ("PostgreSQL", 1),
            ("Kubernetes", 1),
            ("部署", 1),
            ("API", 1),
        ]

        search_results = {}
        for query, min_expected in search_tests:
            results = extractor.search_decisions(query=query, owner=owner)
            search_results[query] = len(results)

        # ---- Search by project ----
        frontend_decisions = extractor.get_project_decisions(
            project_id="proj_frontend", owner=owner
        )
        backend_decisions = extractor.get_project_decisions(
            project_id="proj_backend", owner=owner
        )

        # ---- Metrics ----
        all_saved = len(saved_ids) == len(decisions_to_store)
        search_pass_count = sum(
            1 for q, min_e in search_tests
            if search_results.get(q, 0) >= min_e
        )
        search_pass_rate = search_pass_count / len(search_tests)

        result_data = {
            "decisions_saved": {
                "value": len(saved_ids),
                "target": len(decisions_to_store),
                "passed": all_saved,
            },
            "search_pass_rate": {
                "value": round(search_pass_rate, 4),
                "target": 0.80,
                "passed": search_pass_rate >= 0.80,
            },
            "project_frontend_found": {
                "value": len(frontend_decisions),
                "target": 1,
                "passed": len(frontend_decisions) >= 1,
            },
            "project_backend_found": {
                "value": len(backend_decisions),
                "target": 2,
                "passed": len(backend_decisions) >= 2,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_decision_search ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Saved {len(saved_ids)} decisions. Search results: {search_results}. "
                    f"Frontend={len(frontend_decisions)}, Backend={len(backend_decisions)}",
        )

        assert all_saved, f"Expected all {len(decisions_to_store)} saved, got {len(saved_ids)}"
        assert search_pass_rate >= 0.80, f"Search pass rate too low: {search_pass_rate:.0%}"
        if not passed:
            pytest.fail("Decision search test failed")


# ── 3. Decision Cards ─────────────────────────────────────────────────────
class TestDecisionCards:
    """Verify the system can format and push relevant decision cards."""

    TEST_ID = "direction_b_003"
    CATEGORY = "decision_cards"

    def test_decision_cards(self, store, data_gen, metrics, report_collector):
        from decision_memory.decision_card import DecisionCardManager

        card_mgr = DecisionCardManager(store)
        owner = "user_dec_cards"

        # ---- Record some decisions ----
        decisions = [
            {
                "title": "前端框架选型React",
                "decision": "决定采用React作为前端框架",
                "rationale": "团队经验丰富",
                "project_id": "proj_web",
                "alternatives": ["Vue", "Angular"],
                "participants": ["张明", "李华"],
            },
            {
                "title": "数据库选择PostgreSQL",
                "decision": "确认使用PostgreSQL",
                "rationale": "JSON支持好",
                "project_id": "proj_web",
                "alternatives": ["MySQL"],
                "participants": ["王芳"],
            },
            {
                "title": "缓存方案选择Redis",
                "decision": "采用Redis作为缓存层",
                "rationale": "性能优秀",
                "project_id": "proj_web",
                "alternatives": ["Memcached"],
                "participants": ["赵刚"],
            },
        ]

        saved_ids = []
        for dec in decisions:
            did = card_mgr.record_decision(
                title=dec["title"],
                decision=dec["decision"],
                rationale=dec["rationale"],
                project_id=dec["project_id"],
                alternatives=dec.get("alternatives"),
                participants=dec.get("participants"),
                owner=owner,
            )
            if did:
                saved_ids.append(did)

        # ---- Test card push with related message ----
        related_message = "我们现在讨论一下React组件的设计规范"
        cards = card_mgr.check_and_push(
            current_message=related_message,
            owner=owner,
            project_id="proj_web",
        )

        # ---- Test card push with unrelated message ----
        unrelated_message = "今天中午吃什么"
        no_cards = card_mgr.check_and_push(
            current_message=unrelated_message,
            owner=owner,
        )

        # ---- Test Markdown formatting ----
        markdown = ""
        if cards:
            markdown = card_mgr.format_cards_markdown(cards)

        has_markdown_header = "历史决策" in markdown if markdown else False
        has_decision_content = any(
            kw in markdown for kw in ["React", "PostgreSQL", "Redis"]
        ) if markdown else False

        # ---- Test decision history ----
        history = card_mgr.get_decision_history(
            project_id="proj_web", owner=owner, limit=10
        )

        # ---- Test overturn ----
        overturn_ok = False
        if saved_ids:
            overturn_ok = card_mgr.overturn_decision(
                saved_ids[0], reason="需求变更"
            )

        # ---- Metrics ----
        result_data = {
            "decisions_recorded": {
                "value": len(saved_ids),
                "target": len(decisions),
                "passed": len(saved_ids) >= len(decisions),
            },
            "related_cards_pushed": {
                "value": len(cards),
                "target": 1,
                "passed": len(cards) >= 1,
            },
            "unrelated_no_cards": {
                "value": 1.0 if len(no_cards) == 0 else 0.0,
                "target": 1.0,
                "passed": len(no_cards) == 0,
            },
            "markdown_formatted": {
                "value": 1.0 if has_markdown_header else 0.0,
                "target": 1.0,
                "passed": has_markdown_header,
            },
            "decision_history": {
                "value": len(history),
                "target": len(decisions),
                "passed": len(history) >= len(decisions),
            },
            "decision_overturn": {
                "value": 1.0 if overturn_ok else 0.0,
                "target": 1.0,
                "passed": overturn_ok,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_decision_cards ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Recorded {len(saved_ids)}, cards={len(cards)}, "
                    f"no_cards_for_unrelated={len(no_cards) == 0}, "
                    f"markdown={has_markdown_header}, history={len(history)}, "
                    f"overturn={overturn_ok}",
        )

        assert len(saved_ids) >= len(decisions), "Not all decisions recorded"
        assert len(cards) >= 1, "Expected at least 1 card for related message"
        if not passed:
            pytest.fail("Decision cards test failed")


# ── 4. Decision Lifecycle ─────────────────────────────────────────────────
class TestDecisionLifecycle:
    """Verify decision lifecycle: extract → save → search → push → overturn."""

    TEST_ID = "direction_b_004"
    CATEGORY = "decision_lifecycle"

    def test_decision_lifecycle(self, store, data_gen, metrics, report_collector):
        from decision_memory.decision_extractor import DecisionExtractor
        from decision_memory.decision_card import DecisionCardManager

        extractor = DecisionExtractor(store)
        card_mgr = DecisionCardManager(store)
        owner = "user_dec_lifecycle"

        # ---- Step 1: Extract from conversation ----
        conversation = [
            {"sender": "Alice", "content": "大家觉得API用RESTful还是GraphQL？", "timestamp_ms": 1000},
            {"sender": "Bob", "content": "GraphQL查询更灵活，但RESTful工具链更完善", "timestamp_ms": 2000},
            {"sender": "Alice", "content": "考虑到团队熟悉度，我们决定采用RESTful API风格", "timestamp_ms": 3000},
            {"sender": "Charlie", "content": "同意，GraphQL以后再说", "timestamp_ms": 4000},
        ]

        extracted = extractor.extract_from_conversation(
            messages=conversation,
            project_id="proj_api",
            channel_id="ch_design",
        )

        # ---- Step 2: Save decisions ----
        saved_ids = extractor.save_decisions(extracted, owner=owner)

        # Also manually record one more decision
        manual_id = card_mgr.record_decision(
            title="使用JWT认证",
            decision="采用JWT token进行API认证",
            rationale="无状态，易于扩展",
            project_id="proj_api",
            alternatives=["Session", "OAuth2"],
            owner=owner,
        )

        # ---- Step 3: Search ----
        search_results = extractor.search_decisions(
            query="RESTful", owner=owner
        )

        jwt_results = extractor.search_decisions(
            query="JWT", owner=owner
        )

        # ---- Step 4: Push cards ----
        cards = card_mgr.check_and_push(
            current_message="我们来讨论一下API的认证方案",
            owner=owner,
        )

        # ---- Step 5: Overturn ----
        target_id = manual_id if manual_id else (saved_ids[0] if saved_ids else None)
        overturned = False
        if target_id:
            overturned = card_mgr.overturn_decision(
                target_id, reason="改用OAuth2"
            )

        # Verify overturned status
        decision_after = None
        if target_id:
            decision_after = store.get_decision(target_id)

        status_overturned = False
        if decision_after:
            tags = decision_after.get("tags", "{}")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = {}
            status_overturned = tags.get("status") == "overturned"

        # ---- Metrics ----
        result_data = {
            "extraction_from_conversation": {
                "value": len(extracted),
                "target": 1,
                "passed": len(extracted) >= 1,
            },
            "decisions_saved": {
                "value": len(saved_ids) + (1 if manual_id else 0),
                "target": 2,
                "passed": len(saved_ids) >= 1 and manual_id is not None,
            },
            "search_restful": {
                "value": len(search_results),
                "target": 1,
                "passed": len(search_results) >= 1,
            },
            "search_jwt": {
                "value": len(jwt_results),
                "target": 1,
                "passed": len(jwt_results) >= 1,
            },
            "card_push_on_topic": {
                "value": len(cards),
                "target": 1,
                "passed": len(cards) >= 1,
            },
            "decision_overturned": {
                "value": 1.0 if overturned else 0.0,
                "target": 1.0,
                "passed": overturned,
            },
            "status_updated": {
                "value": 1.0 if status_overturned else 0.0,
                "target": 1.0,
                "passed": status_overturned,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_decision_lifecycle ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Extracted={len(extracted)}, saved={len(saved_ids) + (1 if manual_id else 0)}, "
                    f"search_RESTful={len(search_results)}, search_JWT={len(jwt_results)}, "
                    f"cards={len(cards)}, overturned={overturned}, status={status_overturned}",
        )

        assert len(extracted) >= 1, "Should extract at least 1 decision from conversation"
        assert len(search_results) >= 1, "Should find RESTful decision"
        if not passed:
            pytest.fail("Decision lifecycle test failed")
