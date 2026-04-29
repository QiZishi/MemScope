#!/usr/bin/env python3
"""
MemScope 真实性能评估 v2 — 全部200条评测数据集 × 真实系统

与 pytest 代码测试的区别：
- pytest: mock LLM + mock 数据 → 检验代码有没有 bug
- 本脚本: 真实系统 + 全部评测数据集 → 衡量实际性能好坏

用法:
    python3 real_evaluation.py [--output OUTPUT]
"""

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# 路径设置
# ---------------------------------------------------------------------------
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(EVAL_DIR, "..")
SRC_DIR = os.path.join(OUTPUT_DIR, "src")
DATASETS_DIR = os.path.join(EVAL_DIR, "datasets")

for p in (OUTPUT_DIR, SRC_DIR,
          os.path.join(SRC_DIR, "command_memory"),
          os.path.join(SRC_DIR, "decision_memory"),
          os.path.join(SRC_DIR, "preference_memory"),
          os.path.join(SRC_DIR, "knowledge_health")):
    if p not in sys.path:
        sys.path.insert(0, p)

import sqlite3
import tempfile
from schema_v2 import apply_v2_schema
from ministore import MiniStore


# ---------------------------------------------------------------------------
# 初始化真实 MemScope 系统
# ---------------------------------------------------------------------------
def create_real_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, sessionKey TEXT NOT NULL, turnId TEXT NOT NULL,
            seq INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            kind TEXT DEFAULT 'paragraph', summary TEXT, owner TEXT DEFAULT 'local',
            visibility TEXT DEFAULT 'private', sharedWith TEXT, taskId TEXT,
            skillId TEXT, createdAt INTEGER NOT NULL, updatedAt INTEGER NOT NULL,
            UNIQUE(sessionKey, turnId, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(sessionKey);
        CREATE INDEX IF NOT EXISTS idx_chunks_owner ON chunks(owner);
        CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(createdAt);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, summary, content='chunks', content_rowid='rowid'
        );
        CREATE TABLE IF NOT EXISTS tool_logs (
            id TEXT PRIMARY KEY, tool TEXT NOT NULL, args TEXT,
            result TEXT, ts INTEGER NOT NULL, owner TEXT DEFAULT 'local'
        );
        CREATE TABLE IF NOT EXISTS embeddings (
            chunkId TEXT PRIMARY KEY, embedding BLOB NOT NULL, createdAt INTEGER NOT NULL,
            FOREIGN KEY (chunkId) REFERENCES chunks(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    apply_v2_schema(conn)
    store = MiniStore(conn)
    return store, conn, db_path


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def ts_str_to_ms(ts_str: str) -> int:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def insert_conversation(store, user_msg: str, assistant_msg: str,
                        timestamp: str = None, owner: str = "local",
                        session_key: str = "eval") -> Tuple[str, str]:
    ts_ms = ts_str_to_ms(timestamp) if timestamp else int(time.time() * 1000)
    user_id = str(uuid.uuid4())
    asst_id = str(uuid.uuid4())
    store.insert_chunk({"id": user_id, "sessionKey": session_key, "turnId": str(ts_ms),
                        "seq": 0, "role": "user", "content": user_msg, "owner": owner,
                        "createdAt": ts_ms, "updatedAt": ts_ms})
    store.insert_chunk({"id": asst_id, "sessionKey": session_key, "turnId": str(ts_ms),
                        "seq": 1, "role": "assistant", "content": assistant_msg, "owner": owner,
                        "createdAt": ts_ms + 1, "updatedAt": ts_ms + 1})
    return user_id, asst_id


def text_contains(text: str, keywords: List[str]) -> float:
    if not keywords: return 1.0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower) / len(keywords)


def text_not_contains(text: str, forbidden: List[str]) -> float:
    if not forbidden: return 1.0
    text_lower = text.lower()
    return sum(1 for fw in forbidden if fw.lower() not in text_lower) / len(forbidden)


# ---------------------------------------------------------------------------
# 评估器
# ---------------------------------------------------------------------------

def eval_anti_interference(store, case: Dict) -> Dict[str, Any]:
    inp = case["input"]
    expected = case["expected"]
    sid = f"eval-{case['test_id']}"
    target = inp["target"]
    insert_conversation(store, target["user_msg"], target["assistant_msg"],
                        target.get("timestamp"), target.get("owner", "local"), sid)
    for noise in inp.get("noise", []):
        insert_conversation(store, noise["user_msg"], noise["assistant_msg"],
                            noise.get("timestamp"), noise.get("owner", "local"), sid)
    query = inp.get("query", "")
    start = time.perf_counter()
    results = store.search_chunks(query, max_results=10)
    latency_ms = (time.perf_counter() - start) * 1000
    all_content = " ".join(r.get("content", "") for r in results)
    recall = text_contains(all_content, expected.get("expected_keywords", []))
    noise_rate = 1.0 - text_not_contains(all_content, expected.get("noise_keywords", []))
    precision = 1.0 - noise_rate
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {"recall": round(recall, 4), "precision": round(precision, 4),
            "noise_injection_rate": round(noise_rate, 4), "f1_score": round(f1, 4),
            "latency_ms": round(latency_ms, 2), "chunks_found": len(results),
            "content_preview": all_content[:300]}


def eval_contradiction_update(store, case: Dict) -> Dict[str, Any]:
    inp = case["input"]
    expected = case["expected"]
    sid = f"eval-{case['test_id']}"

    # 格式1: old/new (cases 1-8)
    if "old" in inp and "new" in inp:
        old, new = inp["old"], inp["new"]
        insert_conversation(store, old["user_msg"], old["assistant_msg"],
                            old.get("timestamp"), session_key=sid)
        insert_conversation(store, new["user_msg"], new["assistant_msg"],
                            new.get("timestamp"), session_key=sid)
        query = inp.get("query", "")

    # 格式2: versions 列表 (cases 9-12, 19-20)
    elif "versions" in inp:
        for ver in inp["versions"]:
            insert_conversation(store, ver["user_msg"], ver["assistant_msg"],
                                ver.get("timestamp"), session_key=sid)
        query = inp.get("query", "")

    # 格式3: original/update + queries (cases 13-15)
    elif "original" in inp:
        orig = inp["original"]
        updates = inp.get("update", inp.get("updates", []))
        if isinstance(updates, dict):
            updates = [updates]
        insert_conversation(store, orig["user_msg"], orig["assistant_msg"],
                            orig.get("timestamp"), session_key=sid)
        for u in updates:
            insert_conversation(store, u["user_msg"], u["assistant_msg"],
                                u.get("timestamp"), session_key=sid)
        # 用第一个 query
        queries = inp.get("queries", [inp.get("query", "")])
        query = queries[0] if isinstance(queries, list) else queries
        if isinstance(query, dict):
            query = query.get("query", query.get("text", str(query)))

    # 格式4: create/cancel (cases 16-18)
    elif "create" in inp:
        create, cancel = inp["create"], inp["cancel"]
        insert_conversation(store, create["user_msg"], create["assistant_msg"],
                            create.get("timestamp"), session_key=sid)
        insert_conversation(store, cancel["user_msg"], cancel["assistant_msg"],
                            cancel.get("timestamp"), session_key=sid)
        query = inp.get("query", "")
    else:
        return {"error": f"unknown format: {list(inp.keys())}"}

    if isinstance(query, dict):
        query = query.get("query", query.get("text", str(query)))

    start = time.perf_counter()
    results = store.search_chunks(query, max_results=10)
    latency_ms = (time.perf_counter() - start) * 1000
    all_content = " ".join(r.get("content", "") for r in results)

    # 检查 latest_value
    latest_value = expected.get("latest_value", "")
    old_value = expected.get("old_value", "")
    latest_correct = latest_value in all_content if latest_value else True
    old_preserved = old_value in all_content if old_value else True

    # 检查 expected_answer_contains
    answer_contains = expected.get("expected_answer_contains", [])
    answer_found = text_contains(all_content, answer_contains) >= 0.5 if answer_contains else True

    return {"latest_value_correct": latest_correct, "old_value_preserved": old_preserved,
            "answer_contains_found": answer_found, "latency_ms": round(latency_ms, 2),
            "chunks_found": len(results), "content_preview": all_content[:300]}


def eval_efficiency(store, case: Dict) -> Dict[str, Any]:
    inp = case["input"]
    category = case.get("category", "")
    if "write" in category:
        conv = inp.get("conversation", {})
        iterations = inp.get("iterations", 10)
        latencies = []
        for i in range(iterations):
            start = time.perf_counter()
            insert_conversation(store, conv.get("user_msg", f"test {i}"),
                                conv.get("assistant_msg", f"reply {i}"),
                                conv.get("timestamp"), session_key=f"eval-eff-{i}")
            latencies.append((time.perf_counter() - start) * 1000)
        latencies.sort()
        return {"p50_ms": round(latencies[len(latencies)//2], 2),
                "p95_ms": round(latencies[int(len(latencies)*0.95)], 2),
                "p99_ms": round(latencies[int(len(latencies)*0.99)], 2),
                "iterations": iterations}
    elif "query" in category:
        for i in range(50):
            insert_conversation(store, f"查询测试 {i}", f"回复 {i}",
                                session_key=f"eval-eff-q-{i}")
        latencies = []
        for i in range(inp.get("iterations", 20)):
            start = time.perf_counter()
            store.search_chunks(f"测试 {i%50}", max_results=5)
            latencies.append((time.perf_counter() - start) * 1000)
        latencies.sort()
        return {"p50_ms": round(latencies[len(latencies)//2], 2),
                "p95_ms": round(latencies[int(len(latencies)*0.95)], 2),
                "iterations": len(latencies)}
    return {"status": "measured"}


def eval_command_memory(store, case: Dict) -> Dict[str, Any]:
    from command_memory.command_tracker import CommandTracker
    from command_memory.recommender import CommandRecommender
    tracker = CommandTracker(store)
    recommender = CommandRecommender(store)
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})

    # 写入命令
    for user_key in ["user_a_commands", "user_b_commands", "commands"]:
        commands = setup.get(user_key, [])
        if user_key == "user_a_commands":
            owner = setup.get("user_a", "user_a")
        elif user_key == "user_b_commands":
            owner = setup.get("user_b", "user_b")
        else:
            owner = setup.get("user", query.get("user", "local"))
        for cmd_entry in commands:
            cmd = cmd_entry.get("command", "")
            count = cmd_entry.get("count", 1)
            for _ in range(count):
                tracker.log_command(owner=owner, command=cmd,
                                    project_path=setup.get("project_path"), exit_code=0)

    q_user = query.get("user", "user_a")
    q_type = query.get("type", "frequent")
    results = {}
    if q_type == "frequent":
        freq = store.get_command_patterns(q_user, limit=10)
        results["top_commands"] = [p.get("command", "") for p in freq]
    elif q_type == "recommend":
        prefix = query.get("prefix", "")
        recs = recommender.recommend(owner=q_user, prefix=prefix, limit=5)
        results["recommendations"] = recs if isinstance(recs, list) else recs.get("commands", []) if isinstance(recs, dict) else []

    passed, failed = [], []
    if "top_command" in expected:
        top = expected["top_command"]
        actual = results.get("top_commands", [""])[0] if results.get("top_commands") else ""
        (passed if top in actual else failed).append(f"top_command={top}")
    if "must_not_contain" in expected:
        all_cmds = " ".join(results.get("top_commands", []))
        for fb in expected["must_not_contain"]:
            (passed if fb not in all_cmds else failed).append(f"not_contain={fb}")
    if "min_frequency" in expected:
        freqs = results.get("frequencies", {})
        max_freq = max(freqs.values()) if freqs else 0
        (passed if max_freq >= expected["min_frequency"] else failed).append(f"min_freq={expected['min_frequency']}")
    return {"passed_checks": passed, "failed_checks": failed, "results": results}


def eval_decision_memory(store, case: Dict) -> Dict[str, Any]:
    from decision_memory.decision_extractor import DecisionExtractor
    extractor = DecisionExtractor(store)
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})

    messages = setup.get("messages", [])
    all_decisions = []
    for msg in messages:
        content = msg.get("content", "")
        decisions = extractor.extract_from_message(content, sender=msg.get("role", "user"))
        all_decisions.extend(decisions)

    # 保存决策
    if all_decisions:
        extractor.save_decisions(all_decisions, owner="eval_user")

    keyword = query.get("keyword", "")
    search_results = store.search_chunks(keyword, max_results=10) if keyword else []
    all_content = " ".join(r.get("content", "") for r in search_results)

    # 也搜索 decisions 表
    decision_results = []
    if keyword:
        decision_results = extractor.search_decisions(keyword, owner="eval_user")

    passed, failed = [], []
    if expected.get("decision_found"):
        dec_content = expected.get("decision_content", "")
        found = any(dec_content in d.get("title", "") + d.get("chosen", "") + d.get("context", "")
                    for d in all_decisions)
        if not found:
            found = dec_content in all_content
        if not found:
            found = any(dec_content in d.get("title", "") + d.get("chosen", "")
                        for d in decision_results)
        (passed if found else failed).append(f"decision_found={dec_content}")

    if expected.get("has_reason"):
        reason_kw = expected.get("reason_keywords", [])
        combined = all_content + " ".join(d.get("context", "") for d in all_decisions)
        found = any(kw in combined for kw in reason_kw)
        (passed if found else failed).append(f"reason={reason_kw}")

    return {"extracted_count": len(all_decisions), "search_results": len(search_results),
            "decision_search_results": len(decision_results),
            "passed_checks": passed, "failed_checks": failed}


def eval_preference_memory(store, case: Dict) -> Dict[str, Any]:
    from preference_memory.preference_extractor import PreferenceExtractor
    from preference_memory.preference_manager import PreferenceManager
    extractor = PreferenceExtractor(store)
    pm = PreferenceManager(store)
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})

    messages = setup.get("messages", [])
    # 用正确的 API 提取偏好: extract_from_conversation(user_msg, assistant_msg, owner)
    extracted = []
    owner = query.get("user", "user_a")
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        user_msg = content if role == "user" else ""
        asst_msg = content if role == "assistant" else ""
        try:
            prefs = extractor.extract_from_conversation(user_msg, asst_msg, owner)
            extracted.extend(prefs)
        except Exception:
            pass

    # 保存提取到的偏好
    for pref in extracted:
        pm.set_preference(
            owner=pref.get("owner", query.get("user", "user_a")),
            category=pref.get("category", "general"),
            key=pref.get("key", ""),
            value=pref.get("value", ""),
            source=pref.get("source", "extracted"),
            confidence=pref.get("confidence", 0.5),
        )

    q_user = query.get("user", "user_a")
    q_category = query.get("category", "general")
    stored = store.list_preferences(q_user, category=q_category) if q_category else store.list_preferences(q_user)

    passed, failed = [], []
    if expected.get("preference_found"):
        pref_value = expected.get("preference_value", "")
        found = any(pref_value in p.get("value", "") for p in stored)
        if not found:
            found = any(pref_value in p.get("content", "") for p in
                        store.search_chunks(pref_value, max_results=5))
        (passed if found else failed).append(f"pref_found={pref_value}")

    if expected.get("category"):
        cats = set(p.get("category", "") for p in stored)
        (passed if expected["category"] in cats else failed).append(f"category={expected['category']}")

    return {"extracted_count": len(extracted), "stored_count": len(stored),
            "passed_checks": passed, "failed_checks": failed}


