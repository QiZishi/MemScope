"""Memory Architecture Performance Evaluation.

Measures ACTUAL PERFORMANCE with metrics, not pass/fail.

Metrics:
1. Fact Extraction: Precision / Recall / F1 on extracted facts
2. Contradiction Detection: Detection Rate / False Positive Rate
3. Retrieval: Recall@k / MRR / F1 (existing direct_api_eval)
4. Proactive Recommendation: Relevance@k
5. Forgetting: Correctness (should-forgotten vs actually-forgotten)
"""

import sys
import os
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.store import SqliteStore
from core.fact_extractor import FactExtractor, MemoryManager


# ============================================================
# Test Data: Annotated ground truth for each capability
# ============================================================

FACT_EXTRACTION_TEST_DATA = [
    {
        "input": "我们决定用React作为前端框架",
        "expected_facts": {
            "decisions": [{"title_contains": "前端框架", "chosen_contains": "React"}],
            "preferences": [],
            "knowledge": [],
        },
    },
    {
        "input": "我喜欢用Python写代码",
        "expected_facts": {
            "decisions": [],
            "preferences": [{"key_contains": "编程语言", "value_contains": "Python"}],
            "knowledge": [],
        },
    },
    {
        "input": "项目数据库用的是PostgreSQL",
        "expected_facts": {
            "decisions": [],
            "preferences": [],
            "knowledge": [{"topic_contains": "PostgreSQL"}],
        },
    },
    {
        "input": "我们决定用Docker部署，数据库用MySQL",
        "expected_facts": {
            "decisions": [{"chosen_contains": "Docker"}],
            "preferences": [],
            "knowledge": [{"topic_contains": "MySQL"}],
        },
    },
    {
        "input": "今天天气不错",
        "expected_facts": {
            "decisions": [],
            "preferences": [],
            "knowledge": [],
        },
    },
    {
        "input": "我们最终确认使用PostgreSQL，不用MySQL了",
        "expected_facts": {
            "decisions": [{"chosen_contains": "PostgreSQL"}],
            "preferences": [],
            "knowledge": [],
        },
    },
    {
        "input": "我更喜欢用Go语言，不要用Python了",
        "expected_facts": {
            "decisions": [],
            "preferences": [{"key_contains": "编程语言", "value_contains": "Go"}],
            "knowledge": [],
        },
    },
    {
        "input": "部署在AWS上，版本是3.2.1",
        "expected_facts": {
            "decisions": [],
            "preferences": [],
            "knowledge": [{"topic_contains": "AWS"}],
        },
    },
    {
        "input": "框架用的是FastAPI",
        "expected_facts": {
            "decisions": [],
            "preferences": [],
            "knowledge": [{"topic_contains": "FastAPI"}],
        },
    },
    {
        "input": "我们决定用Kafka作为消息队列，监控用Prometheus",
        "expected_facts": {
            "decisions": [{"chosen_contains": "Kafka"}],
            "preferences": [],
            "knowledge": [],
        },
    },
]

CONTRADICTION_TEST_DATA = [
    {
        "sequence": [
            "我们决定用React作为前端框架",
            "我们最终决定把前端框架切换到Vue",
        ],
        "expected_contradictions": 1,
        "expected_final_chosen": "Vue",
    },
    {
        "sequence": [
            "我喜欢用Python",
            "我更喜欢用Go，不要用Python了",
        ],
        "expected_contradictions": 1,
        "expected_final_value": "Go",
    },
    {
        "sequence": [
            "我们决定用React作为前端框架",
            "我们决定用PostgreSQL作为数据库",
        ],
        "expected_contradictions": 0,
    },
    {
        "sequence": [
            "项目数据库用的是MySQL",
            "经过性能测试，我们切换到PostgreSQL",
            "最终确认使用PostgreSQL",
        ],
        "expected_contradictions": 1,  # MySQL->PostgreSQL is a contradiction
        "expected_final_chosen": "PostgreSQL",
    },
]

RETRIEVAL_TEST_DATA = [
    {
        "setup": [
            "我们决定用React作为前端框架",
            "数据库用的是PostgreSQL",
            "部署在AWS上",
            "我喜欢用VS Code",
            "消息队列用RabbitMQ",
        ],
        "queries": [
            {"query": "React", "should_find": "React"},
            {"query": "PostgreSQL", "should_find": "PostgreSQL"},
            {"query": "AWS", "should_find": "AWS"},
            {"query": "前端框架", "should_find": "React"},
            {"query": "数据库", "should_find": "PostgreSQL"},
        ],
    },
]


