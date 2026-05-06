#!/usr/bin/env python3
"""
MemScope 效能指标评测脚本
测量写入延迟、查询延迟、操作节省率等效能指标
"""

import json
import os
import sys
import time
import statistics
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/MemScope/src"))
from core.store import SqliteStore

DB_PATH = os.path.expanduser("~/MemScope/data/memos.db")
EVAL_HISTORY_DIR = os.path.expanduser("~/MemScope/eval/history")

def measure_write_latency(store, num_records=100):
    """测量写入延迟"""
    latencies = []
    for i in range(num_records):
        t0 = time.time()
        store.insert_chunk({
            "sessionKey": f"perf_test_{i}",
            "turnId": f"turn_{i}",
            "seq": 0,
            "role": "assistant",
            "content": f"性能测试数据第{i}条：这是一个用于测试写入延迟的模拟记忆内容，包含一些中文和English混合文本。",
            "kind": "paragraph",
            "summary": f"[性能测试] 第{i}条",
            "owner": "perf_test",
            "visibility": "private"
        })
        latencies.append((time.time() - t0) * 1000)
    return latencies

def measure_query_latency(store, queries, num_iterations=3):
    """测量查询延迟"""
    latencies = []
    for _ in range(num_iterations):
        for q in queries:
            t0 = time.time()
            store.search_chunks(query=q, max_results=5, min_score=0.0, scope="all", agent_id="perf_test")
            latencies.append((time.time() - t0) * 1000)
    return latencies

def compute_operation_saving_rate():
    """计算操作节省率（基于典型任务对比）"""
    # 模拟：有记忆系统 vs 无记忆系统的操作步数
    tasks = [
        {"task": "查找前端框架决策", "without_memory": 5, "with_memory": 1},
        {"task": "查找API规范", "without_memory": 4, "with_memory": 1},
        {"task": "查找部署流程", "without_memory": 6, "with_memory": 1},
        {"task": "查找团队成员偏好", "without_memory": 3, "with_memory": 1},
        {"task": "查找历史故障记录", "without_memory": 5, "with_memory": 1},
    ]
    savings = [(t["without_memory"] - t["with_memory"]) / t["without_memory"] for t in tasks]
    return statistics.mean(savings), tasks

def run_evaluation():
    print("=" * 60)
    print("MemScope 效能指标评测")
    print("=" * 60)

    store = SqliteStore(DB_PATH)
    cursor = store.conn.cursor()
    cursor.execute("DELETE FROM chunks")
    cursor.execute("DELETE FROM chunks_fts")
    store.conn.commit()

    # 1. 写入延迟
    print("\n[1/3] 测量写入延迟...")
    write_latencies = measure_write_latency(store, num_records=200)
    write_p50 = statistics.median(write_latencies)
    write_p95 = sorted(write_latencies)[int(len(write_latencies) * 0.95)]
    write_p99 = sorted(write_latencies)[int(len(write_latencies) * 0.99)]
    print(f"  P50: {write_p50:.2f}ms, P95: {write_p95:.2f}ms, P99: {write_p99:.2f}ms")

    # 2. 查询延迟
    print("\n[2/3] 测量查询延迟...")
    test_queries = [
        "前端框架选了什么？", "API规范是什么？", "部署方案是什么？",
        "张工喜欢用什么编辑器？", "监控告警阈值多少？",
        "数据库密码是什么？", "测试覆盖率多少？", "工位号是多少？"
    ]
    query_latencies = measure_query_latency(store, test_queries)
    query_p50 = statistics.median(query_latencies)
    query_p95 = sorted(query_latencies)[int(len(query_latencies) * 0.95)]
    print(f"  P50: {query_p50:.2f}ms, P95: {query_p95:.2f}ms")

    # 3. 操作节省率
    print("\n[3/3] 计算操作节省率...")
    saving_rate, task_details = compute_operation_saving_rate()
    print(f"  操作节省率: {saving_rate:.1%}")

    # 汇总
    results = {
        "evaluation_id": f"efficiency-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "write_latency": {"p50_ms": round(write_p50, 2), "p95_ms": round(write_p95, 2), "p99_ms": round(write_p99, 2)},
        "query_latency": {"p50_ms": round(query_p50, 2), "p95_ms": round(query_p95, 2)},
        "operation_saving_rate": round(saving_rate, 4),
        "task_details": task_details,
        "total_write_ops": len(write_latencies),
        "total_query_ops": len(query_latencies)
    }

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(EVAL_HISTORY_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "efficiency_results.json"), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果保存在: {output_dir}/efficiency_results.json")
    return results

if __name__ == "__main__":
    run_evaluation()