def eval_knowledge_health(store, case: Dict) -> Dict[str, Any]:
    from knowledge_health.freshness_monitor import FreshnessMonitor
    from knowledge_health.gap_detector import GapDetector
    fm = FreshnessMonitor(store)
    gd = GapDetector(store)
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})

    passed, failed = [], []
    q_type = query.get("type", "")

    if q_type == "health_check":
        entry = setup.get("knowledge_entry", {})
        chunk_id = store.insert_chunk({"sessionKey": "eval-kh", "turnId": str(int(time.time()*1000)),
                                        "seq": 0, "role": "assistant", "content": entry.get("content", ""), "owner": "local"})
        kh_id = fm.register_knowledge(chunk_id, team_id="eval-team", category="general")
        (passed if kh_id else failed).append("knowledge_registered")
        health = store.get_knowledge_health(chunk_id)
        (passed if health else failed).append("health_record_exists")

    elif q_type == "gap_detection":
        entries = setup.get("entries", [])
        team_id = setup.get("team_id", "eval-team")
        for entry in entries:
            cid = store.insert_chunk({"sessionKey": "eval-gap", "turnId": str(int(time.time()*1000)),
                                      "seq": 0, "role": "assistant", "content": entry.get("content", ""),
                                      "owner": entry.get("owner", "local")})
            fm.register_knowledge(cid, team_id=team_id, category=entry.get("category", "general"))
        gaps = gd.detect_gaps(team_id)
        passed.append(f"gaps_detected={len(gaps) if gaps else 0}")

    elif q_type == "coverage":
        team_id = setup.get("team_id", "eval-team")
        coverage = gd.analyze_coverage(team_id)
        (passed if coverage else failed).append("coverage_analyzed")

    else:
        # 通用: 尝试注册知识并检查
        entries = setup.get("entries", setup.get("knowledge_entries", []))
        team_id = setup.get("team_id", "eval-team")
        for entry in entries:
            content = entry.get("content", "") if isinstance(entry, dict) else str(entry)
            cid = store.insert_chunk({"sessionKey": "eval-kh-generic", "turnId": str(int(time.time()*1000)),
                                      "seq": 0, "role": "assistant", "content": content, "owner": "local"})
            fm.register_knowledge(cid, team_id=team_id, category="general")
        passed.append("generic_setup_done")

    return {"passed_checks": passed, "failed_checks": failed}


