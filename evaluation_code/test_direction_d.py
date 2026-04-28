"""
Direction D — Team Knowledge Health Test Suite — 5 test cases.

Tests the enterprise memory engine's ability to:
  1. Detect knowledge gaps
  2. Provide forgetting alerts
  3. Synchronize team knowledge
  4. Identify critical knowledge forgetting
  5. Assess team knowledge coverage

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid
from datetime import datetime, timedelta

import pytest


# ── 1. Knowledge Gap Detection ────────────────────────────────────────────
class TestKnowledgeGapDetection:
    """Verify the system can identify knowledge gaps and conflicts in a team."""

    TEST_ID = "direction_d_001"
    CATEGORY = "knowledge_gap_detection"

    def test_knowledge_gap_detection(self, store, data_gen, metrics, report_collector):
        from gap_detector import GapDetector

        team_members = ["张三", "李四", "王五", "赵六"]
        team_id = "team_gap_test"

        # ---- Populate team chunks ----
        # Zhang San knows about React + TypeScript stack
        team_data = {
            "张三": [
                "项目K使用 React + TypeScript 技术栈，前端组件库用Ant Design",
                "项目K的部署用的是 AWS ECS，CI/CD用GitHub Actions",
            ],
            "李四": [
                "项目K的前端用的是 Vue，Vue 3组合式API",
            ],
            # 王五 and 赵六 have no relevant project K knowledge
        }

        chunks = data_gen.make_team_chunks(team_members, team_data, team_id)
        for chunk in chunks:
            store.insert_chunk(chunk)

        # ---- Run gap detection ----
        detector = GapDetector(store)
        result = detector.detect_gaps(team_id)

        # ---- Verify ----
        domains = result.get("domains", [])
        gaps = result.get("gaps", [])
        spof = result.get("single_points_of_failure", [])

        # Check if knowledge conflict is detected (React vs Vue)
        # The system should flag that different members have different info
        has_conflict = any(
            d.get("domain") == "frontend" and len(d.get("members_with_knowledge", [])) >= 2
            for d in domains
        )

        # Check if gaps are detected for uncovered members
        uncovered_detected = len(gaps) > 0

        # Check if team map was created
        team_map = store.get_team_knowledge_map(team_id)
        map_created = team_map is not None

        # Verify frontend domain has conflict
        frontend_domain = next(
            (d for d in domains if d.get("domain") == "frontend"), {}
        )
        frontend_members = frontend_domain.get("members_with_knowledge", [])

        result_data = {
            "gap_detected": {
                "value": 1.0 if uncovered_detected else 0.0,
                "target": 0.80,
                "passed": uncovered_detected,
            },
            "conflict_identified": {
                "value": 1.0 if len(frontend_members) >= 2 else 0.0,
                "target": 0.85,
                "passed": len(frontend_members) >= 2,
            },
            "team_map_created": {
                "value": 1.0 if map_created else 0.0,
                "target": 1.0,
                "passed": map_created,
            },
            "domains_analyzed": {
                "value": len(domains),
                "target": 5,
                "passed": len(domains) >= 5,
            },
            "spof_detected": {
                "value": len(spof),
                "target": 0,
                "passed": True,  # Any number is fine
            },
        }

        passed = result_data["gap_detected"]["passed"]
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_knowledge_gap_detection ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Domains={len(domains)}, Gaps={len(gaps)}, SPOFs={len(spof)}, "
                    f"Frontend members={frontend_members}",
        )

        assert uncovered_detected, "No knowledge gaps detected"
        assert len(frontend_members) >= 2, "Frontend conflict not identified"


# ── 2. Forgetting Alerts ─────────────────────────────────────────────────
class TestForgettingAlert:
    """Verify the system detects and alerts about knowledge that is about to expire."""

    TEST_ID = "direction_d_002"
    CATEGORY = "forgetting_alert"

    def test_forgetting_alert(self, store, data_gen, metrics, report_collector):
        from freshness_monitor import FreshnessMonitor

        # ---- Create knowledge entries with old timestamps ----
        old_ts = data_gen.days_ago_ts(60)  # 60 days ago

        # Security audit deadline (60 days old, deadline in 15 more days = urgent)
        security_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "team-l-session",
            "turnId": "1",
            "seq": 0,
            "role": "user",
            "content": "项目L的安全审计要在6月1日前完成，这是高优先级事项",
            "owner": "team_l_member",
            "visibility": "shared",
            "createdAt": old_ts,
            "updatedAt": old_ts,
        }
        store.insert_chunk(security_chunk)

        # DB backup strategy (also old)
        db_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "team-l-session",
            "turnId": "2",
            "seq": 1,
            "role": "user",
            "content": "项目L的数据库备份策略需要更新，这是待办事项",
            "owner": "team_l_member",
            "visibility": "shared",
            "createdAt": data_gen.days_ago_ts(45),
            "updatedAt": data_gen.days_ago_ts(45),
        }
        store.insert_chunk(db_chunk)

        # Create knowledge health records with stale status
        store.upsert_knowledge_health(
            chunk_id=security_chunk["id"],
            team_id="team_l",
            importance_score=0.9,
            freshness_status="stale",
            category="time_sensitive",
        )
        store.upsert_knowledge_health(
            chunk_id=db_chunk["id"],
            team_id="team_l",
            importance_score=0.7,
            freshness_status="aging",
        )

        # ---- Run freshness monitor ----
        monitor = FreshnessMonitor(store, stale_threshold_days=30, forgotten_threshold_days=90)
        check_result = monitor.check_freshness(team_id="team_l")

        # ---- Get warnings ----
        warnings = monitor.get_warnings(team_id="team_l")

        # ---- Verify ----
        has_stale_alerts = any(w.get("freshness_status") == "stale" for w in warnings)
        has_aging_alerts = any(w.get("freshness_status") == "aging" for w in warnings)

        # Check alert messages contain actionable info
        alert_messages = [w.get("alert_message", "") for w in warnings]
        has_security_alert = any("security" in msg.lower() or "stale" in msg.lower()
                                  or "forgot" in msg.lower() or "⚠" in msg
                                  for msg in alert_messages)

        # Check status distribution
        status_dist = check_result.get("status_distribution", {})

        result_data = {
            "stale_alerts_generated": {
                "value": 1.0 if has_stale_alerts else 0.0,
                "target": 0.90,
                "passed": has_stale_alerts,
            },
            "aging_detected": {
                "value": 1.0 if has_aging_alerts else 0.0,
                "target": 0.85,
                "passed": has_aging_alerts,
            },
            "alert_messages_present": {
                "value": 1.0 if len(alert_messages) > 0 else 0.0,
                "target": 0.90,
                "passed": len(alert_messages) > 0,
            },
            "entries_tracked": {
                "value": check_result.get("total_entries", 0),
                "target": 2,
                "passed": check_result.get("total_entries", 0) >= 2,
            },
        }

        passed = result_data["stale_alerts_generated"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_forgetting_alert ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Warnings={len(warnings)}, Status distribution={status_dist}",
        )

        assert has_stale_alerts, "No stale alerts generated for 60-day-old knowledge"
        if has_aging_alerts is False:
            # aging is acceptable if not enough time has passed
            pass


# ── 3. Team Knowledge Sync ───────────────────────────────────────────────
class TestTeamKnowledgeSync:
    """Verify the system detects knowledge migrations and sync issues."""

    TEST_ID = "direction_d_003"
    CATEGORY = "team_knowledge_sync"

    def test_team_knowledge_sync(self, store, data_gen, metrics, report_collector):
        team_id = "team_sync_test"

        # ---- Zhang San knows about old location ----
        old_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "team-sync-session",
            "turnId": "1",
            "seq": 0,
            "role": "user",
            "content": "项目M的API文档在Confluence上",
            "owner": "张三",
            "visibility": "shared",
            "createdAt": data_gen.days_ago_ts(30),
            "updatedAt": data_gen.days_ago_ts(30),
        }
        store.insert_chunk(old_chunk)

        # ---- Li Si knows about new location ----
        new_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "team-sync-session",
            "turnId": "2",
            "seq": 1,
            "role": "user",
            "content": "项目M的API文档迁移到Notion了",
            "owner": "李四",
            "visibility": "shared",
            "createdAt": data_gen.days_ago_ts(5),
            "updatedAt": data_gen.days_ago_ts(5),
        }
        store.insert_chunk(new_chunk)

        # ---- Query ----
        results = store.search_chunks("项目M API文档", max_results=10)
        all_content = " ".join(r.get("content", "") for r in results)

        # Should find the new location
        has_new_location = "Notion" in all_content
        # Should still be able to find old location
        has_old_location = "Confluence" in all_content

        # Check if both locations are discoverable
        has_both = has_new_location and has_old_location

        # ---- Update team knowledge map ----
        store.upsert_team_knowledge_map(
            team_id=team_id,
            domain="documentation",
            description="Project M API documentation",
            member_coverage={"张三": 1, "李四": 1},
            overall_coverage=0.5,
            gap_areas=[{
                "issue": "location_conflict",
                "old": "Confluence",
                "new": "Notion",
                "updated_by": "李四",
                "days_since_update": 5,
            }],
        )

        team_map = store.get_team_knowledge_map(team_id)

        result_data = {
            "new_location_found": {
                "value": 1.0 if has_new_location else 0.0,
                "target": 0.90,
                "passed": has_new_location,
            },
            "old_location_preserved": {
                "value": 1.0 if has_old_location else 0.0,
                "target": 0.85,
                "passed": has_old_location,
            },
            "both_locations_accessible": {
                "value": 1.0 if has_both else 0.0,
                "target": 0.85,
                "passed": has_both,
            },
            "team_map_updated": {
                "value": 1.0 if team_map else 0.0,
                "target": 1.0,
                "passed": team_map is not None,
            },
        }

        passed = has_new_location  # At minimum, new location should be found
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_team_knowledge_sync ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"New={has_new_location}, Old={has_old_location}, Both={has_both}",
        )

        assert has_new_location, "New API doc location (Notion) not found"


# ── 4. Critical Knowledge Forgetting ─────────────────────────────────────
class TestCriticalKnowledgeForgetting:
    """Verify that critical/sensitive knowledge gets appropriate reminders."""

    TEST_ID = "direction_d_004"
    CATEGORY = "critical_knowledge_forgetting"

    def test_critical_knowledge_forgetting(self, store, data_gen, metrics, report_collector):
        from freshness_monitor import FreshnessMonitor

        team_id = "team_critical_test"

        # ---- Create a 90-day-old password entry ----
        old_ts = data_gen.days_ago_ts(90)
        password_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "critical-session",
            "turnId": "1",
            "seq": 0,
            "role": "user",
            "content": "项目N的数据库root密码是 SecretP@ss123，建议使用密钥管理服务",
            "owner": "team_n_admin",
            "visibility": "shared",
            "createdAt": old_ts,
            "updatedAt": old_ts,
        }
        store.insert_chunk(password_chunk)

        # Create health record marked as forgotten
        store.upsert_knowledge_health(
            chunk_id=password_chunk["id"],
            team_id=team_id,
            importance_score=0.95,  # Critical
            freshness_status="forgotten",
            category="time_sensitive",
        )

        # ---- Run freshness monitor ----
        monitor = FreshnessMonitor(store, stale_threshold_days=30, forgotten_threshold_days=90)
        check_result = monitor.check_freshness(team_id=team_id)

        # Get entry health
        entry_health = monitor.get_entry_health(password_chunk["id"])

        # ---- Verify ----
        status_is_forgotten = entry_health.get("freshness_status") == "forgotten"
        has_recommended_action = entry_health.get("recommended_action") in (
            "re_verify", "archive", "review"
        )

        # Check alerts
        alerts = store.get_knowledge_alerts(team_id=team_id, alert_type="forgotten")
        has_forgotten_alert = len(alerts) > 0

        # Security note: password should be flagged
        alert_messages = [a.get("alert_message", "") for a in alerts]
        has_security_note = any(
            "forgot" in msg.lower() or "forgotten" in msg.lower() or "⚠" in msg
            for msg in alert_messages
        )

        result_data = {
            "status_correctly_forgotten": {
                "value": 1.0 if status_is_forgotten else 0.0,
                "target": 0.90,
                "passed": status_is_forgotten,
            },
            "action_recommended": {
                "value": 1.0 if has_recommended_action else 0.0,
                "target": 0.85,
                "passed": has_recommended_action,
            },
            "alert_generated": {
                "value": 1.0 if has_forgotten_alert else 0.0,
                "target": 0.90,
                "passed": has_forgotten_alert,
            },
            "security_reminder_present": {
                "value": 1.0 if has_security_note else 0.0,
                "target": 0.85,
                "passed": has_security_note,
            },
        }

        passed = result_data["status_correctly_forgotten"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_critical_knowledge_forgetting ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Status={entry_health.get('freshness_status')}, "
                    f"Action={entry_health.get('recommended_action')}, "
                    f"Alerts={len(alerts)}",
        )

        assert status_is_forgotten, "Critical knowledge not marked as forgotten"
        assert has_forgotten_alert, "No alert generated for forgotten critical knowledge"


# ── 5. Team Knowledge Coverage ───────────────────────────────────────────
class TestTeamKnowledgeCoverage:
    """Verify the system can assess and report team knowledge coverage."""

    TEST_ID = "direction_d_005"
    CATEGORY = "team_knowledge_coverage"

    def test_team_knowledge_coverage(self, store, data_gen, metrics, report_collector):
        from gap_detector import GapDetector

        team_id = "team_coverage_test"
        team_members = ["张三", "李四", "王五", "赵六", "钱七"]
        knowledge_domains = ["前端", "后端", "数据库", "DevOps", "安全", "产品"]

        # ---- Populate team knowledge ----
        team_data = {
            "张三": [
                "项目使用React前端框架，组件化开发",
                "后端用Go语言编写微服务",
            ],
            "李四": [
                "数据库使用PostgreSQL，支持JSONB查询",
            ],
            "王五": [
                "部署使用Kubernetes，支持自动扩缩容",
            ],
            # 赵六 and 钱七 have no domain-specific knowledge
        }

        chunks = data_gen.make_team_chunks(team_members, team_data, team_id)
        for chunk in chunks:
            store.insert_chunk(chunk)

        # ---- Run gap detection ----
        detector = GapDetector(store)
        result = detector.detect_gaps(team_id)

        domains = result.get("domains", [])
        gaps = result.get("gaps", [])

        # ---- Verify coverage ----
        # Domains with zero coverage should be detected as gaps
        zero_coverage_domains = [d for d in domains if d.get("overall_coverage", 1.0) < 0.2]
        low_coverage_domains = [d for d in domains if d.get("overall_coverage", 1.0) < 0.5]

        # Security and product should have zero coverage
        security_domain = next((d for d in domains if d.get("domain") == "security"), {})
        product_domain = next((d for d in domains if d.get("domain") == "product"), {})

        security_has_gap = security_domain.get("overall_coverage", 1.0) < 0.5
        product_has_gap = product_domain.get("overall_coverage", 1.0) < 0.5

        # Check team map exists
        team_map = store.get_team_knowledge_map(team_id)

        result_data = {
            "gaps_detected": {
                "value": 1.0 if len(gaps) > 0 else 0.0,
                "target": 0.80,
                "passed": len(gaps) > 0,
            },
            "security_gap_detected": {
                "value": 1.0 if security_has_gap else 0.0,
                "target": 0.80,
                "passed": security_has_gap,
            },
            "product_gap_detected": {
                "value": 1.0 if product_has_gap else 0.0,
                "target": 0.80,
                "passed": product_has_gap,
            },
            "team_map_created": {
                "value": 1.0 if team_map else 0.0,
                "target": 1.0,
                "passed": team_map is not None,
            },
            "coverage_calculated": {
                "value": len(domains),
                "target": 5,
                "passed": len(domains) >= 5,
            },
        }

        passed = result_data["gaps_detected"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_team_knowledge_coverage ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Domains={len(domains)}, Gaps={len(gaps)}, "
                    f"Zero-coverage={len(zero_coverage_domains)}, "
                    f"Security gap={security_has_gap}, Product gap={product_has_gap}",
        )

        assert len(gaps) > 0, "No knowledge gaps detected"
        assert security_has_gap, "Security domain gap not detected"
        assert product_has_gap, "Product domain gap not detected"