# ============================================================
# Metric Calculation Functions
# ============================================================

def calc_precision_recall_f1(
    expected: List[str], actual: List[str]
) -> Tuple[float, float, float]:
    """Calculate precision, recall, F1 between expected and actual lists."""
    if not expected and not actual:
        return 1.0, 1.0, 1.0
    if not actual:
        return 0.0, 0.0, 0.0
    if not expected:
        return 0.0, 1.0, 0.0

    expected_set = set(e.lower() for e in expected)
    actual_set = set(a.lower() for a in actual)

    true_positives = len(expected_set & actual_set)
    precision = true_positives / len(actual_set) if actual_set else 0
    recall = true_positives / len(expected_set) if expected_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return precision, recall, f1


def contains_match(expected_substring: str, actual_text: str) -> bool:
    """Check if expected substring appears in actual text."""
    return expected_substring.lower() in actual_text.lower()


# ============================================================
# Evaluation Functions
# ============================================================

def eval_fact_extraction_performance() -> Dict[str, float]:
    """Evaluate fact extraction with Precision/Recall/F1."""
    print("\n" + "=" * 60)
    print("1. FACT EXTRACTION PERFORMANCE")
    print("=" * 60)

    total_decisions_expected = 0
    total_decisions_actual = 0
    total_decisions_correct = 0

    total_preferences_expected = 0
    total_preferences_actual = 0
    total_preferences_correct = 0

    total_knowledge_expected = 0
    total_knowledge_actual = 0
    total_knowledge_correct = 0

    for i, test in enumerate(FACT_EXTRACTION_TEST_DATA):
        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        expected = test["expected_facts"]

        # Extract facts
        result = mm.ingest_conversation(
            [{"role": "user", "content": test["input"]}],
            owner="test",
            session_key=f"s{i}",
        )

        # Count decisions
        expected_decisions = expected.get("decisions", [])
        actual_decisions = result["facts_extracted"]["decisions"]
        total_decisions_expected += len(expected_decisions)
        total_decisions_actual += actual_decisions

        # Check if expected decisions were found
        if expected_decisions:
            db_decisions = store.search_decisions(owner="test", limit=10)
            for exp in expected_decisions:
                found = False
                for d in db_decisions:
                    if contains_match(exp.get("title_contains", ""), d.get("title", "")) and \
                       contains_match(exp.get("chosen_contains", ""), d.get("chosen", "")):
                        found = True
                        break
                if found:
                    total_decisions_correct += 1

        # Count preferences
        expected_prefs = expected.get("preferences", [])
        actual_prefs = result["facts_extracted"]["preferences"]
        total_preferences_expected += len(expected_prefs)
        total_preferences_actual += actual_prefs

        if expected_prefs:
            db_prefs = store.list_preferences(owner="test")
            for exp in expected_prefs:
                found = False
                for p in db_prefs:
                    key_ok = contains_match(exp.get("key_contains", ""), p.get("key", ""))
                    val_ok = contains_match(exp.get("value_contains", ""), p.get("value", "")) if exp.get("value_contains") else True
                    if key_ok and val_ok:
                        found = True
                        break
                if found:
                    total_preferences_correct += 1

        # Count knowledge
        expected_kn = expected.get("knowledge", [])
        actual_kn = result["facts_extracted"]["knowledge"]
        total_knowledge_expected += len(expected_kn)
        total_knowledge_actual += actual_kn

        if expected_kn:
            cursor = store.conn.cursor()
            cursor.execute("SELECT topic FROM knowledge_health WHERE owner = ?", ("test",))
            db_topics = [row[0] for row in cursor.fetchall()]
            for exp in expected_kn:
                found = any(contains_match(exp.get("topic_contains", ""), t) for t in db_topics)
                if found:
                    total_knowledge_correct += 1

        os.unlink(db)

    # Calculate overall metrics
    total_expected = total_decisions_expected + total_preferences_expected + total_knowledge_expected
    total_actual = total_decisions_actual + total_preferences_actual + total_knowledge_actual
    total_correct = total_decisions_correct + total_preferences_correct + total_knowledge_correct

    precision = total_correct / total_actual if total_actual > 0 else 0
    recall = total_correct / total_expected if total_expected > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n  Decisions:   expected={total_decisions_expected} actual={total_decisions_actual} correct={total_decisions_correct}")
    print(f"  Preferences: expected={total_preferences_expected} actual={total_preferences_actual} correct={total_preferences_correct}")
    print(f"  Knowledge:   expected={total_knowledge_expected} actual={total_knowledge_actual} correct={total_knowledge_correct}")
    print(f"\n  Overall:")
    print(f"    Precision: {precision:.1%} ({total_correct}/{total_actual})")
    print(f"    Recall:    {recall:.1%} ({total_correct}/{total_expected})")
    print(f"    F1:        {f1:.1%}")

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "total_expected": total_expected,
        "total_actual": total_actual,
        "total_correct": total_correct,
    }


