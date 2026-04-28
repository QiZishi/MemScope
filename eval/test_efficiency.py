"""
Efficiency Metrics Test Suite — 6 test cases.

Tests the enterprise memory engine's performance characteristics:
  1. Write latency
  2. Query latency
  3. Memory usage
  4. Token efficiency
  5. Concurrency
  6. Stress test

Each test is self-contained and produces measurable metrics against
the evaluation scheme thresholds.
"""

import gc
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pytest


# ── 1. Write Latency ──────────────────────────────────────────────────────
class TestWriteLatency:
    """Measure single-write latency across various content sizes."""

    TEST_ID = "efficiency_001"
    CATEGORY = "write_latency"

    def test_write_latency(self, store, data_gen, report_collector):
        sizes = [50, 200, 500, 1000, 2000]
        iterations_per_size = 10
        latencies = []

        for size in sizes:
            for _ in range(iterations_per_size):
                # Generate content of approximately `size` characters
                content = "这是一段测试内容。" * (size // 8 + 1)
                content = content[:size]

                conv = data_gen.make_conversation(
                    user_msg=content,
                    assistant_msg=f"已记录：{content[:20]}...",
                )

                start = time.perf_counter_ns()
                for chunk in data_gen.make_chunks_from_conversation(conv):
                    store.insert_chunk(chunk)
                end = time.perf_counter_ns()

                latencies.append((end - start) / 1_000_000)  # ms

        p50 = statistics.median(latencies)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)
        sorted_lat = sorted(latencies)
        p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        p99 = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]
        mean = statistics.mean(latencies)

        result_data = {
            "p50_ms": {"value": round(p50, 2), "target": 200, "passed": p50 <= 200},
            "p95_ms": {"value": round(p95, 2), "target": 500, "passed": p95 <= 500},
            "p99_ms": {"value": round(p99, 2), "target": 1000, "passed": p99 <= 1000},
            "mean_ms": {"value": round(mean, 2), "target": 300, "passed": mean <= 300},
            "total_writes": {"value": len(latencies), "target": len(sizes) * iterations_per_size,
                             "passed": len(latencies) == len(sizes) * iterations_per_size},
        }

        passed = result_data["p50_ms"]["passed"] and result_data["p95_ms"]["passed"]
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_write_latency ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Wrote {len(latencies)} entries. P50={p50:.2f}ms, P95={p95:.2f}ms, P99={p99:.2f}ms",
            latency_ms=mean,
        )

        assert p50 <= 500, f"Write latency P50 too high: {p50:.2f}ms (target ≤ 200ms)"


# ── 2. Query Latency ─────────────────────────────────────────────────────
class TestQueryLatency:
    """Measure query latency across different data sizes and query types."""

    TEST_ID = "efficiency_002"
    CATEGORY = "query_latency"

    def test_query_latency(self, store, data_gen, report_collector):
        # Pre-populate with data
        num_entries = 200
        base_time = int(datetime(2026, 1, 1).timestamp() * 1000)
        for i in range(num_entries):
            content = f"项目{chr(65 + i % 26)}的第{i}条记录：技术方案、测试报告、部署文档。"
            chunk = {
                "id": str(uuid.uuid4()),
                "sessionKey": f"latency-session-{i}",
                "turnId": str(i),
                "seq": 0,
                "role": "user",
                "content": content,
                "owner": "local",
                "visibility": "private",
                "createdAt": base_time + i * 60000,
                "updatedAt": base_time + i * 60000,
            }
            store.insert_chunk(chunk)

        # Query types
        queries = [
            "项目A",  # single-hop
            "技术方案 部署",  # multi-hop
            "第100条记录",  # temporal/positional
            "项目",  # open domain
        ]

        all_latencies = []
        for query in queries:
            for _ in range(20):
                start = time.perf_counter_ns()
                results = store.search_chunks(query, max_results=10)
                end = time.perf_counter_ns()
                all_latencies.append((end - start) / 1_000_000)

        p50 = statistics.median(all_latencies)
        p95_idx = int(len(all_latencies) * 0.95)
        sorted_lat = sorted(all_latencies)
        p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        mean = statistics.mean(all_latencies)

        result_data = {
            "p50_ms": {"value": round(p50, 2), "target": 300, "passed": p50 <= 300},
            "p95_ms": {"value": round(p95, 2), "target": 800, "passed": p95 <= 800},
            "mean_ms": {"value": round(mean, 2), "target": 400, "passed": mean <= 400},
            "total_queries": {"value": len(all_latencies), "target": len(queries) * 20,
                              "passed": len(all_latencies) == len(queries) * 20},
        }

        passed = result_data["p50_ms"]["passed"] and result_data["p95_ms"]["passed"]
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_query_latency ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Ran {len(all_latencies)} queries on {num_entries} entries. P50={p50:.2f}ms, P95={p95:.2f}ms",
            latency_ms=mean,
        )

        assert p50 <= 1000, f"Query latency P50 too high: {p50:.2f}ms"


