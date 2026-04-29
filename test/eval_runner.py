#!/usr/bin/env python3
"""
Enterprise Memory Engine — Evaluation Runner

Runs all test suites and produces a comprehensive JSON report with:
  - Per-test metrics
  - Per-dimension scores (weighted)
  - Overall weighted score
  - Timestamps and system info

Usage:
    python eval_runner.py [--output eval_results.json] [--verbose]
"""

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Scoring weights (from evaluation_scheme.md)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "anti_interference": 0.15,
    "contradiction_update": 0.15,
    "efficiency": 0.15,
    "direction_a": 0.10,
    "direction_b": 0.15,
    "direction_c": 0.15,
    "direction_d": 0.15,
}

SUB_DIMENSION_WEIGHTS = {
    "anti_interference": {
        "recall": 0.30,
        "precision": 0.30,
        "noise_injection_rate": 0.20,
        "f1_score": 0.20,
    },
    "contradiction_update": {
        "latest_accuracy": 0.35,
        "history_preservation": 0.25,
        "temporal_sort": 0.20,
        "partial_update_fidelity": 0.20,
    },
    "efficiency": {
        "write_latency": 0.25,
        "query_latency": 0.30,
        "memory_usage": 0.15,
        "token_efficiency": 0.15,
        "concurrency": 0.15,
    },
    "direction_a": {
        "tracking_accuracy": 0.30,
        "frequency_ranking": 0.25,
        "project_association": 0.25,
        "context_recommendation": 0.20,
    },
    "direction_b": {
        "extraction_accuracy": 0.30,
        "search_precision": 0.25,
        "card_relevance": 0.25,
        "lifecycle_tracking": 0.20,
    },
    "direction_c": {
        "preference_recall": 0.25,
        "preference_update_accuracy": 0.25,
        "history_traceability": 0.20,
        "context_awareness": 0.15,
        "preference_distinction": 0.15,
    },
    "direction_d": {
        "gap_detection_rate": 0.25,
        "alert_timeliness": 0.25,
        "conflict_identification": 0.20,
        "coverage_accuracy": 0.15,
        "security_compliance": 0.15,
    },
}

# Test-to-dimension mapping
TEST_DIMENSION_MAP = {
    "anti_interference_001": "anti_interference",
    "anti_interference_002": "anti_interference",
    "anti_interference_003": "anti_interference",
    "anti_interference_004": "anti_interference",
    "anti_interference_005": "anti_interference",
    "contradiction_001": "contradiction_update",
    "contradiction_002": "contradiction_update",
    "contradiction_003": "contradiction_update",
    "contradiction_004": "contradiction_update",
    "contradiction_005": "contradiction_update",
    "efficiency_001": "efficiency",
    "efficiency_002": "efficiency",
    "efficiency_003": "efficiency",
    "efficiency_004": "efficiency",
    "efficiency_005": "efficiency",
    "efficiency_006": "efficiency",
    "direction_a_001": "direction_a",
    "direction_a_002": "direction_a",
    "direction_a_003": "direction_a",
    "direction_a_004": "direction_a",
    "direction_b_001": "direction_b",
    "direction_b_002": "direction_b",
    "direction_b_003": "direction_b",
    "direction_b_004": "direction_b",
    "direction_c_001": "direction_c",
    "direction_c_002": "direction_c",
    "direction_c_003": "direction_c",
    "direction_c_004": "direction_c",
    "direction_d_001": "direction_d",
    "direction_d_002": "direction_d",
    "direction_d_003": "direction_d",
    "direction_d_004": "direction_d",
    "direction_d_005": "direction_d",
}


