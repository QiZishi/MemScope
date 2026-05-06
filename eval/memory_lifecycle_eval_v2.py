"""Memory Lifecycle Evaluation for MemScope.

Tests the FULL memory system (not just RAG retrieval):
1. Fact Extraction - from raw conversation text to structured facts
2. Contradiction Detection - new info supersedes old info
3. Unified Recall - search across chunks + decisions + preferences + knowledge
4. Memory Consistency - after contradictions, only latest info is returned
5. Temporal Ordering - later info has priority over earlier info

This evaluation tests what makes MemScope a MEMORY system, not just a RAG system.
"""

import sys
import os
import json
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.store import SqliteStore
from core.fact_extractor import FactExtractor, MemoryManager


class MemoryLifecycleEval:
    """Evaluate the full memory lifecycle."""

    def __init__(self):
        self.results = {
            "fact_extraction": {"total": 0, "passed": 0, "details": []},
            "contradiction_detection": {"total": 0, "passed": 0, "details": []},
            "unified_recall": {"total": 0, "passed": 0, "details": []},
            "memory_consistency": {"total": 0, "passed": 0, "details": []},
            "temporal_ordering": {"total": 0, "passed": 0, "details": []},
            "consolidation": {"total": 0, "passed": 0, "details": []},
            "health_monitoring": {"total": 0, "passed": 0, "details": []},
            "cross_agent_sharing": {"total": 0, "passed": 0, "details": []},
            "memory_forgetting": {"total": 0, "passed": 0, "details": []},
        }

    def run_all(self):
        """Run all evaluations."""
        print("=" * 60)
        print("MemScope Memory Lifecycle Evaluation")
        print("=" * 60)

        self._eval_fact_extraction()
        self._eval_contradiction_detection()
        self._eval_unified_recall()
        self._eval_memory_consistency()
        self._eval_temporal_ordering()
        self._eval_consolidation()
        self._eval_health_monitoring()
        self._eval_cross_agent_sharing()
        self._eval_memory_forgetting()

        self._print_summary()
        return self.results

    def _eval_fact_extraction(self):
        """Test: Can the system extract structured facts from raw text?"""
        print("\n[1/5] Fact Extraction")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        test_cases = [
            {
                "name": "Decision extraction",
                "messages": [{"role": "user", "content": "我们决定用React作为前端框架"}],
                "expect": {"decisions": 1, "preferences": 0, "knowledge": 0},
            },
            {
                "name": "Preference extraction",
                "messages": [{"role": "user", "content": "我喜欢用Python写代码"}],
                "expect": {"decisions": 0, "preferences": 1, "knowledge": 0},
            },
            {
                "name": "Knowledge extraction",
                "messages": [{"role": "user", "content": "项目数据库用的是PostgreSQL"}],
                "expect": {"decisions": 0, "preferences": 0, "knowledge": 1},
            },
            {
                "name": "Mixed extraction",
                "messages": [
                    {"role": "user", "content": "我们决定用Docker部署，数据库用MySQL"},
                    {"role": "user", "content": "我喜欢用VS Code"},
                ],
                "expect": {"decisions": 1, "preferences": 1, "knowledge": 1},
            },
            {
                "name": "No facts (casual chat)",
                "messages": [{"role": "user", "content": "今天天气不错"}],
                "expect": {"decisions": 0, "preferences": 0, "knowledge": 0},
            },
        ]

        for tc in test_cases:
            self.results["fact_extraction"]["total"] += 1
            # Fresh DB for each test
            store2 = SqliteStore(tempfile.mktemp(suffix='.db'))
            mm2 = MemoryManager(store2)
            r = mm2.ingest_conversation(tc["messages"], owner="test", session_key="s1")
            
            passed = True
            for fact_type in ["decisions", "preferences", "knowledge"]:
                actual = r["facts_extracted"][fact_type]
                expected = tc["expect"][fact_type]
                if actual < expected:
                    passed = False
            
            if passed:
                self.results["fact_extraction"]["passed"] += 1
                print(f"  ✅ {tc['name']}: {r['facts_extracted']}")
            else:
                print(f"  ❌ {tc['name']}: expected {tc['expect']}, got {r['facts_extracted']}")
            
            self.results["fact_extraction"]["details"].append({
                "name": tc["name"],
                "passed": passed,
                "expected": tc["expect"],
                "actual": r["facts_extracted"],
            })

        os.unlink(db)

    def _eval_contradiction_detection(self):
        """Test: Does new info correctly supersede old info?"""
        print("\n[2/5] Contradiction Detection")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        test_cases = [
            {
                "name": "Decision update (React → Vue)",
                "rounds": [
                    [{"role": "user", "content": "我们决定用React作为前端框架"}],
                    [{"role": "user", "content": "我们最终决定把前端框架切换到Vue"}],
                ],
                "expect_contradictions": 1,
                "expect_active_chosen": "Vue",
            },
            {
                "name": "Preference update (Python → Go)",
                "rounds": [
                    [{"role": "user", "content": "我喜欢用Python"}],
                    [{"role": "user", "content": "我更喜欢用Go，不要用Python了"}],
                ],
                "expect_contradictions": 1,
                "expect_active_value": "Go",
            },
            {
                "name": "No contradiction (different topics)",
                "rounds": [
                    [{"role": "user", "content": "我们决定用React作为前端框架"}],
                    [{"role": "user", "content": "我们决定用PostgreSQL作为数据库"}],
                ],
                "expect_contradictions": 0,
            },
        ]

        for tc in test_cases:
            self.results["contradiction_detection"]["total"] += 1
            store2 = SqliteStore(tempfile.mktemp(suffix='.db'))
            mm2 = MemoryManager(store2)

            total_contradictions = 0
            for round_msgs in tc["rounds"]:
                r = mm2.ingest_conversation(round_msgs, owner="test", session_key="s1")
                total_contradictions += r["contradictions_resolved"]

            passed = total_contradictions == tc["expect_contradictions"]
            
            # Additional check: verify the active item is correct
            if "expect_active_chosen" in tc and passed:
                decisions = store2.search_decisions(owner="test", limit=10)
                active = [d for d in decisions if d["status"] == "active"]
                if active and active[0]["chosen"] != tc["expect_active_chosen"]:
                    passed = False

            if "expect_active_value" in tc and passed:
                prefs = store2.list_preferences(owner="test")
                if prefs and prefs[0]["value"] != tc["expect_active_value"]:
                    passed = False

            if passed:
                self.results["contradiction_detection"]["passed"] += 1
                print(f"  ✅ {tc['name']}: {total_contradictions} contradictions")
            else:
                print(f"  ❌ {tc['name']}: expected {tc['expect_contradictions']}, got {total_contradictions}")

            self.results["contradiction_detection"]["details"].append({
                "name": tc["name"],
                "passed": passed,
                "contradictions": total_contradictions,
            })

        os.unlink(db)

    def _eval_unified_recall(self):
        """Test: Can the system recall from chunks + structured memories?"""
        print("\n[3/5] Unified Recall")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Ingest a rich conversation
        conversation = [
            {"role": "user", "content": "我们决定用React作为前端框架，不用Vue了"},
            {"role": "assistant", "content": "好的，React确实更适合这个项目"},
            {"role": "user", "content": "数据库用的是PostgreSQL，部署在AWS上"},
            {"role": "user", "content": "我喜欢用VS Code写代码"},
            {"role": "assistant", "content": "项目版本是2.1.0"},
        ]
        mm.ingest_conversation(conversation, owner="test", session_key="s1")

        test_cases = [
            {
                "name": "Recall decision by tech term",
                "query": "React",
                "expect_in": "decisions",
                "expect_field": "chosen",
                "expect_value": "React",
            },
            {
                "name": "Recall preference by tool",
                "query": "VS Code",
                "expect_in": "preferences",
                "expect_field": "value",
                "expect_value": "VS Code",
            },
            {
                "name": "Recall knowledge by tech",
                "query": "PostgreSQL",
                "expect_in": "knowledge",
                "expect_field": "topic",
                "expect_value": "PostgreSQL",
            },
            {
                "name": "Recall chunk by content",
                "query": "AWS",
                "expect_in": "chunks",
                "expect_field": "content",
                "expect_value": "AWS",
            },
        ]

        for tc in test_cases:
            self.results["unified_recall"]["total"] += 1
            recall = mm.recall(tc["query"], owner="test")
            
            items = recall.get(tc["expect_in"], [])
            found = False
            for item in items:
                field_val = str(item.get(tc["expect_field"], ""))
                if tc["expect_value"] in field_val:
                    found = True
                    break

            if found:
                self.results["unified_recall"]["passed"] += 1
                print(f"  ✅ {tc['name']}: found '{tc['expect_value']}' in {tc['expect_in']}")
            else:
                print(f"  ❌ {tc['name']}: '{tc['expect_value']}' not found in {tc['expect_in']}")
                print(f"     Got: {items}")

            self.results["unified_recall"]["details"].append({
                "name": tc["name"],
                "passed": found,
                "query": tc["query"],
                "results_count": len(items),
            })

        os.unlink(db)

    def _eval_memory_consistency(self):
        """Test: After contradictions, only the latest info is returned."""
        print("\n[4/5] Memory Consistency")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Phase 1: Store initial facts
        mm.ingest_conversation([
            {"role": "user", "content": "我们决定用React作为前端框架"},
            {"role": "user", "content": "我喜欢用Python"},
        ], owner="test", session_key="s1")

        # Phase 2: Update with new facts (contradictions)
        mm.ingest_conversation([
            {"role": "user", "content": "我们决定把前端框架切换到Vue"},
            {"role": "user", "content": "我更喜欢用Go，不要用Python了"},
        ], owner="test", session_key="s2")

        test_cases = [
            {
                "name": "Decision shows latest value",
                "query": "前端框架",
                "check": lambda r: self._check_latest_decision(r, "Vue"),
            },
            {
                "name": "Preference shows latest value",
                "query": "编程语言",
                "check": lambda r: self._check_latest_preference(r, "Go"),
            },
            {
                "name": "Old decision is superseded",
                "query": "React",
                "check": lambda r: self._check_decision_superseded(r, "React"),
            },
        ]

        for tc in test_cases:
            self.results["memory_consistency"]["total"] += 1
            recall = mm.recall(tc["query"], owner="test")
            passed = tc["check"](recall)

            if passed:
                self.results["memory_consistency"]["passed"] += 1
                print(f"  ✅ {tc['name']}")
            else:
                print(f"  ❌ {tc['name']}")
                print(f"     Decisions: {recall['decisions']}")
                print(f"     Preferences: {recall['preferences']}")

            self.results["memory_consistency"]["details"].append({
                "name": tc["name"],
                "passed": passed,
            })

        os.unlink(db)

    def _eval_temporal_ordering(self):
        """Test: Later information has priority over earlier information."""
        print("\n[5/5] Temporal Ordering")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Multiple rounds of evolving decisions
        rounds = [
            "我们决定用MySQL作为数据库",
            "经过测试，我们决定切换到PostgreSQL",
            "最终确认使用PostgreSQL，性能更好",
        ]

        for i, msg in enumerate(rounds):
            mm.ingest_conversation(
                [{"role": "user", "content": msg}],
                owner="test",
                session_key=f"round_{i}",
            )

        self.results["temporal_ordering"]["total"] += 1

        # Check: only PostgreSQL should be active
        decisions = store.search_decisions(owner="test", limit=10)
        active = [d for d in decisions if d["status"] == "active"]
        superseded = [d for d in decisions if d["status"] == "superseded"]

        passed = (
            len(active) >= 1
            and any("PostgreSQL" in (d.get("chosen", "") or "") for d in active)
            and len(superseded) >= 1
        )

        if passed:
            self.results["temporal_ordering"]["passed"] += 1
            print(f"  ✅ Temporal ordering: {len(active)} active, {len(superseded)} superseded")
            for d in active:
                print(f"     Active: {d['title']} = {d['chosen']}")
        else:
            print(f"  ❌ Temporal ordering failed")
            print(f"     Active: {active}")
            print(f"     Superseded: {superseded}")

        self.results["temporal_ordering"]["details"].append({
            "name": "Decision evolution (MySQL → PostgreSQL)",
            "passed": passed,
            "active_count": len(active),
            "superseded_count": len(superseded),
        })

        os.unlink(db)


    def _eval_consolidation(self):
        """Test: Memory consolidation - multiple related memories merged into higher-level knowledge."""
        print("\n[6/6] Memory Consolidation")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Create multiple decisions about same topic
        mm.ingest_conversation([{"role": "user", "content": "我们决定用MySQL作为数据库"}], owner="test", session_key="s1")
        mm.ingest_conversation([{"role": "user", "content": "经过测试，我们决定切换到PostgreSQL"}], owner="test", session_key="s2")

        # Create preferences
        mm.ingest_conversation([{"role": "user", "content": "我喜欢用React"}], owner="test", session_key="s3")
        mm.ingest_conversation([{"role": "user", "content": "我更喜欢用Vue"}], owner="test", session_key="s4")

        # Create knowledge
        mm.ingest_conversation([{"role": "user", "content": "项目数据库用的是PostgreSQL"}], owner="test", session_key="s5")
        mm.ingest_conversation([{"role": "user", "content": "部署在AWS上"}], owner="test", session_key="s6")

        # Consolidate
        self.results["consolidation"]["total"] += 1
        result = mm.consolidate_memories(owner="test")

        passed = (
            result["decision_timelines"] >= 1
            and result["preference_profiles"] >= 1
            and result["knowledge_graphs"] >= 1
        )

        if passed:
            self.results["consolidation"]["passed"] += 1
            print(f"  ✅ Consolidation: {result}")
        else:
            print(f"  ❌ Consolidation failed: {result}")

        self.results["consolidation"]["details"].append({
            "name": "Memory consolidation",
            "passed": passed,
            "result": result,
        })

        os.unlink(db)



    def _eval_health_monitoring(self):
        """Test: Memory health monitoring - freshness, consistency, coverage."""
        print("\n[7/8] Health Monitoring")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Create diverse memories
        mm.ingest_conversation([
            {"role": "user", "content": "我们决定用React作为前端框架"},
            {"role": "user", "content": "数据库用的是PostgreSQL"},
            {"role": "user", "content": "我喜欢用Python"},
            {"role": "user", "content": "部署在AWS上"},
        ], owner="test", session_key="s1")

        self.results["health_monitoring"]["total"] += 1
        health = mm.check_memory_health(owner="test")

        passed = (
            health["overall_score"] > 0.5
            and health["freshness"]["score"] > 0
            and health["consistency"]["score"] > 0
            and health["coverage"]["score"] > 0
        )

        if passed:
            self.results["health_monitoring"]["passed"] += 1
            print(f"  ✅ Health: overall={health['overall_score']:.2f} freshness={health['freshness']['score']:.2f} consistency={health['consistency']['score']:.2f} coverage={health['coverage']['score']:.2f}")
        else:
            print(f"  ❌ Health check failed: {health}")

        self.results["health_monitoring"]["details"].append({
            "name": "Memory health monitoring",
            "passed": passed,
            "score": health["overall_score"],
        })

        os.unlink(db)

    def _eval_cross_agent_sharing(self):
        """Test: Cross-agent memory sharing."""
        print("\n[8/8] Cross-Agent Sharing")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Alice creates memories
        mm.ingest_conversation([
            {"role": "user", "content": "我们决定用React作为前端框架"},
            {"role": "user", "content": "数据库用的是PostgreSQL"},
        ], owner="alice", session_key="s1")

        # Share Alice's decision with Bob
        self.results["cross_agent_sharing"]["total"] += 1
        decisions = store.search_decisions(owner="alice", limit=5)
        shared = mm.share_memory("decision", decisions[0]["id"], "bob")

        # Bob can recall the shared memory
        bob_recall = mm.recall("React", owner="bob")
        bob_has_shared = len(bob_recall.get("decisions", [])) > 0

        passed = shared and bob_has_shared

        if passed:
            self.results["cross_agent_sharing"]["passed"] += 1
            print(f"  ✅ Cross-agent sharing: Alice -> Bob, Bob recalled {len(bob_recall['decisions'])} decision(s)")
        else:
            print(f"  ❌ Cross-agent sharing failed: shared={shared}, bob_recall={len(bob_recall.get('decisions', []))}")

        self.results["cross_agent_sharing"]["details"].append({
            "name": "Cross-agent sharing (Alice -> Bob)",
            "passed": passed,
        })

        os.unlink(db)


    def _eval_memory_forgetting(self):
        """Test: Memory forgetting - superseded memories are properly forgotten."""
        print("\n[9/10] Memory Forgetting")
        print("-" * 40)

        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Create and contradict a decision
        mm.ingest_conversation([{"role": "user", "content": "我们决定用React作为前端框架"}], owner="test", session_key="s1")
        mm.ingest_conversation([{"role": "user", "content": "我们最终决定切换到Vue"}], owner="test", session_key="s2")

        # Auto-forget (force=True to skip age check)
        self.results["memory_forgetting"]["total"] += 1
        result = store.auto_forget(owner="test", max_age_days=0, force=True)
        forgotten = store.execute_forgetting(owner="test")

        # Verify: superseded decision should be forgotten
        decisions = store.search_decisions(owner="test", limit=10)
        active = [d for d in decisions if d["status"] == "active"]
        forgotten_decs = [d for d in decisions if d["status"] == "forgotten"]

        passed = (
            len(active) >= 1
            and len(forgotten_decs) >= 1
            and any("Vue" in (d.get("chosen", "") or "") for d in active)
            and any("React" in (d.get("chosen", "") or "") for d in forgotten_decs)
        )

        if passed:
            self.results["memory_forgetting"]["passed"] += 1
            print(f"  ✅ Forgetting: active={len(active)}, forgotten={len(forgotten_decs)}")
        else:
            print(f"  ❌ Forgetting failed: active={len(active)}, forgotten={len(forgotten_decs)}")

        self.results["memory_forgetting"]["details"].append({
            "name": "Superseded decision forgetting",
            "passed": passed,
        })

        os.unlink(db)

    def _check_latest_decision(self, recall, expected_chosen):
        """Check if the active decision has the expected chosen value."""
        for d in recall.get("decisions", []):
            if d.get("status") == "active" and expected_chosen in (d.get("chosen", "") or ""):
                return True
        return False

    def _check_latest_preference(self, recall, expected_value):
        """Check if the preference has the expected value."""
        for p in recall.get("preferences", []):
            if expected_value in (p.get("value", "") or ""):
                return True
        return False

    def _check_decision_superseded(self, recall, chosen_value):
        """Check if a decision with the given chosen value is superseded."""
        for d in recall.get("decisions", []):
            if d.get("status") == "superseded" and chosen_value in (d.get("chosen", "") or ""):
                return True
        return False

    def _print_summary(self):
        """Print evaluation summary."""
        print("\n" + "=" * 60)
        print("MEMORY LIFECYCLE EVALUATION SUMMARY")
        print("=" * 60)

        total_passed = 0
        total_tests = 0

        # Include all categories including consolidation
        for category, data in self.results.items():
            passed = data["passed"]
            total = data["total"]
            total_passed += passed
            total_tests += total
            
            pct = (passed / total * 100) if total > 0 else 0
            status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
            print(f"  {status} {category}: {passed}/{total} ({pct:.0f}%)")

        overall = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"\n  Overall: {total_passed}/{total_tests} ({overall:.1f}%)")
        
        # Memory capability assessment
        print("\n  Memory Capabilities:")
        caps = {
            "Fact Extraction": self.results["fact_extraction"]["passed"] > 0,
            "Contradiction Detection": self.results["contradiction_detection"]["passed"] > 0,
            "Unified Recall": self.results["unified_recall"]["passed"] > 0,
            "Memory Consistency": self.results["memory_consistency"]["passed"] > 0,
            "Temporal Ordering": self.results["temporal_ordering"]["passed"] > 0,
            "Memory Consolidation": self.results.get("consolidation", {}).get("passed", 0) > 0,
            "Health Monitoring": self.results.get("health_monitoring", {}).get("passed", 0) > 0,
            "Cross-Agent Sharing": self.results.get("cross_agent_sharing", {}).get("passed", 0) > 0,
            "Memory Forgetting": self.results.get("memory_forgetting", {}).get("passed", 0) > 0,
        }
        for cap, available in caps.items():
            print(f"    {'✅' if available else '❌'} {cap}")

        print("=" * 60)


def main():
    evaluator = MemoryLifecycleEval()
    results = evaluator.run_all()

    # Save results
    history_dir = Path(__file__).parent / "history"
    history_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    result_file = history_dir / f"memory_lifecycle_{ts}.json"
    
    with open(result_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults saved to: {result_file}")


if __name__ == "__main__":
    main()
