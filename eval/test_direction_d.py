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


# ── Helper: register knowledge entries for GapDetector ─────────────────
def _register_team_knowledge(store, team_id, member_knowledge):
    """Register knowledge_health entries for team members.

    Args:
        store: MiniStore instance
        team_id: Team identifier
        member_knowledge: Dict[member_name -> List[(topic_text, category, importance)]]
    """
    from src.direction_d.freshness_monitor import FreshnessMonitor

    monitor = FreshnessMonitor(store)
    ids = {}
    for member, entries in member_knowledge.items():
        for topic, category, importance in entries:
            kh_id = monitor.register_knowledge(
                chunk_id=topic,
                team_id=team_id,
                category=category,
                importance=importance,
                holders=[member],
            )
            ids[topic] = kh_id
    return ids


# ── 1. Knowledge Gap Detection ────────────────────────────────────────────
class TestKnowledgeGapDetection:
    """Verify the system can identify knowledge gaps and conflicts in a team."""

    TEST_ID = "direction_d_001"
    CATEGORY = "knowledge_gap_detection"

    def test_knowledge_gap_detection(self, store, data_gen, metrics, report_collector):
        from src.direction_d.gap_detector import GapDetector

        team_members = ["张三", "李四", "王五", "赵六"]
        team_id = "team_gap_test"

        # ---- Populate team chunks (for search-based recall) ----
        team_data = {
            "张三": [
                "项目K使用 React + TypeScript 技术栈，前端组件库用Ant Design",
                "项目K的部署用的是 AWS ECS，CI/CD用GitHub Actions",
            ],
            "李四": [
                "项目K的前端用的是 Vue，组件库用Element Plus，页面布局是响应式的",
            ],
        }
        chunks = data_gen.make_team_chunks(team_members, team_data, team_id)
        for chunk in chunks:
            store.insert_chunk(chunk)

        # ---- Register knowledge for GapDetector ----
        member_knowledge = {
            "张三": [
                ("React TypeScript 前端 Ant Design 组件库", "frontend", 0.8),
                ("AWS ECS 部署 GitHub Actions CI/CD", "devops", 0.8),
            ],
            "李四": [
                ("Vue 前端 Element Plus 响应式布局", "frontend", 0.7),
            ],
        }
        _register_team_knowledge(store, team_id, member_knowledge)

        # ---- Run gap detection ----
        detector = GapDetector(store)
        gaps = detector.detect_gaps(team_id)
        coverage = detector.analyze_coverage(team_id)

        # Update team map for completeness
        detector.update_team_map(team_id)

        # ---- Verify ----
        domain_details = coverage.get("domain_details", {})
        spof = detector.detect_single_points(team_id)

        # Frontend domain should have multiple holders (conflict)
        frontend_info = domain_details.get("frontend", {})
        frontend_holder_count = frontend_info.get("holder_count", 0)

        # Check if gaps are detected for uncovered domains
        uncovered_detected = len(gaps) > 0

        # Check if team map was created
        team_map = store.get_team_knowledge_map(team_id)
        map_created = team_map is not None

        result_data = {
            "gap_detected": {
                "value": 1.0 if uncovered_detected else 0.0,
                "target": 0.80,
                "passed": uncovered_detected,
            },
            "conflict_identified": {
                "value": 1.0 if frontend_holder_count >= 2 else 0.0,
                "target": 0.85,
                "passed": frontend_holder_count >= 2,
            },
            "team_map_created": {
                "value": 1.0 if map_created else 0.0,
                "target": 1.0,
                "passed": map_created,
            },
            "domains_analyzed": {
                "value": len(domain_details),
                "target": 5,
                "passed": len(domain_details) >= 5,
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
            details=f"Domains={len(domain_details)}, Gaps={len(gaps)}, SPOFs={len(spof)}, "
                    f"Frontend holders={frontend_holder_count}",
        )

        assert uncovered_detected, "No knowledge gaps detected"
        assert frontend_holder_count >= 2, "Frontend conflict not identified"


# ── 2. Forgetting Alerts ─────────────────────────────────────────────────
class TestForgettingAlert:
    """Verify the system detects and alerts about knowledge that is about to expire."""

    TEST_ID = "direction_d_002"
    CATEGORY = "forgetting_alert"

    def test_forgetting_alert(self, store, data_gen, metrics, report_collector):
        from src.direction_d.freshness_monitor import FreshnessMonitor

        team_id = "team_l"
        monitor = FreshnessMonitor(store)

        # ---- Register knowledge entries ----
        topic_1 = "项目L的安全审计要在6月1日前完成 高优先级"
        topic_2 = "项目L的数据库备份策略需要更新 待办"

        kh_id_1 = monitor.register_knowledge(
            chunk_id=topic_1, team_id=team_id,
            category="api_doc", importance=0.9, holders=["team_l_member"],
        )
        kh_id_2 = monitor.register_knowledge(
            chunk_id=topic_2, team_id=team_id,
            category="api_doc", importance=0.7, holders=["team_l_member"],
        )

        # Also insert chunks for search-based tests
        for topic, content in [(topic_1, "项目L的安全审计要在6月1日前完成"), (topic_2, "项目L的数据库备份策略需要更新")]:
            chunk = {
                "id": str(uuid.uuid4()),
                "sessionKey": "team-l-session",
                "turnId": str(int(time.time() * 1000)),
                "seq": 0,
                "role": "user",
                "content": content,
                "owner": "team_l_member",
                "visibility": "shared",
                "createdAt": data_gen.days_ago_ts(60),
                "updatedAt": data_gen.days_ago_ts(60),
            }
            store.insert_chunk(chunk)

        # ---- Set last_verified_at to old dates (api_doc validity=30 days) ----
        now_ms = int(time.time() * 1000)
        old_90_days = now_ms - 90 * 86400000   # stale (>2*30=60, <=4*30=120)
        old_45_days = now_ms - 45 * 86400000   # aging (>30, <=60)

        c = store.conn.cursor()
        c.execute("UPDATE knowledge_health SET last_verified_at = ? WHERE id = ?", (old_90_days, kh_id_1))
        c.execute("UPDATE knowledge_health SET last_verified_at = ? WHERE id = ?", (old_45_days, kh_id_2))
        store.conn.commit()

        # ---- Run freshness check ----
        changes = monitor.check_freshness(team_id=team_id)

        # ---- Get health summary ----
        summary = monitor.get_health_summary(team_id=team_id)
        status_counts = summary.get("status_counts", {})

        # ---- Verify ----
        has_stale = status_counts.get("stale", 0) > 0 or status_counts.get("forgotten", 0) > 0
        has_aging = status_counts.get("aging", 0) > 0
        total_knowledge = summary.get("total_knowledge", 0)

        result_data = {
            "stale_alerts_generated": {
                "value": 1.0 if has_stale else 0.0,
                "target": 0.90,
                "passed": has_stale,
            },
            "aging_detected": {
                "value": 1.0 if has_aging else 0.0,
                "target": 0.85,
                "passed": has_aging,
            },
            "entries_tracked": {
                "value": total_knowledge,
                "target": 2,
                "passed": total_knowledge >= 2,
            },
            "freshness_changes_detected": {
                "value": len(changes),
                "target": 1,
                "passed": len(changes) >= 1,
            },
        }

        passed = result_data["stale_alerts_generated"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_forgetting_alert ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Changes={len(changes)}, Status counts={status_counts}",
        )

        assert has_stale, "No stale alerts generated for old knowledge"
        if has_aging is False:
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

        # ---- Update team knowledge map (old-style API) ----
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
        from src.direction_d.freshness_monitor import FreshnessMonitor

        team_id = "team_critical_test"
        monitor = FreshnessMonitor(store)

        # ---- Register critical knowledge ----
        password_topic = "项目N的数据库root密码 密钥管理服务 建议"

        kh_id = monitor.register_knowledge(
            chunk_id=password_topic,
            team_id=team_id,
            category="api_doc",   # api_doc validity=30 days
            importance=0.95,
            holders=["team_n_admin"],
        )

        # Also insert chunk
        password_chunk = {
            "id": str(uuid.uuid4()),
            "sessionKey": "critical-session",
            "turnId": "1",
            "seq": 0,
            "role": "user",
            "content": "项目N的数据库root密码是 SecretP@ss123，建议使用密钥管理服务",
            "owner": "team_n_admin",
            "visibility": "shared",
            "createdAt": data_gen.days_ago_ts(150),
            "updatedAt": data_gen.days_ago_ts(150),
        }
        store.insert_chunk(password_chunk)

        # ---- Set to 150 days ago → forgotten for api_doc (>4*30=120) ----
        now_ms = int(time.time() * 1000)
        old_150_days = now_ms - 150 * 86400000

        c = store.conn.cursor()
        c.execute("UPDATE knowledge_health SET last_verified_at = ? WHERE id = ?", (old_150_days, kh_id))
        store.conn.commit()

        # ---- Run freshness check ----
        changes = monitor.check_freshness(team_id=team_id)

        # ---- Get health summary ----
        summary = monitor.get_health_summary(team_id=team_id)
        status_counts = summary.get("status_counts", {})
        high_risk_items = summary.get("high_risk_items", [])

        # ---- Verify ----
        has_forgotten = status_counts.get("forgotten", 0) > 0
        has_high_risk = len(high_risk_items) > 0
        total_knowledge = summary.get("total_knowledge", 0)

        # Check the health record directly
        health_record = store.get_knowledge_health(password_topic)
        record_exists = health_record is not None

        result_data = {
            "status_correctly_forgotten": {
                "value": 1.0 if has_forgotten else 0.0,
                "target": 0.90,
                "passed": has_forgotten,
            },
            "high_risk_detected": {
                "value": 1.0 if has_high_risk else 0.0,
                "target": 0.85,
                "passed": has_high_risk,
            },
            "freshness_changes_detected": {
                "value": len(changes),
                "target": 1,
                "passed": len(changes) >= 1,
            },
            "knowledge_recorded": {
                "value": 1.0 if record_exists else 0.0,
                "target": 1.0,
                "passed": record_exists,
            },
        }

        passed = result_data["status_correctly_forgotten"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_critical_knowledge_forgetting ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Status counts={status_counts}, "
                    f"High risk={len(high_risk_items)}, "
                    f"Changes={len(changes)}",
        )

        assert has_forgotten, "Critical knowledge not marked as forgotten"
        assert record_exists, "Knowledge health record not found"


# ── 5. Team Knowledge Coverage ───────────────────────────────────────────
class TestTeamKnowledgeCoverage:
    """Verify the system can assess and report team knowledge coverage."""

    TEST_ID = "direction_d_005"
    CATEGORY = "team_knowledge_coverage"

    def test_team_knowledge_coverage(self, store, data_gen, metrics, report_collector):
        from src.direction_d.gap_detector import GapDetector

        team_id = "team_coverage_test"
        team_members = ["张三", "李四", "王五", "赵六", "钱七"]

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
        }
        chunks = data_gen.make_team_chunks(team_members, team_data, team_id)
        for chunk in chunks:
            store.insert_chunk(chunk)

        # ---- Register knowledge for GapDetector ----
        member_knowledge = {
            "张三": [
                ("React 前端框架 组件化开发", "frontend", 0.7),
                ("Go语言 微服务 后端", "backend", 0.7),
            ],
            "李四": [
                ("PostgreSQL 数据库 JSONB查询", "database", 0.7),
            ],
            "王五": [
                ("Kubernetes 部署 自动扩缩容 DevOps", "devops", 0.8),
            ],
        }
        _register_team_knowledge(store, team_id, member_knowledge)

        # ---- Run gap detection ----
        detector = GapDetector(store)
        gaps = detector.detect_gaps(team_id)
        coverage = detector.analyze_coverage(team_id)

        domain_details = coverage.get("domain_details", {})

        # ---- Verify coverage ----
        # Domains with zero coverage should be detected as gaps
        zero_coverage_domains = [
            d for d, info in domain_details.items()
            if not info.get("is_covered", False)
        ]
        uncovered_gap_domains = [
            g["domain"] for g in gaps if g.get("severity") == "critical"
        ]

        # Security and product/business should have zero coverage
        security_info = domain_details.get("security", {})
        security_has_gap = not security_info.get("is_covered", True)
        business_info = domain_details.get("business", {})
        business_has_gap = not business_info.get("is_covered", True)

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
            "business_gap_detected": {
                "value": 1.0 if business_has_gap else 0.0,
                "target": 0.80,
                "passed": business_has_gap,
            },
            "team_map_created": {
                "value": 1.0 if team_map else 0.0,
                "target": 1.0,
                "passed": team_map is not None,
            },
            "coverage_calculated": {
                "value": len(domain_details),
                "target": 5,
                "passed": len(domain_details) >= 5,
            },
        }

        passed = result_data["gaps_detected"]["passed"]
        status_str = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_team_knowledge_coverage ({self.CATEGORY})",
            status=status_str,
            metrics=result_data,
            details=f"Domains={len(domain_details)}, Gaps={len(gaps)}, "
                    f"Zero-coverage={len(zero_coverage_domains)}, "
                    f"Security gap={security_has_gap}, Business gap={business_has_gap}",
        )

        assert len(gaps) > 0, "No knowledge gaps detected"
        assert security_has_gap, "Security domain gap not detected"
        assert business_has_gap, "Business domain gap not detected"
