#!/usr/bin/env python3
"""
Enterprise Memory Engine — Markdown Report Generator

Generates a comprehensive Markdown evaluation report from JSON results.
Produces a professional report with:
  - Executive summary
  - Score breakdown by dimension
  - Individual test results
  - Benchmark comparisons
  - Improvement recommendations

Usage:
    python eval_report_generator.py <eval_results.json> [output.md]
"""

import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, List


def _score_emoji(score: float) -> str:
    """Return an emoji indicator for a score."""
    if score >= 85:
        return "🟢"
    elif score >= 70:
        return "🟡"
    elif score >= 50:
        return "🟠"
    else:
        return "🔴"


def _status_emoji(status: str) -> str:
    """Return an emoji for test status."""
    mapping = {
        "pass": "✅",
        "fail": "❌",
        "error": "⚠️",
        "skip": "⏭️",
    }
    return mapping.get(status, "❓")


def _bar_chart(score: float, width: int = 20) -> str:
    """Generate a simple ASCII bar chart."""
    filled = int(score / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score:.1f}%"


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Generate a comprehensive Markdown report from the JSON results."""

    lines = []
    w = lines.append  # shorthand

    summary = report.get("summary", {})
    dim_scores = report.get("dimension_scores", {})
    detailed = report.get("detailed_results", [])
    recs = report.get("recommendations", [])
    benchmarks = report.get("benchmark_comparison", {})

    # ── Header ──
    w(f"# 企业记忆引擎 — 评估报告")
    w(f"")
    w(f"> **报告ID**: `{report.get('report_id', 'N/A')}`  ")
    w(f"> **生成时间**: {report.get('run_timestamp', 'N/A')}  ")
    w(f"> **系统版本**: {report.get('system_version', 'N/A')}  ")
    w(f"> **总耗时**: {report.get('elapsed_seconds', 0):.1f} 秒")
    w(f"")

    # ── Executive Summary ──
    w(f"## 1. 执行摘要")
    w(f"")
    w(f"| 指标 | 值 |")
    w(f"|------|-----|")
    w(f"| 测试总数 | {summary.get('total_tests', 0)} |")
    w(f"| 通过 | ✅ {summary.get('passed', 0)} |")
    w(f"| 失败 | ❌ {summary.get('failed', 0)} |")
    w(f"| 错误 | ⚠️ {summary.get('errors', 0)} |")
    w(f"| 跳过 | ⏭️ {summary.get('skipped', 0)} |")
    w(f"| 通过率 | {summary.get('pass_rate', 0):.1f}% |")
    w(f"| **综合得分** | **{summary.get('overall_score', 0):.1f} / 100** |")
    w(f"| **评级** | **{summary.get('grade', 'N/A')}** |")
    w(f"")

    # Overall score bar
    overall = summary.get("overall_score", 0)
    w(f"### 综合得分")
    w(f"")
    w(f"```")
    w(f"Overall: {_bar_chart(overall, 40)}")
    w(f"```")
    w(f"")

    # Pass threshold
    if overall >= 85:
        w(f"> 🏆 **优秀！** 超过优秀线（85分）")
    elif overall >= 70:
        w(f"> ✅ **及格。** 达到竞赛及格线（70分），继续提升以争取更高分数。")
    else:
        w(f"> ⚠️ **未达及格线。** 当前 {overall:.1f} 分，需达到 70 分才能通过竞赛。")
    w(f"")

    # ── Dimension Scores ──
    w(f"## 2. 各维度得分")
    w(f"")
    w(f"| 维度 | 得分 | 权重 | 加权得分 | 测试数 | 通过数 | 状态 |")
    w(f"|------|------|------|----------|--------|--------|------|")

    for dim, info in dim_scores.items():
        score = info.get("score", 0)
        weight = info.get("weight", 0)
        weighted = info.get("weighted_score", 0)
        test_count = info.get("test_count", 0)
        passed_count = info.get("passed_count", 0)
        emoji = _score_emoji(score)

        dim_names = {
            "anti_interference": "抗干扰能力",
            "contradiction_update": "矛盾更新",
            "efficiency": "效率指标",
            "direction_c": "方向C-个人偏好",
            "direction_d": "方向D-团队知识",
        }
        dim_display = dim_names.get(dim, dim)

        w(f"| {emoji} {dim_display} | {score:.1f}/100 | {weight:.0%} | {weighted:.1f} | {test_count} | {passed_count}/{test_count} | "
          f"{'PASS' if score >= 70 else 'FAIL'} |")

    w(f"| **总计** | | **100%** | **{overall:.1f}** | | | |")
    w(f"")

    # Score visualization
    w(f"### 得分可视化")
    w(f"")
    w(f"```")
    for dim, info in dim_scores.items():
        score = info.get("score", 0)
        dim_names = {
            "anti_interference": "Anti-interference",
            "contradiction_update": "Contradiction     ",
            "efficiency": "Efficiency         ",
            "direction_c": "Direction C        ",
            "direction_d": "Direction D        ",
        }
        label = dim_names.get(dim, dim)
        w(f"  {label}: {_bar_chart(score)}")
    w(f"  {'':18s} ─────────────────────────────")
    w(f"  {'Overall':18s}: {_bar_chart(overall)}")
    w(f"```")
    w(f"")

    # ── Individual Test Results ──
    w(f"## 3. 详细测试结果")
    w(f"")

    # Group by dimension
    dim_order = ["anti_interference", "contradiction_update", "efficiency", "direction_c", "direction_d"]
    dim_names_cn = {
        "anti_interference": "抗干扰能力测试",
        "contradiction_update": "矛盾更新测试",
        "efficiency": "效率指标测试",
        "direction_c": "方向C - 个人偏好测试",
        "direction_d": "方向D - 团队知识测试",
    }

    for dim in dim_order:
        dim_tests = [t for t in detailed if t.get("test_id", "").startswith(
            dim.replace("_update", "").replace("_interference", "")[:10]
        )]
        # More precise grouping
        dim_tests = []
        test_dim_map = {
            "anti_interference_": "anti_interference",
            "contradiction_": "contradiction_update",
            "efficiency_": "efficiency",
            "direction_c_": "direction_c",
            "direction_d_": "direction_d",
        }
        for t in detailed:
            tid = t.get("test_id", "")
            for prefix, d in test_dim_map.items():
                if tid.startswith(prefix):
                    if d == dim:
                        dim_tests.append(t)
                    break

        if not dim_tests:
            continue

        dim_score = dim_scores.get(dim, {}).get("score", 0)
        w(f"### 3.{dim_order.index(dim)+1} {dim_names_cn.get(dim, dim)} ({dim_score:.1f}/100)")
        w(f"")
        w(f"| 测试ID | 测试名称 | 状态 | 延迟(ms) | Token数 |")
        w(f"|--------|----------|------|----------|---------|")

        for test in dim_tests:
            status = test.get("status", "unknown")
            emoji = _status_emoji(status)
            test_id = test.get("test_id", "")
            test_name = test.get("test_name", "")
            latency = test.get("latency_ms", 0)
            tokens = test.get("token_count", 0)

            w(f"| {test_id} | {test_name[:40]} | {emoji} {status} | {latency:.1f} | {tokens} |")

        w(f"")

        # Detailed metrics for each test
        for test in dim_tests:
            status = test.get("status", "unknown")
            emoji = _status_emoji(status)
            test_id = test.get("test_id", "")
            w(f"**{emoji} {test_id}** — {test.get('test_name', '')}")
            w(f"")

            metrics = test.get("metrics", {})
            if metrics:
                w(f"| 指标 | 值 | 目标 | 通过 |")
                w(f"|------|-----|------|------|")
                for metric_name, metric_info in metrics.items():
                    if isinstance(metric_info, dict):
                        val = metric_info.get("value", "N/A")
                        target = metric_info.get("target", "N/A")
                        passed = "✅" if metric_info.get("passed", False) else "❌"

                        if isinstance(val, float):
                            val_str = f"{val:.4f}" if val < 1 else f"{val:.2f}"
                        else:
                            val_str = str(val)

                        if isinstance(target, float):
                            target_str = f"{target:.4f}" if target < 1 else f"{target:.2f}"
                        else:
                            target_str = str(target)

                        w(f"| {metric_name} | {val_str} | {target_str} | {passed} |")
                w(f"")

            details = test.get("details", "")
            if details:
                w(f"> {details}")
                w(f"")

            error = test.get("error_message", "")
            if error:
                w(f"> ⚠️ Error: {error}")
                w(f"")

        w(f"---")
        w(f"")

    # ── Benchmark Comparison ──
    w(f"## 4. 基准对标")
    w(f"")
    w(f"| 维度 | 目标 | 实际 | 状态 |")
    w(f"|------|------|------|------|")

    benchmark_map = {
        "anti_interference": ("≥ 90% recall, ≥ 87% F1",
                             dim_scores.get("anti_interference", {}).get("score", 0)),
        "contradiction_update": ("≥ 95% latest accuracy, ≥ 90% history",
                                dim_scores.get("contradiction_update", {}).get("score", 0)),
        "efficiency": ("P50 ≤ 200ms write, ≤ 300ms query",
                      dim_scores.get("efficiency", {}).get("score", 0)),
        "direction_c": ("≥ 90% preference recall",
                       dim_scores.get("direction_c", {}).get("score", 0)),
        "direction_d": ("≥ 80% gap detection rate",
                       dim_scores.get("direction_d", {}).get("score", 0)),
    }

    for dim, (target, score) in benchmark_map.items():
        dim_cn = {
            "anti_interference": "抗干扰能力",
            "contradiction_update": "矛盾更新",
            "efficiency": "效率指标",
            "direction_c": "方向C",
            "direction_d": "方向D",
        }.get(dim, dim)
        status = "✅ PASS" if score >= 70 else "❌ FAIL"
        w(f"| {dim_cn} | {target} | {score:.1f}/100 | {status} |")

    w(f"")

    # ── Recommendations ──
    w(f"## 5. 改进建议")
    w(f"")

    if recs:
        for i, rec in enumerate(recs, 1):
            w(f"{i}. {rec}")
            w(f"")
    else:
        w(f"> 暂无改进建议 — 系统表现良好！")
        w(f"")

    # ── Technical Details ──
    w(f"## 6. 技术细节")
    w(f"")
    w(f"### 评估配置")
    w(f"")
    w(f"| 参数 | 值 |")
    w(f"|------|-----|")
    w(f"| 维度权重 | 抗干扰: 25%, 矛盾更新: 25%, 效率: 20%, C: 15%, D: 15% |")
    w(f"| 及格线 | 70 分 |")
    w(f"| 优秀线 | 85 分 |")
    w(f"| 测试文件数 | 5 |")
    w(f"| 总测试用例数 | {summary.get('total_tests', 0)} |")
    w(f"")

    w(f"### 评分算法")
    w(f"")
    w(f"```")
    w(f"overall_score = Σ(dimension_score × dimension_weight)")
    w(f"dimension_score = Σ(test_score × test_weight)")
    w(f"test_score = (passed_metrics / total_metrics) × 100  [if failed]")
    w(f"test_score = 100  [if passed]")
    w(f"```")
    w(f"")

    # ── Footer ──
    w(f"---")
    w(f"")
    w(f"*报告由企业记忆引擎评估系统自动生成 — {report.get('run_timestamp', '')}*  ")
    w(f"*Enterprise Memory Engine Evaluation System v2.0*")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python eval_report_generator.py <eval_results.json> [output.md]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".json", "_report.md")

    with open(input_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    markdown = generate_markdown_report(report)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Markdown report generated: {output_path}")
    print(f"Report size: {len(markdown)} characters, {markdown.count(chr(10))} lines")


if __name__ == "__main__":
    main()
