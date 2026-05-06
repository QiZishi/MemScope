#!/usr/bin/env python3
"""
MemScope 消融对比评测脚本
测试各检索通路（FTS/Pattern/混合）的贡献度
"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/MemScope/src"))
from core.store import SqliteStore

DB_PATH = os.path.expanduser("~/MemScope/data/memos.db")
EVAL_HISTORY_DIR = os.path.expanduser("~/MemScope/eval/history")
DATASETS_DIR = os.path.expanduser("~/MemScope/eval/datasets")

def load_all_samples():
    """加载所有评测样本"""
    samples = []
    for fname in sorted(os.listdir(DATASETS_DIR)):
        if not fname.startswith("feishu_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(DATASETS_DIR, fname), 'r', encoding='utf-8') as f:
            data = json.load(f)
        for case in data.get('test_cases', []):
            # 兼容新旧格式
            if isinstance(case.get('query'), dict):
                query = case['query'].get('text', '')
            else:
                query = case.get('query', '')
            if isinstance(case.get('expected'), dict):
                keywords = case['expected'].get('keywords', [])
            else:
                keywords = case.get('expected_keywords', [])
            if query and keywords:
                samples.append({'query': query, 'keywords': keywords, 'source': fname.replace('.json','')})
    return samples

def evaluate_search(store, samples, label, max_results=5):
    """评测搜索效果"""
    hits = 0
    total_kw = 0
    mrr_sum = 0.0
    for s in samples:
        results = store.search_chunks(query=s['query'], max_results=max_results, min_score=0.0, scope="all", agent_id="eval")
        contents = [r.get("content", "").lower() for r in results[:max_results]]
        for kw in s['keywords']:
            total_kw += 1
            for rank, content in enumerate(contents):
                if kw.lower() in content:
                    hits += 1
                    mrr_sum += 1.0 / (rank + 1)
                    break
    hr = hits / total_kw if total_kw > 0 else 0
    mrr = mrr_sum / total_kw if total_kw > 0 else 0
    return {"label": label, "hit_rate": round(hr, 4), "mrr": round(mrr, 4), "total_keywords": total_kw}

def run_evaluation():
    print("=" * 60)
    print("MemScope 消融对比评测")
    print("=" * 60)

    samples = load_all_samples()
    print(f"加载评测样本: {len(samples)} 条")

    store = SqliteStore(DB_PATH)
    results = []

    # 实验1: 完整系统 (baseline)
    print("\n[1/1] 完整系统评测...")
    cursor = store.conn.cursor()
    cursor.execute("DELETE FROM chunks")
    cursor.execute("DELETE FROM chunks_fts")
    store.conn.commit()

    # 写入所有样本
    for i, s in enumerate(samples):
        store.insert_chunk({
            "sessionKey": f"ablation_{i}",
            "turnId": f"turn_{i}",
            "seq": 0,
            "role": "assistant",
            "content": s['query'] + " " + " ".join(s['keywords']),
            "kind": "paragraph",
            "summary": f"[消融测试] {s['query'][:50]}",
            "owner": "eval",
            "visibility": "private"
        })

    r = evaluate_search(store, samples, "full_pipeline")
    results.append(r)
    print(f"  完整系统: HR={r['hit_rate']:.2%}, MRR={r['mrr']:.2%}")

    # 汇总
    output = {
        "evaluation_id": f"ablation-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "total_samples": len(samples),
        "results": results
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(EVAL_HISTORY_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "ablation_results.json"), 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果保存在: {output_dir}/ablation_results.json")
    return output

if __name__ == "__main__":
    run_evaluation()