def calculate_dimension_score(
    test_results: List[Dict[str, Any]],
    dimension: str,
) -> float:
    """Calculate weighted score for a dimension (0-100 scale)."""
    if not test_results:
        return 0.0

    total_score = 0.0
    total_weight = 0.0

    for test in test_results:
        test_metrics = test.get("metrics", {})
        test_passed = test.get("status") == "pass"

        # Each test contributes equally to the dimension
        test_weight = 1.0 / max(len(test_results), 1)

        if test_passed:
            # Full score if passed
            test_score = 100.0
        else:
            # Partial score based on metric pass rate
            passed_count = sum(
                1 for m in test_metrics.values()
                if isinstance(m, dict) and m.get("passed", False)
            )
            total_count = max(
                sum(1 for m in test_metrics.values() if isinstance(m, dict)),
                1,
            )
            test_score = (passed_count / total_count) * 100.0

        total_score += test_score * test_weight
        total_weight += test_weight

    return round(total_score / max(total_weight, 0.01), 2)


def calculate_overall_score(dimension_scores: Dict[str, float]) -> float:
    """Calculate weighted overall score from dimension scores."""
    overall = 0.0
    for dim, weight in SCORING_WEIGHTS.items():
        score = dimension_scores.get(dim, 0.0)
        overall += score * weight
    return round(overall, 2)


def generate_recommendations(
    dimension_scores: Dict[str, float],
    test_results: List[Dict[str, Any]],
) -> List[str]:
    """Generate improvement recommendations based on scores."""
    recs = []

    # Anti-interference recommendations
    ai_score = dimension_scores.get("anti_interference", 0)
    if ai_score < 70:
        recs.append(
            f"Anti-interference score is low ({ai_score:.1f}/100). "
            "Consider improving noise filtering, adding conversation importance scoring, "
            "or implementing relevance-based retrieval."
        )
    elif ai_score < 85:
        recs.append(
            f"Anti-interference score is moderate ({ai_score:.1f}/100). "
            "Consider fine-tuning similarity thresholds and adding deduplication."
        )

    # Contradiction update recommendations
    cu_score = dimension_scores.get("contradiction_update", 0)
    if cu_score < 70:
        recs.append(
            f"Contradiction update score is low ({cu_score:.1f}/100). "
            "Improve temporal ordering, ensure history preservation, "
            "and add conflict resolution logic."
        )

    # Efficiency recommendations
    eff_score = dimension_scores.get("efficiency", 0)
    if eff_score < 70:
        recs.append(
            f"Efficiency score is low ({eff_score:.1f}/100). "
            "Consider optimizing database indexes, adding caching, "
            "or using batch operations for writes."
        )

    # Direction C recommendations
    dc_score = dimension_scores.get("direction_c", 0)
    if dc_score < 70:
        recs.append(
            f"Direction C (preferences) score is low ({dc_score:.1f}/100). "
            "Improve preference extraction, add confidence decay, "
            "and enhance context-aware recommendation logic."
        )

    # Direction D recommendations
    dd_score = dimension_scores.get("direction_d", 0)
    if dd_score < 70:
        recs.append(
            f"Direction D (team knowledge) score is low ({dd_score:.1f}/100). "
            "Improve gap detection algorithms, add freshness monitoring, "
            "and enhance team knowledge map accuracy."
        )

    # Overall recommendation
    overall = calculate_overall_score(dimension_scores)
    if overall >= 85:
        recs.append(
            f"Overall score ({overall:.1f}/100) is excellent! "
            "Focus on edge cases and robustness improvements."
        )
    elif overall >= 70:
        recs.append(
            f"Overall score ({overall:.1f}/100) meets the competition pass threshold. "
            "Target the weakest dimension for maximum score improvement."
        )
    else:
        recs.append(
            f"Overall score ({overall:.1f}/100) is below the competition pass threshold (70). "
            "Prioritize fixing the lowest-scoring dimensions."
        )

    # Find failed tests and provide specific advice
    failed_tests = [t for t in test_results if t.get("status") == "fail"]
    if failed_tests:
        recs.append(
            f"{len(failed_tests)} test(s) failed. Review individual test details "
            "for specific failure modes."
        )

    return recs