def eval_contradiction_detection_performance() -> Dict[str, float]:
    """Evaluate contradiction detection with Detection Rate / False Positive Rate."""
    print("\n" + "=" * 60)
    print("2. CONTRADICTION DETECTION PERFORMANCE")
    print("=" * 60)

    total_contradictions_expected = 0
    total_contradictions_detected = 0
    total_false_positives = 0
    total_correct_final = 0
    total_final_checks = 0

    for i, test in enumerate(CONTRADICTION_TEST_DATA):
        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        total_detected = 0
        for j, msg in enumerate(test["sequence"]):
            r = mm.ingest_conversation(
                [{"role": "user", "content": msg}],
                owner="test",
                session_key=f"s{i}_{j}",
            )
            total_detected += r["contradictions_resolved"]

        expected_contradictions = test["expected_contradictions"]
        total_contradictions_expected += expected_contradictions

        # Count true positives (detected contradictions that were expected)
        if expected_contradictions > 0:
            total_contradictions_detected += min(total_detected, expected_contradictions)
        else:
            # False positive: detected contradiction where none expected
            total_false_positives += max(0, total_detected - expected_contradictions)

        # Check final value
        if "expected_final_chosen" in test:
            total_final_checks += 1
            decisions = store.search_decisions(owner="test", limit=10)
            active = [d for d in decisions if d.get("status") == "active"]
            if active and contains_match(test["expected_final_chosen"], active[0].get("chosen", "")):
                total_correct_final += 1

        if "expected_final_value" in test:
            total_final_checks += 1
            prefs = store.list_preferences(owner="test")
            if prefs:
                # Find the most relevant preference
                for p in prefs:
                    if contains_match(test["expected_final_value"], p.get("value", "")):
                        total_correct_final += 1
                        break

        os.unlink(db)

    detection_rate = total_contradictions_detected / total_contradictions_expected if total_contradictions_expected > 0 else 0
    final_accuracy = total_correct_final / total_final_checks if total_final_checks > 0 else 0

    print(f"\n  Contradictions expected: {total_contradictions_expected}")
    print(f"  Contradictions detected: {total_contradictions_detected}")
    print(f"  False positives: {total_false_positives}")
    print(f"  Detection Rate: {detection_rate:.1%}")
    print(f"  Final Value Accuracy: {final_accuracy:.1%} ({total_correct_final}/{total_final_checks})")

    return {
        "detection_rate": detection_rate,
        "false_positives": total_false_positives,
        "final_accuracy": final_accuracy,
    }