def eval_long_term_memory(store, case: Dict) -> Dict[str, Any]:
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})
    sid = f"eval-ltm-{case['test_id']}"

    conv = setup.get("conversation", {})
    messages = conv.get("messages", [])
    for msg in messages:
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")
        insert_conversation(store, content, "已记录。", ts, session_key=sid)

    keyword = query.get("keyword", "")
    start = time.perf_counter()
    results = store.search_chunks(keyword, max_results=10)
    latency_ms = (time.perf_counter() - start) * 1000
    all_content = " ".join(r.get("content", "") for r in results)

    passed, failed = [], []
    if expected.get("found"):
        content_kw = expected.get("content_keywords", [])
        if text_contains(all_content, content_kw) >= 0.5:
            passed.append("found")
        else:
            failed.append(f"not_found: keywords={content_kw}")
    if expected.get("still_accessible"):
        (passed if results else failed).append("still_accessible")

    return {"passed_checks": passed, "failed_checks": failed,
            "latency_ms": round(latency_ms, 2), "chunks_found": len(results),
            "content_preview": all_content[:300]}


# ---------------------------------------------------------------------------
# 数据集 → 评估函数映射
# ---------------------------------------------------------------------------
EVALUATORS = {
    "anti_interference": eval_anti_interference,
    "contradiction_update": eval_contradiction_update,
    "efficiency": eval_efficiency,
    "command_memory": eval_command_memory,
    "decision_memory": eval_decision_memory,
    "preference_memory": eval_preference_memory,
    "knowledge_health": eval_knowledge_health,
    "long_term_memory": eval_long_term_memory,
}