def run_pytest_tests(output_path: str, verbose: bool = False) -> List[Dict[str, Any]]:
    """Run pytest tests and collect results via a JSON results file.

    Uses a pytest plugin to write results to a temp file, avoiding the
    singleton re-import issue with _report_collector.
    """
    import pytest as _pytest

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Use a temp file to collect results across pytest invocations
    results_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".eval_results_tmp.json")

    # Write empty list to start
    with open(results_file, "w") as f:
        json.dump([], f)

    class ResultsFilePlugin:
        """Pytest plugin that reads results from the report_collector after each test."""
        def pytest_runtest_teardown(self, item, nextitem):
            # After each test, flush the report_collector to the temp file
            try:
                from conftest import _report_collector
                current = _report_collector.results
                if current:
                    with open(results_file, "w") as f:
                        json.dump(current, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = [
        os.path.join(test_dir, "test_anti_interference.py"),
        os.path.join(test_dir, "test_contradiction_update.py"),
        os.path.join(test_dir, "test_efficiency.py"),
        os.path.join(test_dir, "test_command_memory.py"),
        os.path.join(test_dir, "test_decision_memory.py"),
        os.path.join(test_dir, "test_preference_memory.py"),
        os.path.join(test_dir, "test_knowledge_health.py"),
    ]

    # Filter to existing files only
    existing_files = [f for f in test_files if os.path.exists(f)]
    missing = [os.path.basename(f) for f in test_files if not os.path.exists(f)]
    for m in missing:
        print(f"  WARNING: Test file not found: {m}")

    # Run ALL tests in a single pytest invocation
    print(f"\n  Running {len(existing_files)} test files...")
    args = existing_files + ["-v", "--tb=short", "--no-header"]
    if not verbose:
        args.append("-q")

    try:
        _pytest.main(args, plugins=[ResultsFilePlugin()])
    except SystemExit:
        pass
    except Exception as e:
        print(f"  Error running tests: {e}")

    # Read results from temp file
    try:
        with open(results_file, "r") as f:
            results = json.load(f)
        os.remove(results_file)
        return results
    except Exception:
        return []


def run_direct_tests() -> List[Dict[str, Any]]:
    """Run tests directly without pytest (fallback mode)."""
    import pytest as _pytest

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = [
        os.path.join(test_dir, "test_anti_interference.py"),
        os.path.join(test_dir, "test_contradiction_update.py"),
        os.path.join(test_dir, "test_efficiency.py"),
        os.path.join(test_dir, "test_command_memory.py"),
        os.path.join(test_dir, "test_decision_memory.py"),
        os.path.join(test_dir, "test_preference_memory.py"),
        os.path.join(test_dir, "test_knowledge_health.py"),
    ]

    existing_files = [f for f in test_files if os.path.exists(f)]

    print(f"\n  Running {len(existing_files)} test files...")
    try:
        _pytest.main(
            existing_files + ["-v", "--tb=short", "--no-header", "-q"],
            plugins=[],
        )
    except (SystemExit, Exception):
        pass

    # Collect from the report collector
    from conftest import _report_collector
    return _report_collector.results


def generate_report(
    test_results: List[Dict[str, Any]],
    elapsed_seconds: float,
) -> Dict[str, Any]:
    """Generate the final evaluation report."""

    # Group results by dimension
    by_dimension: Dict[str, List[Dict]] = {}
    for result in test_results:
        test_id = result.get("test_id", "")
        dim = TEST_DIMENSION_MAP.get(test_id, "unknown")
        by_dimension.setdefault(dim, []).append(result)

    # Calculate dimension scores
    dimension_scores = {}
    for dim in SCORING_WEIGHTS:
        dim_results = by_dimension.get(dim, [])
        dimension_scores[dim] = calculate_dimension_score(dim_results, dim)

    # Overall score
    overall_score = calculate_overall_score(dimension_scores)

    # Count pass/fail
    passed = sum(1 for r in test_results if r.get("status") == "pass")
    failed = sum(1 for r in test_results if r.get("status") == "fail")
    errors = sum(1 for r in test_results if r.get("status") == "error")
    skipped = sum(1 for r in test_results if r.get("status") == "skip")

    # Generate recommendations
    recommendations = generate_recommendations(dimension_scores, test_results)

    report = {
        "report_id": f"eval-{uuid.uuid4().hex[:12]}",
        "run_timestamp": datetime.now().isoformat(),
        "system_version": "enterprise-memory v2.0.0",
        "elapsed_seconds": round(elapsed_seconds, 2),
        "summary": {
            "total_tests": len(test_results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": round(passed / max(len(test_results), 1) * 100, 1),
            "overall_score": overall_score,
            "grade": (
                "Excellent" if overall_score >= 85
                else "Good" if overall_score >= 70
                else "Needs Improvement"
            ),
        },
        "dimension_scores": {
            dim: {
                "score": score,
                "weight": SCORING_WEIGHTS[dim],
                "weighted_score": round(score * SCORING_WEIGHTS[dim], 2),
                "test_count": len(by_dimension.get(dim, [])),
                "passed_count": sum(
                    1 for t in by_dimension.get(dim, []) if t.get("status") == "pass"
                ),
            }
            for dim, score in dimension_scores.items()
        },
        "detailed_results": test_results,
        "recommendations": recommendations,
        "benchmark_comparison": {
            "anti_interference_target": "≥ 90% recall, ≥ 87% F1",
            "contradiction_update_target": "≥ 95% latest accuracy, ≥ 90% history",
            "efficiency_target": "P50 ≤ 200ms write, ≤ 300ms query",
            "direction_c_target": "≥ 90% preference recall",
            "direction_d_target": "≥ 80% gap detection rate",
        },
    }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise Memory Engine Evaluation Runner"
    )
    parser.add_argument(
        "--output", "-o",
        default="eval_results.json",
        help="Output JSON report path",
    )
    parser.add_argument(
        "--report", "-r",
        default=None,
        help="Output Markdown report path (auto-generated if not specified)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Enterprise Memory Engine — Evaluation Suite")
    print("=" * 70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Output: {args.output}")
    print()

    start_time = time.time()

    # ---- Phase 1: Run all tests ----
    print("-" * 70)
    print("Phase 1: Running test suites")
    print("-" * 70)

    test_results = run_pytest_tests(args.output, verbose=args.verbose)

    elapsed = time.time() - start_time

    # ---- Phase 2: Generate report ----
    print("\n" + "-" * 70)
    print("Phase 2: Generating evaluation report")
    print("-" * 70)

    report = generate_report(test_results, elapsed)

    # ---- Phase 3: Save JSON report ----
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nJSON report saved to: {args.output}")

    # ---- Phase 4: Generate Markdown report ----
    report_path = args.report or args.output.replace(".json", "_report.md")
    try:
        # eval_report_generator is in eval/ directory
        eval_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval")
        sys.path.insert(0, eval_dir)
        from eval_report_generator import generate_markdown_report
        markdown = generate_markdown_report(report)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"Markdown report saved to: {report_path}")
    except ImportError:
        print("Warning: eval_report_generator.py not found, skipping Markdown report")
    except Exception as e:
        print(f"Warning: Failed to generate Markdown report: {e}")

    # ---- Print summary ----
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Total tests:  {report['summary']['total_tests']}")
    print(f"  Passed:       {report['summary']['passed']}")
    print(f"  Failed:       {report['summary']['failed']}")
    print(f"  Pass rate:    {report['summary']['pass_rate']:.1f}%")
    print()
    print("  Dimension Scores:")
    for dim, info in report["dimension_scores"].items():
        print(f"    {dim:25s}: {info['score']:6.1f}/100 (weight: {info['weight']:.0%})")
    print()
    print(f"  OVERALL SCORE: {report['summary']['overall_score']:.1f}/100  "
          f"[{report['summary']['grade']}]")
    print()
    if report["recommendations"]:
        print("  Recommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"    {i}. {rec}")
    print()
    print(f"  Elapsed time: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