def eval_retrieval_performance() -> Dict[str, float]:
    """Evaluate retrieval with Recall@k and MRR."""
    print("\n" + "=" * 60)
    print("3. RETRIEVAL PERFORMANCE (Recall@k / MRR)")
    print("=" * 60)

    recall_at_1 = []
    recall_at_3 = []
    recall_at_5 = []
    mrr_scores = []

    for test in RETRIEVAL_TEST_DATA:
        db = tempfile.mktemp(suffix='.db')
        store = SqliteStore(db)
        mm = MemoryManager(store)

        # Setup
        for j, msg in enumerate(test["setup"]):
            store.insert_chunk({
                "sessionKey": "test",
                "turnId": f"turn_{j}",
                "seq": j,
                "role": "user",
                "content": msg,
                "owner": "test",
            })

        # Query
        for q in test["queries"]:
            results = store.search_chunks(q["query"], max_results=5)
            found_contents = [r.get("content", "") for r in results]
            should_find = q["should_find"].lower()

            # Recall@k
            r1 = 1 if any(should_find in c.lower() for c in found_contents[:1]) else 0
            r3 = 1 if any(should_find in c.lower() for c in found_contents[:3]) else 0
            r5 = 1 if any(should_find in c.lower() for c in found_contents[:5]) else 0

            recall_at_1.append(r1)
            recall_at_3.append(r3)
            recall_at_5.append(r5)

            # MRR
            for rank, content in enumerate(found_contents, 1):
                if should_find in content.lower():
                    mrr_scores.append(1.0 / rank)
                    break
            else:
                mrr_scores.append(0.0)

        os.unlink(db)

    avg_r1 = sum(recall_at_1) / len(recall_at_1) if recall_at_1 else 0
    avg_r3 = sum(recall_at_3) / len(recall_at_3) if recall_at_3 else 0
    avg_r5 = sum(recall_at_5) / len(recall_at_5) if recall_at_5 else 0
    avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0

    print(f"\n  Samples: {len(recall_at_1)}")
    print(f"  Recall@1: {avg_r1:.1%}")
    print(f"  Recall@3: {avg_r3:.1%}")
    print(f"  Recall@5: {avg_r5:.1%}")
    print(f"  MRR:      {avg_mrr:.1%}")

    return {
        "recall_at_1": avg_r1,
        "recall_at_3": avg_r3,
        "recall_at_5": avg_r5,
        "mrr": avg_mrr,
    }


def eval_proactive_recommendation_relevance() -> Dict[str, float]:
    """Evaluate proactive recommendation relevance."""
    print("\n" + "=" * 60)
    print("4. PROACTIVE RECOMMENDATION RELEVANCE")
    print("=" * 60)

    # Test: given a memory base, how relevant are proactive recommendations?
    db = tempfile.mktemp(suffix='.db')
    store = SqliteStore(db)
    mm = MemoryManager(store)

    # Build memory base
    mm.ingest_conversation([
        {"role": "user", "content": "我们决定用React作为前端框架"},
        {"role": "user", "content": "数据库用的是PostgreSQL"},
        {"role": "user", "content": "部署在AWS上"},
        {"role": "user", "content": "我喜欢用Python"},
        {"role": "user", "content": "消息队列用RabbitMQ"},
    ], owner="test", session_key="s1")
    mm.consolidate_memories(owner="test")

    # Test queries with expected relevant topics
    test_queries = [
        {"query": "我们需要优化数据库查询", "expected_topics": ["PostgreSQL", "数据库"]},
        {"query": "前端框架选型讨论", "expected_topics": ["React", "前端"]},
        {"query": "部署架构规划", "expected_topics": ["AWS", "Docker", "部署"]},
        {"query": "选择编程语言", "expected_topics": ["Python"]},
        {"query": "今天午饭吃什么", "expected_topics": []},  # No relevant topics
    ]

    total_relevant = 0
    total_recommended = 0
    total_expected_relevant = 0
    false_positive_queries = 0

    for tq in test_queries:
        rec = mm.proactive_recommend(tq["query"], owner="test")
        recommended = rec.get("recommendations", [])
        expected = tq["expected_topics"]

        total_recommended += len(recommended)
        total_expected_relevant += len(expected)

        # Count how many recommendations are relevant
        for r in recommended:
            rec_text = json.dumps(r, ensure_ascii=False).lower()
            for topic in expected:
                if topic.lower() in rec_text:
                    total_relevant += 1
                    break

        # False positive: recommendations when none expected
        if not expected and recommended:
            false_positive_queries += 1

    precision = total_relevant / total_recommended if total_recommended > 0 else 0
    recall = total_relevant / total_expected_relevant if total_expected_relevant > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n  Total recommended: {total_recommended}")
    print(f"  Total relevant: {total_relevant}")
    print(f"  Total expected relevant: {total_expected_relevant}")
    print(f"  False positive queries: {false_positive_queries}")
    print(f"\n  Precision: {precision:.1%}")
    print(f"  Recall:    {recall:.1%}")
    print(f"  F1:        {f1:.1%}")

    os.unlink(db)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_queries": false_positive_queries,
    }