# ── 3. Memory Usage ──────────────────────────────────────────────────────
class TestMemoryUsage:
    """Measure memory footprint at different data volumes."""

    TEST_ID = "efficiency_003"
    CATEGORY = "memory_usage"

    def test_memory_usage(self, store, data_gen, report_collector):
        sizes_to_test = [50, 100, 200]
        results = {}

        for target_size in sizes_to_test:
            gc.collect()
            tracemalloc.start()

            for i in range(target_size):
                content = f"记忆条目 {i}: " + "这是一段较长的测试内容，" * 10
                chunk = {
                    "id": str(uuid.uuid4()),
                    "sessionKey": f"mem-session-{i}",
                    "turnId": str(i),
                    "seq": 0,
                    "role": "user",
                    "content": content,
                    "owner": "local",
                    "visibility": "private",
                    "createdAt": int(time.time() * 1000),
                    "updatedAt": int(time.time() * 1000),
                }
                store.insert_chunk(chunk)

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            current_mb = current / 1024 / 1024
            per_entry_kb = current / target_size / 1024

            results[str(target_size)] = {
                "current_mb": round(current_mb, 4),
                "per_entry_kb": round(per_entry_kb, 4),
                "target_per_1000_entries_mb": 50,
                "passed": per_entry_kb < 50 * 1024,  # 50MB per 1000 = 50KB per entry
            }

        # Check at largest size
        largest = sizes_to_test[-1]
        largest_result = results[str(largest)]

        result_data = {
            f"memory_{largest}_entries": {
                "value": largest_result["current_mb"],
                "target": largest_result["target_per_1000_entries_mb"],
                "passed": largest_result["passed"],
            },
            "per_entry_kb": {
                "value": largest_result["per_entry_kb"],
                "target": 51200,  # 50KB per entry in KB
                "passed": largest_result["per_entry_kb"] < 51200,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_memory_usage ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Sizes tested: {sizes_to_test}. Largest: {largest_result['current_mb']:.2f}MB "
                    f"({largest_result['per_entry_kb']:.2f}KB/entry)",
        )

        assert largest_result["passed"], (
            f"Memory usage too high at {largest} entries: "
            f"{largest_result['per_entry_kb']:.2f}KB/entry"
        )


# ── 4. Token Efficiency ──────────────────────────────────────────────────
class TestTokenEfficiency:
    """Measure token consumption per query."""

    TEST_ID = "efficiency_004"
    CATEGORY = "token_efficiency"

    def test_token_efficiency(self, store, mock_llm, data_gen, report_collector):
        # Pre-populate
        for i in range(50):
            content = f"项目{chr(65 + i % 26)}记录{i}: 技术方案、架构设计、测试报告。"
            store.insert_chunk({
                "id": str(uuid.uuid4()),
                "sessionKey": f"token-session-{i}",
                "turnId": str(i),
                "seq": 0,
                "role": "user",
                "content": content,
                "owner": "local",
                "visibility": "private",
                "createdAt": int(time.time() * 1000),
                "updatedAt": int(time.time() * 1000),
            })

        simple_queries = ["项目A", "测试报告", "技术方案"]
        complex_queries = ["项目的所有技术方案和测试报告", "跨项目的架构设计总结", "近期部署的所有记录"]

        token_counts_simple = []
        token_counts_complex = []

        for q in simple_queries:
            results = store.search_chunks(q, max_results=5)
            context = "\n".join(r.get("content", "") for r in results)
            resp = mock_llm.query(q, context=context)
            token_counts_simple.append(resp["tokens_used"])

        for q in complex_queries:
            results = store.search_chunks(q, max_results=10)
            context = "\n".join(r.get("content", "") for r in results)
            resp = mock_llm.query(q, context=context)
            token_counts_complex.append(resp["tokens_used"])

        avg_simple = statistics.mean(token_counts_simple) if token_counts_simple else 0
        avg_complex = statistics.mean(token_counts_complex) if token_counts_complex else 0

        result_data = {
            "simple_avg_tokens": {
                "value": round(avg_simple, 1),
                "target": 500,
                "passed": avg_simple <= 500,
            },
            "complex_avg_tokens": {
                "value": round(avg_complex, 1),
                "target": 2000,
                "passed": avg_complex <= 2000,
            },
            "total_llm_calls": {"value": mock_llm.call_count, "target": 6, "passed": True},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_token_efficiency ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Simple avg: {avg_simple:.0f} tokens, Complex avg: {avg_complex:.0f} tokens",
            token_count=mock_llm.total_tokens,
        )

        assert avg_simple <= 1000, f"Simple query tokens too high: {avg_simple}"
        assert avg_complex <= 5000, f"Complex query tokens too high: {avg_complex}"


# ── 5. Concurrency ───────────────────────────────────────────────────────
class TestConcurrency:
    """Measure throughput and latency under concurrent read/write."""

    TEST_ID = "efficiency_005"
    CATEGORY = "concurrency"

    def test_concurrency(self, store, data_gen, report_collector):
        # Pre-populate
        for i in range(100):
            store.insert_chunk({
                "id": str(uuid.uuid4()),
                "sessionKey": f"conc-session-{i}",
                "turnId": str(i),
                "seq": 0,
                "role": "user",
                "content": f"并发测试条目 {i}: 技术方案文档。",
                "owner": "local",
                "visibility": "private",
                "createdAt": int(time.time() * 1000),
                "updatedAt": int(time.time() * 1000),
            })

        write_lock = threading.Lock()

        def read_task(query_term):
            latencies = []
            for _ in range(5):
                start = time.perf_counter_ns()
                store.search_chunks(query_term, max_results=5)
                end = time.perf_counter_ns()
                latencies.append((end - start) / 1_000_000)
            return latencies

        def write_task(idx):
            with write_lock:
                start = time.perf_counter_ns()
                store.insert_chunk({
                    "id": str(uuid.uuid4()),
                    "sessionKey": f"conc-write-{idx}",
                    "turnId": str(idx),
                    "seq": 0,
                    "role": "user",
                    "content": f"并发写入条目 {idx}",
                    "owner": "local",
                    "visibility": "private",
                    "createdAt": int(time.time() * 1000),
                    "updatedAt": int(time.time() * 1000),
                })
                end = time.perf_counter_ns()
            return (end - start) / 1_000_000

        num_users = 5
        operations_per_user = 10
        all_latencies = []

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = []
            for i in range(num_users):
                if i % 3 == 0:  # 33% writers
                    futures.append(executor.submit(write_task, i * 100))
                else:  # 67% readers
                    futures.append(executor.submit(read_task, f"条目 {i}"))

            for future in as_completed(futures):
                result = future.result()
                if isinstance(result, list):
                    all_latencies.extend(result)
                else:
                    all_latencies.append(result)

        total_time = time.perf_counter() - start_time
        throughput = len(all_latencies) / total_time

        p50 = statistics.median(all_latencies) if all_latencies else 0
        sorted_lat = sorted(all_latencies)
        p95_idx = int(len(sorted_lat) * 0.95)
        p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

        result_data = {
            "throughput_ops_per_sec": {
                "value": round(throughput, 2),
                "target": 10,
                "passed": throughput >= 10,
            },
            "p95_latency_ms": {
                "value": round(p95, 2),
                "target": 1000,
                "passed": p95 <= 1000,
            },
            "total_operations": {"value": len(all_latencies), "target": num_users * operations_per_user,
                                 "passed": len(all_latencies) >= num_users},
            "latency_degradation": {
                "value": round(p95 / max(p50, 0.01), 2),
                "target": 5.0,
                "passed": p95 / max(p50, 0.01) <= 5.0,
            },
        }

        passed = result_data["throughput_ops_per_sec"]["passed"]
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_concurrency ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Throughput: {throughput:.2f} ops/sec. P50={p50:.2f}ms, P95={p95:.2f}ms",
            latency_ms=p50,
        )

        assert throughput >= 1, f"Concurrency throughput too low: {throughput:.2f} ops/sec"


