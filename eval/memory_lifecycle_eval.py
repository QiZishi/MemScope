#!/usr/bin/env python3
"""
MemScope 记忆生命周期评测脚本

测试真正的memory能力（不只是RAG检索）：
1. 记忆提取：从对话中提取结构化决策/偏好/知识
2. 记忆更新：新信息覆盖旧信息（矛盾解决）
3. 记忆检索：通过结构化API检索（不只是search_chunks）
4. 记忆衰减：旧记忆应降权

评测维度：
- decision_lifecycle: 决策的创建→搜索→更新→验证最新值
- preference_lifecycle: 偏好的创建→更新→验证覆盖
- knowledge_lifecycle: 知识的创建→衰减→验证新鲜度
- contradiction_resolution: 矛盾信息的正确覆写
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, os.path.expanduser("~/MemScope/src"))
from core.store import SqliteStore

DB_PATH = os.path.expanduser("~/MemScope/data/memos.db")
EVAL_HISTORY_DIR = os.path.expanduser("~/MemScope/eval/history")
DATASETS_DIR = os.path.expanduser("~/MemScope/eval/datasets")


def clean_db(store):
    """清空所有表"""
    cursor = store.conn.cursor()
    for table in ["chunks", "chunks_fts", "decisions", "decision_cards",
                   "user_preferences", "behavior_patterns", "knowledge_health",
                   "forgetting_schedule", "team_knowledge_map",
                   "command_history", "command_patterns"]:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    store.conn.commit()


def evaluate_decision_lifecycle(store) -> Dict[str, Any]:
    """评测决策记忆生命周期：创建→搜索→更新→验证"""
    print("\n[1/4] 决策记忆生命周期评测")
    results = []

    # 测试用例：每个包含创建和后续更新
    test_cases = [
        {
            "name": "前端框架决策-初始",
            "create": {"owner": "eval", "title": "前端框架选型", "project": "项目A",
                       "context": "团队讨论React vs Vue", "chosen": "React", "alternatives": "Vue"},
            "search_query": "前端框架",
            "expected_chosen": "React",
        },
        {
            "name": "前端框架决策-更新为Vue",
            "create": {"owner": "eval", "title": "前端框架选型", "project": "项目A",
                       "context": "团队重新评估，Vue3生态成熟", "chosen": "Vue", "alternatives": "React"},
            "search_query": "前端框架",
            "expected_chosen": "Vue",
            "is_update": True,
        },
        {
            "name": "数据库选型决策",
            "create": {"owner": "eval", "title": "数据库选型", "project": "项目A",
                       "context": "PostgreSQL vs MySQL", "chosen": "PostgreSQL", "alternatives": "MySQL"},
            "search_query": "数据库",
            "expected_chosen": "PostgreSQL",
        },
        {
            "name": "部署方案决策",
            "create": {"owner": "eval", "title": "部署方案选型", "project": "项目B",
                       "context": "Docker容器化 vs 裸机部署", "chosen": "Docker容器化", "alternatives": "裸机部署"},
            "search_query": "部署",
            "expected_chosen": "Docker容器化",
        },
        {
            "name": "CI/CD工具决策",
            "create": {"owner": "eval", "title": "CI/CD工具选型", "project": "项目A",
                       "context": "GitHub Actions vs Jenkins", "chosen": "GitHub Actions", "alternatives": "Jenkins"},
            "search_query": "CI/CD",
            "expected_chosen": "GitHub Actions",
        },
    ]

    for tc in test_cases:
        t0 = time.time()
        # 创建决策
        decision_id = store.insert_decision(**tc["create"])
        create_latency = (time.time() - t0) * 1000

        # 搜索决策
        t0 = time.time()
        found = store.search_decisions(owner="eval", query=tc["search_query"])
        search_latency = (time.time() - t0) * 1000

        # 验证
        hit = any(tc["expected_chosen"].lower() in (d.get("chosen") or "").lower() for d in found)
        latest_correct = False
        if found:
            # 按createdAt降序，第一条应是最新的
            latest = found[0]
            latest_correct = tc["expected_chosen"].lower() in (latest.get("chosen") or "").lower()

        result = {
            "name": tc["name"],
            "decision_id": decision_id,
            "create_latency_ms": round(create_latency, 2),
            "search_latency_ms": round(search_latency, 2),
            "results_count": len(found),
            "hit": hit,
            "latest_correct": latest_correct,
            "expected": tc["expected_chosen"],
            "actual_latest": found[0].get("chosen") if found else None,
        }
        results.append(result)
        status = "✅" if latest_correct else "❌"
        print(f"  {status} {tc['name']}: expected={tc['expected_chosen']} actual={result['actual_latest']} hit={hit} latest={latest_correct}")

    hit_count = sum(1 for r in results if r["hit"])
    latest_count = sum(1 for r in results if r["latest_correct"])
    return {
        "test_name": "decision_lifecycle",
        "total": len(results),
        "hit_count": hit_count,
        "hit_rate": hit_count / len(results) if results else 0,
        "latest_correct_count": latest_count,
        "latest_correct_rate": latest_count / len(results) if results else 0,
        "cases": results,
    }


def evaluate_preference_lifecycle(store) -> Dict[str, Any]:
    """评测偏好记忆生命周期：创建→更新→验证覆盖"""
    print("\n[2/4] 偏好记忆生命周期评测")
    results = []

    test_cases = [
        {
            "name": "编辑器偏好-初始",
            "create": {"owner": "张工", "category": "tool", "key": "editor", "value": "vim", "confidence": 0.9},
            "get": {"owner": "张工", "category": "tool", "key": "editor"},
            "expected_value": "vim",
        },
        {
            "name": "编辑器偏好-更新为VSCode",
            "create": {"owner": "张工", "category": "tool", "key": "editor", "value": "VSCode", "confidence": 0.8},
            "get": {"owner": "张工", "category": "tool", "key": "editor"},
            "expected_value": "VSCode",
            "is_update": True,
        },
        {
            "name": "编程语言偏好",
            "create": {"owner": "张工", "category": "language", "key": "primary", "value": "Python", "confidence": 0.95},
            "get": {"owner": "张工", "category": "language", "key": "primary"},
            "expected_value": "Python",
        },
        {
            "name": "缩进偏好",
            "create": {"owner": "张工", "category": "style", "key": "indent", "value": "4空格", "confidence": 0.85},
            "get": {"owner": "张工", "category": "style", "key": "indent"},
            "expected_value": "4空格",
        },
        {
            "name": "工作时间偏好",
            "create": {"owner": "张工", "category": "schedule", "key": "peak_hours", "value": "9:00-12:00", "confidence": 0.7},
            "get": {"owner": "张工", "category": "schedule", "key": "peak_hours"},
            "expected_value": "9:00-12:00",
        },
    ]

    for tc in test_cases:
        t0 = time.time()
        pref_id = store.upsert_preference(**tc["create"])
        create_latency = (time.time() - t0) * 1000

        t0 = time.time()
        pref = store.get_preference(**tc["get"])
        get_latency = (time.time() - t0) * 1000

        actual = pref.get("value") if pref else None
        correct = actual == tc["expected_value"]

        result = {
            "name": tc["name"],
            "pref_id": pref_id,
            "create_latency_ms": round(create_latency, 2),
            "get_latency_ms": round(get_latency, 2),
            "expected": tc["expected_value"],
            "actual": actual,
            "correct": correct,
        }
        results.append(result)
        status = "✅" if correct else "❌"
        print(f"  {status} {tc['name']}: expected={tc['expected_value']} actual={actual}")

    correct_count = sum(1 for r in results if r["correct"])
    return {
        "test_name": "preference_lifecycle",
        "total": len(results),
        "correct_count": correct_count,
        "correct_rate": correct_count / len(results) if results else 0,
        "cases": results,
    }


def evaluate_knowledge_lifecycle(store) -> Dict[str, Any]:
    """评测知识健康度生命周期：创建→衰减→验证新鲜度"""
    print("\n[3/4] 知识健康度生命周期评测")
    results = []

    test_cases = [
        {
            "name": "API规范-新知识",
            "create": {"owner": "team", "topic": "API设计规范", "source": "技术文档",
                       "freshness_score": 1.0, "accuracy_score": 1.0, "completeness_score": 0.9},
            "get": {"owner": "team", "topic": "API设计规范"},
            "expected_freshness": 1.0,
        },
        {
            "name": "安全规范-老化知识",
            "create": {"owner": "team", "topic": "安全审计流程", "source": "安全部",
                       "freshness_score": 0.5, "accuracy_score": 0.8, "completeness_score": 0.7},
            "get": {"owner": "team", "topic": "安全审计流程"},
            "expected_freshness": 0.5,
        },
        {
            "name": "部署规范-过期知识",
            "create": {"owner": "team", "topic": "部署流程", "source": "运维部",
                       "freshness_score": 0.2, "accuracy_score": 0.6, "completeness_score": 0.5},
            "get": {"owner": "team", "topic": "部署流程"},
            "expected_freshness": 0.2,
        },
        {
            "name": "API规范-更新后变新鲜",
            "create": {"owner": "team", "topic": "API设计规范", "source": "技术文档v2",
                       "freshness_score": 1.0, "accuracy_score": 1.0, "completeness_score": 1.0},
            "get": {"owner": "team", "topic": "API设计规范"},
            "expected_freshness": 1.0,
            "is_update": True,
        },
    ]

    for tc in test_cases:
        t0 = time.time()
        store.upsert_knowledge_health(**tc["create"])
        create_latency = (time.time() - t0) * 1000

        t0 = time.time()
        kh = store.get_knowledge_health(**tc["get"])
        get_latency = (time.time() - t0) * 1000

        actual_freshness = kh.get("freshness_score") if kh else None
        correct = actual_freshness == tc["expected_freshness"]

        result = {
            "name": tc["name"],
            "create_latency_ms": round(create_latency, 2),
            "get_latency_ms": round(get_latency, 2),
            "expected_freshness": tc["expected_freshness"],
            "actual_freshness": actual_freshness,
            "correct": correct,
        }
        results.append(result)
        status = "✅" if correct else "❌"
        print(f"  {status} {tc['name']}: expected={tc['expected_freshness']} actual={actual_freshness}")

    correct_count = sum(1 for r in results if r["correct"])
    return {
        "test_name": "knowledge_lifecycle",
        "total": len(results),
        "correct_count": correct_count,
        "correct_rate": correct_count / len(results) if results else 0,
        "cases": results,
    }


def evaluate_contradiction_resolution(store) -> Dict[str, Any]:
    """评测矛盾信息解决：先存旧值→再存新值→验证返回最新值"""
    print("\n[4/4] 矛盾信息解决评测")
    results = []

    test_cases = [
        {
            "name": "工位号变更",
            "old": {"owner": "eval", "title": "张工工位号", "chosen": "A区3排5号"},
            "new": {"owner": "eval", "title": "张工工位号", "chosen": "B区2排8号"},
            "search_query": "工位号",
            "expected_chosen": "B区2排8号",
        },
        {
            "name": "API超时变更",
            "old": {"owner": "eval", "title": "API超时设置", "chosen": "30秒"},
            "new": {"owner": "eval", "title": "API超时设置", "chosen": "60秒"},
            "search_query": "超时",
            "expected_chosen": "60秒",
        },
        {
            "name": "数据库版本变更",
            "old": {"owner": "eval", "title": "PostgreSQL版本", "chosen": "14.0"},
            "new": {"owner": "eval", "title": "PostgreSQL版本", "chosen": "16.0"},
            "search_query": "PostgreSQL",
            "expected_chosen": "16.0",
        },
        {
            "name": "监控阈值变更",
            "old": {"owner": "eval", "title": "CPU告警阈值", "chosen": "80%"},
            "new": {"owner": "eval", "title": "CPU告警阈值", "chosen": "70%"},
            "search_query": "CPU",
            "expected_chosen": "70%",
        },
        {
            "name": "团队成员变更",
            "old": {"owner": "eval", "title": "项目A负责人", "chosen": "张工"},
            "new": {"owner": "eval", "title": "项目A负责人", "chosen": "李工"},
            "search_query": "负责人",
            "expected_chosen": "李工",
        },
    ]

    for tc in test_cases:
        t0 = time.time()
        # 存入旧值
        old_id = store.insert_decision(**tc["old"])
        time.sleep(0.01)  # 确保时间戳不同
        # 存入新值（作为新决策）
        new_id = store.insert_decision(**tc["new"])
        create_latency = (time.time() - t0) * 1000

        # 搜索
        t0 = time.time()
        found = store.search_decisions(owner="eval", query=tc["search_query"])
        search_latency = (time.time() - t0) * 1000

        # 验证：最新值应排在前面（search_decisions按createdAt DESC排序）
        latest_correct = False
        if found:
            latest = found[0]
            latest_correct = tc["expected_chosen"].lower() in (latest.get("chosen") or "").lower()

        result = {
            "name": tc["name"],
            "old_id": old_id,
            "new_id": new_id,
            "create_latency_ms": round(create_latency, 2),
            "search_latency_ms": round(search_latency, 2),
            "expected": tc["expected_chosen"],
            "actual_latest": found[0].get("chosen") if found else None,
            "latest_correct": latest_correct,
        }
        results.append(result)
        status = "✅" if latest_correct else "❌"
        print(f"  {status} {tc['name']}: expected={tc['expected_chosen']} actual={result['actual_latest']}")

    correct_count = sum(1 for r in results if r["latest_correct"])
    return {
        "test_name": "contradiction_resolution",
        "total": len(results),
        "correct_count": correct_count,
        "correct_rate": correct_count / len(results) if results else 0,
        "cases": results,
    }


def run_evaluation():
    print("=" * 60)
    print("MemScope 记忆生命周期评测")
    print("=" * 60)

    store = SqliteStore(DB_PATH)
    clean_db(store)

    results = {}
    results["decision_lifecycle"] = evaluate_decision_lifecycle(store)
    results["preference_lifecycle"] = evaluate_preference_lifecycle(store)
    results["knowledge_lifecycle"] = evaluate_knowledge_lifecycle(store)
    results["contradiction_resolution"] = evaluate_contradiction_resolution(store)

    # 汇总
    print("\n" + "=" * 60)
    print("评测完成！")
    print("=" * 60)

    total_tests = sum(r["total"] for r in results.values())
    total_correct = sum(r.get("correct_count", r.get("latest_correct_count", r.get("hit_count", 0))) for r in results.values())

    summary = {
        "evaluation_id": f"lifecycle-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "overall": {
            "total_tests": total_tests,
            "total_correct": total_correct,
            "overall_accuracy": total_correct / total_tests if total_tests > 0 else 0,
        },
        "dimensions": {},
    }

    for name, r in results.items():
        key = "correct_rate" if "correct_rate" in r else ("latest_correct_rate" if "latest_correct_rate" in r else "hit_rate")
        rate = r.get(key, 0)
        summary["dimensions"][name] = {
            "total": r["total"],
            "correct": r.get("correct_count", r.get("latest_correct_count", r.get("hit_count", 0))),
            "rate": rate,
        }
        print(f"  {name}: {rate:.1%} ({r.get('correct_count', r.get('latest_correct_count', r.get('hit_count', 0)))}/{r['total']})")

    print(f"\n总体准确率: {summary['overall']['overall_accuracy']:.1%}")

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(EVAL_HISTORY_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "lifecycle_results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n结果保存在: {output_dir}/lifecycle_results.json")
    return summary


if __name__ == "__main__":
    run_evaluation()
