"""End-to-End Memory System Integration Test.

Tests all 10 Memory capabilities working together in a realistic scenario:
1. A team conversation flows in (fact extraction)
2. Contradictions are detected and resolved
3. Memories are consolidated into higher-level knowledge
4. Health is monitored
5. Memories are shared across agents
6. Outdated memories are forgotten
7. New conversations trigger proactive recommendations
8. Session start triggers prefetch briefing

This is the ultimate integration test for the MemScope Memory system.
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


def run_end_to_end():
    """Run the complete end-to-end integration test."""
    print("=" * 60)
    print("MemScope End-to-End Integration Test")
    print("=" * 60)

    db = tempfile.mktemp(suffix='.db')
    store = SqliteStore(db)
    mm = MemoryManager(store)

    results = {}
    total_tests = 0
    passed_tests = 0

    # ========== Phase 1: Team Conversation Ingestion ==========
    print("\n[Phase 1] Team Conversation Ingestion")
    print("-" * 40)

    # Day 1: Initial tech decisions
    r1 = mm.ingest_conversation([
        {"role": "user", "content": "我们决定用React作为前端框架，不用Vue了"},
        {"role": "assistant", "content": "好的，React确实更适合这个项目"},
        {"role": "user", "content": "数据库用的是PostgreSQL"},
        {"role": "user", "content": "我喜欢用VS Code写Python"},
        {"role": "user", "content": "部署在AWS上，用Docker容器化"},
    ], owner="team", session_key="day1")

    total_tests += 1
    if r1["facts_extracted"]["decisions"] >= 1 and r1["facts_extracted"]["knowledge"] >= 1:
        passed_tests += 1
        print(f"  ✅ Ingested: {r1['facts_extracted']} facts, {r1['chunks_stored']} chunks")
    else:
        print(f"  ❌ Ingestion failed: {r1['facts_extracted']}")

    results["ingestion"] = {"passed": r1["facts_extracted"]["decisions"] >= 1}

    # ========== Phase 2: Contradiction Detection ==========
    print("\n[Phase 2] Contradiction Detection")
    print("-" * 40)

    # Day 5: Framework change
    r2 = mm.ingest_conversation([
        {"role": "user", "content": "经过性能测试，我们决定把前端框架切换到Vue"},
        {"role": "user", "content": "数据库也从PostgreSQL切换到MySQL"},
    ], owner="team", session_key="day5")

    total_tests += 1
    if r2["contradictions_resolved"] >= 1:
        passed_tests += 1
        print(f"  ✅ Contradictions resolved: {r2['contradictions_resolved']}")
    else:
        print(f"  ❌ No contradictions detected")

    results["contradiction"] = {"passed": r2["contradictions_resolved"] >= 1}

    # Verify consistency
    total_tests += 1
    recall = mm.recall("前端框架", owner="team")
    active_decisions = [d for d in recall["decisions"] if d.get("status") == "active"]
    if active_decisions and "Vue" in active_decisions[0].get("chosen", ""):
        passed_tests += 1
        print(f"  ✅ Latest value returned: {active_decisions[0]['chosen']}")
    else:
        print(f"  ❌ Consistency check failed")
    results["consistency"] = {"passed": "Vue" in str(active_decisions)}

    # ========== Phase 3: Memory Consolidation ==========
    print("\n[Phase 3] Memory Consolidation")
    print("-" * 40)

    consolidation = mm.consolidate_memories(owner="team")
    total_tests += 1
    if consolidation["decision_timelines"] >= 1:
        passed_tests += 1
        print(f"  ✅ Consolidated: {consolidation}")
    else:
        print(f"  ❌ Consolidation failed: {consolidation}")
    results["consolidation"] = {"passed": consolidation["decision_timelines"] >= 1}

    # ========== Phase 4: Health Monitoring ==========
    print("\n[Phase 4] Health Monitoring")
    print("-" * 40)

    health = mm.check_memory_health(owner="team")
    total_tests += 1
    if health["overall_score"] > 0.5:
        passed_tests += 1
        print(f"  ✅ Health: overall={health['overall_score']:.2f}")
    else:
        print(f"  ❌ Health too low: {health['overall_score']:.2f}")
    results["health"] = {"passed": health["overall_score"] > 0.5, "score": health["overall_score"]}

    # ========== Phase 5: Cross-Agent Sharing ==========
    print("\n[Phase 5] Cross-Agent Sharing")
    print("-" * 40)

    # Share an ACTIVE decision that matches our test query
    all_decisions = store.search_decisions(owner="team", limit=10)
    active_decisions = [d for d in all_decisions if d.get("status") == "active"]
    shared = False
    target_decision = None
    for d in active_decisions:
        if "Vue" in (d.get("chosen", "") or ""):
            target_decision = d
            break
    if not target_decision and active_decisions:
        target_decision = active_decisions[0]
    if target_decision:
        shared = mm.share_memory("decision", target_decision["id"], "new_member")
    new_member_recall = mm.recall(target_decision.get("chosen", "Vue") if target_decision else "Vue", owner="new_member")

    total_tests += 1
    if shared and len(new_member_recall["decisions"]) > 0:
        passed_tests += 1
        print(f"  ✅ Shared decision recalled by new_member")
    else:
        print(f"  ❌ Sharing failed")
    results["sharing"] = {"passed": shared and len(new_member_recall["decisions"]) > 0}

    # ========== Phase 6: Memory Forgetting ==========
    print("\n[Phase 6] Memory Forgetting")
    print("-" * 40)

    forget_result = store.auto_forget(owner="team", max_age_days=0, force=True)
    forgotten = store.execute_forgetting(owner="team")

    total_tests += 1
    if forgotten.get("decision", 0) >= 1:
        passed_tests += 1
        print(f"  ✅ Forgotten: {forgotten}")
    else:
        print(f"  ❌ Nothing forgotten: {forgotten}")
    results["forgetting"] = {"passed": forgotten.get("decision", 0) >= 1}

    # ========== Phase 7: Proactive Recommendation ==========
    print("\n[Phase 7] Proactive Recommendation")
    print("-" * 40)

    rec = mm.proactive_recommend("我们需要优化数据库查询性能", owner="team")
    total_tests += 1
    if len(rec["recommendations"]) > 0:
        passed_tests += 1
        print(f"  ✅ Recommended {len(rec['recommendations'])} memories, topics={rec['topics_detected']}")
    else:
        print(f"  ❌ No recommendations")
    results["proactive"] = {"passed": len(rec["recommendations"]) > 0}

    # ========== Phase 8: Session Prefetch ==========
    print("\n[Phase 8] Session Prefetch")
    print("-" * 40)

    briefing = mm.prefetch(session_key="new_session", owner="team")
    total_tests += 1
    has_briefing = (
        len(briefing.get("recent_decisions", [])) > 0
        or len(briefing.get("knowledge_summary", [])) > 0
    )
    if has_briefing:
        passed_tests += 1
        print(f"  ✅ Prefetch: decisions={len(briefing['recent_decisions'])} knowledge={len(briefing['knowledge_summary'])}")
    else:
        print(f"  ❌ Empty briefing")
    results["prefetch"] = {"passed": has_briefing}

    # ========== Phase 9: Memory Summary ==========
    print("\n[Phase 9] Memory Summary")
    print("-" * 40)

    summary = mm.get_memory_summary(owner="team")
    print(f"  Chunks: {summary['chunks']}")
    print(f"  Decisions: {summary['decisions']['total']} (active: {summary['decisions']['active']}, superseded: {summary['decisions']['superseded']})")
    print(f"  Preferences: {summary['preferences']}")
    print(f"  Knowledge: {summary['knowledge']}")

    # ========== Final Summary ==========
    print("\n" + "=" * 60)
    print("END-TO-END INTEGRATION TEST RESULTS")
    print("=" * 60)

    for name, result in results.items():
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {name}")

    overall_pct = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"\n  Overall: {passed_tests}/{total_tests} ({overall_pct:.1f}%)")

    # Save results
    history_dir = Path(__file__).parent / "history"
    history_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    result_file = history_dir / f"e2e_integration_{ts}.json"

    with open(result_file, "w") as f:
        json.dump({
            "results": results,
            "total": total_tests,
            "passed": passed_tests,
            "percentage": overall_pct,
            "summary": summary,
        }, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {result_file}")

    os.unlink(db)
    return passed_tests, total_tests


if __name__ == "__main__":
    passed, total = run_end_to_end()
    sys.exit(0 if passed == total else 1)