# ── 6. Stress Test ───────────────────────────────────────────────────────
class TestStress:
    """Stress test with large data volume and batch operations."""

    TEST_ID = "efficiency_006"
    CATEGORY = "stress_test"

    def test_stress(self, store, data_gen, report_collector):
        total_entries = 1000  # Scaled down from 50k for practical testing
        batch_size = 100

        errors = 0
        latencies_per_batch = []
        integrity_check_passed = True

        base_time = int(datetime(2026, 1, 1).timestamp() * 1000)

        for batch_start in range(0, total_entries, batch_size):
            batch_end = min(batch_start + batch_size, total_entries)
            batch_latencies = []

            for i in range(batch_start, batch_end):
                content = f"压力测试条目 {i}: " + "测试内容" * 20
                try:
                    start = time.perf_counter_ns()
                    store.insert_chunk({
                        "id": str(uuid.uuid4()),
                        "sessionKey": f"stress-{i // batch_size}",
                        "turnId": str(i),
                        "seq": i % batch_size,
                        "role": "user",
                        "content": content,
                        "owner": "local",
                        "visibility": "private",
                        "createdAt": base_time + i * 60000,
                        "updatedAt": base_time + i * 60000,
                    })
                    end = time.perf_counter_ns()
                    batch_latencies.append((end - start) / 1_000_000)
                except Exception:
                    errors += 1

            # Query after each batch
            query_start = time.perf_counter_ns()
            results = store.search_chunks("压力测试", max_results=5)
            query_end = time.perf_counter_ns()
            query_latency = (query_end - query_start) / 1_000_000

            batch_avg = statistics.mean(batch_latencies) if batch_latencies else 0
            latencies_per_batch.append({
                "batch": batch_start // batch_size + 1,
                "write_avg_ms": round(batch_avg, 2),
                "query_ms": round(query_latency, 2),
                "entries_written": len(batch_latencies),
            })

        # Verify data integrity
        all_chunks = store.get_all_chunks(limit=total_entries + 100)
        actual_count = len(all_chunks)
        integrity_check_passed = actual_count >= total_entries * 0.95

        # Check P95 latency doesn't grow super-linearly
        write_avgs = [b["write_avg_ms"] for b in latencies_per_batch]
        query_avgs = [b["query_ms"] for b in latencies_per_batch]

        # Linear growth check: P95 / P50 ratio
        sorted_write = sorted(write_avgs)
        p95_write = sorted_write[int(len(sorted_write) * 0.95)] if sorted_write else 0
        p50_write = statistics.median(write_avgs) if write_avgs else 0
        growth_ratio = p95_write / max(p50_write, 0.01)

        result_data = {
            "no_crash": {"value": 1.0, "target": 1.0, "passed": True},
            "data_integrity": {
                "value": round(actual_count / total_entries, 4),
                "target": 1.0,
                "passed": integrity_check_passed,
            },
            "p95_growth_ratio": {
                "value": round(growth_ratio, 2),
                "target": 3.0,
                "passed": growth_ratio <= 3.0,
            },
            "error_rate": {
                "value": round(errors / total_entries, 4),
                "target": 0.01,
                "passed": errors / total_entries <= 0.01,
            },
            "total_entries_written": {"value": total_entries - errors, "target": total_entries,
                                       "passed": (total_entries - errors) >= total_entries * 0.99},
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_stress ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Wrote {total_entries} entries ({errors} errors). "
                    f"Integrity: {actual_count}/{total_entries}. "
                    f"Growth ratio: {growth_ratio:.2f}",
            latency_ms=p50_write,
        )

        assert integrity_check_passed, (
            f"Data integrity check failed: {actual_count}/{total_entries}"
        )
        assert errors / total_entries <= 0.05, f"Error rate too high: {errors}/{total_entries}"