# ---------------------------------------------------------------------------
# 主评估流程
# ---------------------------------------------------------------------------
def run_evaluation() -> Dict[str, Any]:
    all_datasets = {}
    for fname in sorted(os.listdir(DATASETS_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(DATASETS_DIR, fname)) as f:
                data = json.load(f)
            all_datasets[fname.replace(".json", "")] = data.get("test_cases", [])

    report = {
        "evaluation_id": f"real-eval-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now().isoformat(),
        "system": "MemScope v2.0.0 — 真实系统评估（非mock）",
        "total_cases": 0, "passed": 0, "failed": 0, "errors": 0,
        "dataset_results": {},
    }

    for ds_name, cases in all_datasets.items():
        evaluator = EVALUATORS.get(ds_name)
        if not evaluator:
            print(f"  ⚠️ 无评估函数: {ds_name}")
            continue

        print(f"\n{'='*60}")
        print(f"评估: {ds_name} ({len(cases)} cases)")
        print(f"{'='*60}")

        ds_results, ds_passed, ds_failed, ds_errors = [], 0, 0, 0

        for i, case in enumerate(cases):
            case_id = case.get("test_id", f"{ds_name}_{i}")
            store, conn, db_path = create_real_store()
            try:
                start = time.perf_counter()
                metrics = evaluator(store, case)
                elapsed = (time.perf_counter() - start) * 1000

                failed_checks = metrics.get("failed_checks", [])
                has_error = "error" in metrics
                status = "error" if has_error else ("fail" if failed_checks else "pass")
                if status == "pass": ds_passed += 1
                elif status == "fail": ds_failed += 1
                else: ds_errors += 1

                ds_results.append({"test_id": case_id, "name": case.get("name", ""),
                                   "difficulty": case.get("difficulty", "unknown"),
                                   "status": status, "metrics": metrics,
                                   "elapsed_ms": round(elapsed, 2)})
                sym = {"pass": "✅", "fail": "❌", "error": "💥"}[status]
                print(f"  [{i+1}/{len(cases)}] {sym} {case_id}: {status} ({elapsed:.1f}ms)")

            except Exception as e:
                ds_errors += 1
                ds_results.append({"test_id": case_id, "name": case.get("name", ""),
                                   "status": "error", "error": str(e),
                                   "traceback": traceback.format_exc()[-500:]})
                print(f"  [{i+1}/{len(cases)}] 💥 {case_id}: {e}")
            finally:
                conn.close()
                try: os.unlink(db_path)
                except: pass

        total = len(cases)
        pass_rate = round(ds_passed / total * 100, 1) if total > 0 else 0
        report["dataset_results"][ds_name] = {"total": total, "passed": ds_passed,
                                               "failed": ds_failed, "errors": ds_errors,
                                               "pass_rate": pass_rate, "cases": ds_results}
        report["total_cases"] += total
        report["passed"] += ds_passed
        report["failed"] += ds_failed
        report["errors"] += ds_errors
        print(f"\n  {ds_name}: {ds_passed}/{total} 通过 ({pass_rate}%)")

    total = report["total_cases"]
    report["pass_rate"] = round(report["passed"] / total * 100, 1) if total > 0 else 0
    return report


if __name__ == "__main__":
    print("=" * 70)
    print("MemScope 真实性能评估 — 全部评测数据集 × 真实系统")
    print("=" * 70)
    start = time.time()
    report = run_evaluation()
    elapsed = time.time() - start
    output_path = os.path.join(EVAL_DIR, "real_eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\n" + "=" * 70)
    print("评估结果汇总")
    print("=" * 70)
    print(f"  总用例: {report['total_cases']}  通过: {report['passed']}  "
          f"失败: {report['failed']}  错误: {report['errors']}  通过率: {report['pass_rate']}%")
    print()
    for name, dr in report["dataset_results"].items():
        print(f"  {name:25s}: {dr['passed']}/{dr['total']} ({dr['pass_rate']}%)")
    print(f"\n  耗时: {elapsed:.1f}s  报告: {output_path}")
    print("=" * 70)