def eval_full_retrieval() -> Dict[str, float]:
    """Run the full 240-sample retrieval evaluation."""
    print("\n" + "=" * 60)
    print("5. FULL RETRIEVAL (240 samples)")
    print("=" * 60)
    print("  Running eval/direct_api_eval.py...")

    import subprocess
    result = subprocess.run(
        [sys.executable, "eval/direct_api_eval.py"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )

    # Parse output for key metrics
    metrics = {}
    for line in result.stdout.split('\n'):
        if 'Recall@1' in line and ':' in line:
            try:
                metrics['recall_at_1'] = float(line.split(':')[1].strip().replace('%', '')) / 100
            except (ValueError, IndexError):
                pass
        if 'MRR' in line and ':' in line:
            try:
                metrics['mrr'] = float(line.split(':')[1].strip().replace('%', '')) / 100
            except (ValueError, IndexError):
                pass
        if 'F1' in line and ':' in line:
            try:
                metrics['f1'] = float(line.split(':')[1].strip().replace('%', '')) / 100
            except (ValueError, IndexError):
                pass
        if '综合评分' in line and ':' in line:
            try:
                metrics['composite'] = float(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass

    if metrics:
        print(f"\n  Recall@1: {metrics.get('recall_at_1', 0):.1%}")
        print(f"  MRR:      {metrics.get('mrr', 0):.1%}")
        print(f"  F1:       {metrics.get('f1', 0):.1%}")
        print(f"  Composite: {metrics.get('composite', 0):.1f}")
    else:
        print("  Could not parse metrics from output")

    return metrics


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("MemScope Memory Architecture — Performance Evaluation")
    print("=" * 60)
    print("\nThis evaluation measures ACTUAL PERFORMANCE with metrics,")
    print("not just pass/fail code testing.\n")

    all_metrics = {}

    # 1. Fact Extraction
    all_metrics["fact_extraction"] = eval_fact_extraction_performance()

    # 2. Contradiction Detection
    all_metrics["contradiction_detection"] = eval_contradiction_detection_performance()

    # 3. Retrieval (small scale)
    all_metrics["retrieval"] = eval_retrieval_performance()

    # 4. Proactive Recommendation
    all_metrics["proactive_recommendation"] = eval_proactive_recommendation_relevance()

    # 5. Full Retrieval (240 samples)
    all_metrics["full_retrieval"] = eval_full_retrieval()

    # ============================================================
    # Final Summary
    # ============================================================
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    print(f"\n  Fact Extraction:")
    print(f"    Precision: {all_metrics['fact_extraction']['precision']:.1%}")
    print(f"    Recall:    {all_metrics['fact_extraction']['recall']:.1%}")
    print(f"    F1:        {all_metrics['fact_extraction']['f1']:.1%}")

    print(f"\n  Contradiction Detection:")
    print(f"    Detection Rate: {all_metrics['contradiction_detection']['detection_rate']:.1%}")
    print(f"    Final Accuracy: {all_metrics['contradiction_detection']['final_accuracy']:.1%}")

    print(f"\n  Retrieval (small scale):")
    print(f"    Recall@1: {all_metrics['retrieval']['recall_at_1']:.1%}")
    print(f"    Recall@5: {all_metrics['retrieval']['recall_at_5']:.1%}")
    print(f"    MRR:      {all_metrics['retrieval']['mrr']:.1%}")

    print(f"\n  Proactive Recommendation:")
    print(f"    Precision: {all_metrics['proactive_recommendation']['precision']:.1%}")
    print(f"    Recall:    {all_metrics['proactive_recommendation']['recall']:.1%}")
    print(f"    F1:        {all_metrics['proactive_recommendation']['f1']:.1%}")

    if all_metrics.get("full_retrieval"):
        print(f"\n  Full Retrieval (240 samples):")
        print(f"    Recall@1:  {all_metrics['full_retrieval'].get('recall_at_1', 0):.1%}")
        print(f"    MRR:       {all_metrics['full_retrieval'].get('mrr', 0):.1%}")
        print(f"    Composite: {all_metrics['full_retrieval'].get('composite', 0):.1f}")

    # Save
    history_dir = Path(__file__).parent / "history"
    history_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    result_file = history_dir / f"performance_eval_{ts}.json"
    with open(result_file, "w") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {result_file}")

    print("=" * 60)


if __name__ == "__main__":
    main()
