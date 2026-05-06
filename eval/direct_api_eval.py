#!/usr/bin/env python3
"""
MemScope 直接API评测脚本 (v2)
直接调用MemScope的API来测试检索能力

支持:
- 新旧数据集格式 (chunk / setup.conversations[])
- Recall@k (k=1,3,5)
- MRR (Mean Reciprocal Rank)
- 真实延迟测量
- 加权评分
- JSON报告输出
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加src到Python路径
sys.path.insert(0, os.path.expanduser("~/MemScope/src"))

from core.store import SqliteStore

# 配置
DB_PATH = os.path.expanduser("~/MemScope/data/memos.db")
EVAL_HISTORY_DIR = os.path.expanduser("~/MemScope/eval/history")

# 所有评测数据集
DATASETS = [
    "feishu_decision_memory",
    "feishu_knowledge_health",
    "feishu_preference_memory",
    "feishu_command_memory",
    "feishu_long_term_memory",
    "feishu_efficiency",
    "feishu_contradiction_update",
    "feishu_anti_interference"
]

# 维度权重 (可根据需要调整)
DIMENSION_WEIGHTS = {
    "feishu_decision_memory": 1.0,
    "feishu_knowledge_health": 1.0,
    "feishu_preference_memory": 1.0,
    "feishu_command_memory": 1.0,
    "feishu_long_term_memory": 1.0,
    "feishu_efficiency": 1.0,
    "feishu_contradiction_update": 1.0,
    "feishu_anti_interference": 1.0,
}

MAX_RESULTS = 5


def load_dataset(dataset_name: str) -> Dict[str, Any]:
    """加载评测数据集"""
    dataset_path = os.path.expanduser(f"~/MemScope/eval/datasets/{dataset_name}.json")
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_recall_at_k(result_contents: List[str], expected_keywords: List[str], k: int) -> float:
    """计算Recall@k: 在top-k结果中是否包含期望关键词"""
    if not expected_keywords:
        return 1.0
    top_k = result_contents[:k]
    hits = 0
    for keyword in expected_keywords:
        for content in top_k:
            if keyword.lower() in content:
                hits += 1
                break
    return hits / len(expected_keywords)


def compute_mrr(result_contents: List[str], expected_keywords: List[str]) -> float:
    """计算MRR (Mean Reciprocal Rank): 第一个相关结果的倒数排名的均值"""
    if not expected_keywords:
        return 1.0
    reciprocal_ranks = []
    for keyword in expected_keywords:
        found_rank = 0
        for rank_idx, content in enumerate(result_contents):
            if keyword.lower() in content:
                found_rank = rank_idx + 1  # 1-indexed
                break
        if found_rank > 0:
            reciprocal_ranks.append(1.0 / found_rank)
        else:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0


def compute_memory_metrics(search_results: List[Dict], expected_keywords: List[str],
                          forbidden_keywords: List[str]) -> Dict[str, float]:
    """
    公平客观的Memory指标计算，包含Recall@k和MRR
    """
    if not search_results:
        return {
            'hit_rate': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0,
            'recall_at_1': 0.0, 'recall_at_3': 0.0, 'recall_at_5': 0.0, 'mrr': 0.0
        }

    # 提取搜索结果的内容
    result_contents = [r.get("content", "").lower() for r in search_results[:MAX_RESULTS]]

    # 计算命中率 (等同于 Recall@MAX_RESULTS)
    hits = 0
    total_expected = len(expected_keywords)
    if total_expected == 0:
        hit_rate = 1.0 if result_contents else 0.0
    else:
        for keyword in expected_keywords:
            for content in result_contents:
                if keyword.lower() in content:
                    hits += 1
                    break
        hit_rate = hits / total_expected

    # 计算精确率
    relevant_count = 0
    for content in result_contents:
        is_relevant = False
        for keyword in expected_keywords:
            if keyword.lower() in content:
                is_relevant = True
                break
        if is_relevant:
            relevant_count += 1
    precision = relevant_count / len(result_contents) if result_contents else 0.0

    # 召回率等于命中率
    recall = hit_rate

    # F1分数
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Recall@k
    recall_at_1 = compute_recall_at_k(result_contents, expected_keywords, 1)
    recall_at_3 = compute_recall_at_k(result_contents, expected_keywords, 3)
    recall_at_5 = compute_recall_at_k(result_contents, expected_keywords, 5)

    # MRR
    mrr = compute_mrr(result_contents, expected_keywords)

    return {
        'hit_rate': hit_rate,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'recall_at_1': recall_at_1,
        'recall_at_3': recall_at_3,
        'recall_at_5': recall_at_5,
        'mrr': mrr
    }


def insert_single_turn(store: SqliteStore, dataset_name: str, test_id: str,
                        seq: int, role: str, content: str, timestamp: Optional[str] = None) -> float:
    """插入单条对话到存储，返回插入延迟(ms)"""
    t0 = time.time()
    chunk_data = {
        "sessionKey": f"eval_{dataset_name}",
        "turnId": test_id,
        "seq": seq,
        "role": role,
        "content": content,
        "kind": "paragraph",
        "summary": f"[记忆存储] {content[:100]}...",
        "owner": "eval",
        "visibility": "private"
    }
    if timestamp:
        chunk_data["timestamp"] = timestamp
    store.insert_chunk(chunk_data)
    return (time.time() - t0) * 1000  # ms


def evaluate_test_case(test_case: Dict[str, Any], store: SqliteStore, dataset_name: str) -> Dict[str, Any]:
    """评测单个测试用例，支持新旧两种数据格式"""
    test_id = test_case['test_id']
    name = test_case['name']
    setup = test_case.get('setup', {})

    # 兼容新旧格式: query/answer/keywords
    if isinstance(test_case.get('query'), dict):
        query = test_case['query'].get('text', '')
    else:
        query = test_case.get('query', '')

    if isinstance(test_case.get('expected'), dict):
        answer = test_case['expected'].get('answer', '')
        expected_keywords = test_case['expected'].get('keywords', [])
        forbidden_keywords = test_case['expected'].get('forbidden', [])
    else:
        answer = test_case.get('answer', '')
        expected_keywords = test_case.get('expected_keywords', [])
        forbidden_keywords = test_case.get('forbidden_keywords', [])

    print(f"  评测用例: {name}")

    # ---- 插入记忆 ----
    insert_latencies = []

    # 检测新格式: setup.conversations[]
    conversations = setup.get('conversations', []) if setup else []
    if conversations:
        # 新格式: 逐轮写入
        for idx, turn in enumerate(conversations):
            role = turn.get('role', 'user')
            content = turn.get('content', '')
            ts = turn.get('timestamp')
            lat = insert_single_turn(store, dataset_name, test_id, idx, role, content, ts)
            insert_latencies.append(lat)
    elif 'chunk' in test_case:
        # 旧格式: 单条chunk
        lat = insert_single_turn(store, dataset_name, test_id, 0, "assistant", test_case['chunk'])
        insert_latencies.append(lat)
    else:
        print(f"    ⚠️ 无可用记忆数据 (无 chunk 也无 conversations)")

    avg_insert_latency = sum(insert_latencies) / len(insert_latencies) if insert_latencies else 0.0

    # ---- 搜索记忆 ----
    t0 = time.time()
    search_results = store.search_chunks(
        query=query,
        max_results=MAX_RESULTS,
        min_score=0.0,
        scope="all",
        agent_id="eval"
    )
    search_latency = (time.time() - t0) * 1000  # ms

    # ---- 计算指标 ----
    metrics = compute_memory_metrics(search_results, expected_keywords, forbidden_keywords)

    # 噪声注入率
    result_contents = [r.get("content", "").lower() for r in search_results[:MAX_RESULTS]]
    noise_count = sum(1 for content in result_contents
                     for k in forbidden_keywords if k.lower() in content)
    noise_injection_rate = noise_count / len(result_contents) if result_contents else 0.0

    # 从结果中提取实际返回的内容片段（用于报告）
    top_contents = [r.get("content", "")[:200] for r in search_results[:MAX_RESULTS]]

    result = {
        'test_id': test_id,
        'name': name,
        'difficulty': test_case.get('difficulty', 'medium'),
        'category': test_case.get('category', ''),
        'format': 'multi_turn' if conversations else 'single_chunk',
        'num_chunks_written': len(insert_latencies),
        'query': query,
        'answer': answer,
        'expected_keywords': expected_keywords,
        'forbidden_keywords': forbidden_keywords,
        # 传统指标
        'hit_rate': metrics['hit_rate'],
        'precision': metrics['precision'],
        'recall': metrics['recall'],
        'f1_score': metrics['f1_score'],
        # 新增指标
        'recall_at_1': metrics['recall_at_1'],
        'recall_at_3': metrics['recall_at_3'],
        'recall_at_5': metrics['recall_at_5'],
        'mrr': metrics['mrr'],
        'noise_injection_rate': noise_injection_rate,
        # 延迟
        'insert_latency_ms': round(avg_insert_latency, 2),
        'search_latency_ms': round(search_latency, 2),
        # 元数据
        'results_count': len(search_results),
        'top_results_preview': top_contents
    }

    print(f"    R@1={metrics['recall_at_1']:.2f} R@3={metrics['recall_at_3']:.2f} "
          f"R@5={metrics['recall_at_5']:.2f} MRR={metrics['mrr']:.2f} "
          f"insert={avg_insert_latency:.1f}ms search={search_latency:.1f}ms")

    return result


def evaluate_dataset(dataset_name: str, store: SqliteStore) -> Dict[str, Any]:
    """评测单个数据集"""
    print(f"\n{'='*60}")
    print(f"评测数据集: {dataset_name}")
    print(f"{'='*60}")

    # 数据库隔离：清除所有chunks和FTS索引，防止跨数据集污染
    cursor = store.conn.cursor()
    cursor.execute("DELETE FROM chunks")
    cursor.execute("DELETE FROM chunks_fts")
    store.conn.commit()
    print(f"  已清除旧数据，开始干净评测")

    dataset = load_dataset(dataset_name)
    test_cases = dataset['test_cases']

    results = []
    for test_case in test_cases:
        result = evaluate_test_case(test_case, store, dataset_name)
        results.append(result)

    # 计算汇总指标
    total_cases = len(results)
    if total_cases == 0:
        return {'test_cases': results, 'summary': {
            'total_cases': 0, 'avg_hit_rate': 0, 'avg_precision': 0,
            'avg_recall': 0, 'avg_f1_score': 0, 'avg_noise_injection_rate': 0,
            'avg_recall_at_1': 0, 'avg_recall_at_3': 0, 'avg_recall_at_5': 0,
            'avg_mrr': 0, 'avg_insert_latency_ms': 0, 'avg_search_latency_ms': 0,
            'difficulty_distribution': {}
        }}

    def avg(key):
        return sum(r[key] for r in results) / total_cases

    summary = {
        'total_cases': total_cases,
        'avg_hit_rate': avg('hit_rate'),
        'avg_precision': avg('precision'),
        'avg_recall': avg('recall'),
        'avg_f1_score': avg('f1_score'),
        'avg_noise_injection_rate': avg('noise_injection_rate'),
        'avg_recall_at_1': avg('recall_at_1'),
        'avg_recall_at_3': avg('recall_at_3'),
        'avg_recall_at_5': avg('recall_at_5'),
        'avg_mrr': avg('mrr'),
        'avg_insert_latency_ms': avg('insert_latency_ms'),
        'avg_search_latency_ms': avg('search_latency_ms'),
        'difficulty_distribution': {}
    }

    for r in results:
        diff = r.get('difficulty', 'medium')
        summary['difficulty_distribution'][diff] = summary['difficulty_distribution'].get(diff, 0) + 1

    return {'test_cases': results, 'summary': summary}


def compute_overall_score(overall_metrics: Dict[str, float]) -> float:
    """
    加权综合评分 (0-100)
    权重分配:
      - recall_at_5: 25%
      - mrr:         20%
      - precision:   15%
      - f1_score:    15%
      - recall_at_1: 10%
      - noise (反向): 10%
      - search_latency (反向): 5%
    """
    weights = {
        'recall_at_5': 0.25,
        'mrr': 0.20,
        'precision': 0.15,
        'f1_score': 0.15,
        'recall_at_1': 0.10,
    }
    score = 0.0
    for key, w in weights.items():
        score += overall_metrics.get(key, 0) * w * 100

    # 噪声越少越好 (反向指标, 0 noise = 10分)
    noise = overall_metrics.get('noise_injection_rate', 0)
    score += (1.0 - noise) * 10

    # 搜索延迟越低越好 (反向指标, <=100ms满分)
    lat = overall_metrics.get('avg_search_latency_ms', 0)
    lat_score = max(0, 1.0 - lat / 1000) * 5  # 1000ms -> 0, 0ms -> 5
    score += lat_score

    return round(score, 2)


def generate_report(eval_results: Dict[str, Any], timestamp: str) -> str:
    """生成Markdown评测报告"""
    om = eval_results['overall_metrics']
    report = f"""# MemScope 直接API评测报告 (v2)

**评测时间**: {timestamp}
**评测ID**: {eval_results['evaluation_id']}
**评测方式**: 直接调用MemScope API
**综合评分**: {om.get('overall_score', 'N/A')}

## 总体Memory指标

| 指标 | 值 | 说明 |
|------|-----|------|
| **Recall@1** | **{om['recall_at_1']:.2%}** | Top-1结果命中率 |
| **Recall@3** | **{om['recall_at_3']:.2%}** | Top-3结果命中率 |
| **Recall@5** | **{om['recall_at_5']:.2%}** | Top-5结果命中率 |
| **MRR** | **{om['mrr']:.2%}** | Mean Reciprocal Rank |
| **命中率 Hit Rate** | **{om['hit_rate']:.2%}** | 搜索结果中包含目标信息的比例 |
| **精确率 Precision** | **{om['precision']:.2%}** | 搜索结果中正确信息的比例 |
| **F1分数** | **{om['f1_score']:.2%}** | 精确率和召回率的调和平均 |
| 噪声注入率 | {om['noise_injection_rate']:.2%} | 搜索结果中噪声信息的比例 |
| 平均搜索延迟 | {om.get('avg_search_latency_ms', 0):.1f}ms | 搜索API调用延迟 |
| 平均写入延迟 | {om.get('avg_insert_latency_ms', 0):.1f}ms | 写入API调用延迟 |
| 总测试用例 | {om['total_cases']} | - |

## 各数据集指标

| 数据集 | R@1 | R@3 | R@5 | MRR | Precision | F1 | 搜索延迟 | 用例数 |
|--------|-----|-----|-----|-----|-----------|-----|---------|--------|
"""

    for dataset_name, dataset_result in eval_results['datasets'].items():
        s = dataset_result['summary']
        report += (f"| {dataset_name} | {s['avg_recall_at_1']:.2%} | {s['avg_recall_at_3']:.2%} | "
                   f"{s['avg_recall_at_5']:.2%} | {s['avg_mrr']:.2%} | "
                   f"{s['avg_precision']:.2%} | {s['avg_f1_score']:.2%} | "
                   f"{s['avg_search_latency_ms']:.1f}ms | {s['total_cases']} |\n")

    return report


def run_evaluation():
    """运行完整评测"""
    print("=" * 80)
    print("MemScope 直接API评测开始 (v2)")
    print("=" * 80)

    # 初始化MemScope
    store = SqliteStore(DB_PATH)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_id = f"direct-v2-{timestamp}"

    all_results = {}
    for dataset_name in DATASETS:
        try:
            dataset_result = evaluate_dataset(dataset_name, store)
            all_results[dataset_name] = dataset_result
        except Exception as e:
            print(f"评测数据集 {dataset_name} 失败: {e}")
            import traceback
            traceback.print_exc()

    # 计算加权总体指标
    total_cases = sum(r['summary']['total_cases'] for r in all_results.values())
    if total_cases > 0:
        def weighted_avg(key):
            return sum(r['summary'].get(key, 0) * r['summary']['total_cases']
                       for r in all_results.values()) / total_cases

        overall_metrics = {
            'total_cases': total_cases,
            'hit_rate': weighted_avg('avg_hit_rate'),
            'precision': weighted_avg('avg_precision'),
            'recall': weighted_avg('avg_recall'),
            'f1_score': weighted_avg('avg_f1_score'),
            'noise_injection_rate': weighted_avg('avg_noise_injection_rate'),
            'recall_at_1': weighted_avg('avg_recall_at_1'),
            'recall_at_3': weighted_avg('avg_recall_at_3'),
            'recall_at_5': weighted_avg('avg_recall_at_5'),
            'mrr': weighted_avg('avg_mrr'),
            'avg_insert_latency_ms': weighted_avg('avg_insert_latency_ms'),
            'avg_search_latency_ms': weighted_avg('avg_search_latency_ms'),
        }
    else:
        overall_metrics = {
            'total_cases': 0, 'hit_rate': 0, 'precision': 0, 'recall': 0,
            'f1_score': 0, 'noise_injection_rate': 0, 'recall_at_1': 0,
            'recall_at_3': 0, 'recall_at_5': 0, 'mrr': 0,
            'avg_insert_latency_ms': 0, 'avg_search_latency_ms': 0,
        }

    overall_score = compute_overall_score(overall_metrics)
    overall_metrics['overall_score'] = overall_score

    eval_results = {
        'evaluation_id': eval_id,
        'timestamp': datetime.now().isoformat(),
        'version': 'v2',
        'max_results': MAX_RESULTS,
        'datasets': all_results,
        'overall_metrics': overall_metrics
    }

    # 保存结果
    output_dir = os.path.join(EVAL_HISTORY_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, 'eval_results.json'), 'w', encoding='utf-8') as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)

    report = generate_report(eval_results, timestamp)
    with open(os.path.join(output_dir, 'eval_report.md'), 'w', encoding='utf-8') as f:
        f.write(report)

    print("\n" + "=" * 80)
    print("评测完成！")
    print("=" * 80)
    print(f"\n总体Memory指标:")
    print(f"  综合评分: {overall_score}")
    print(f"  Recall@1: {overall_metrics['recall_at_1']:.2%}")
    print(f"  Recall@3: {overall_metrics['recall_at_3']:.2%}")
    print(f"  Recall@5: {overall_metrics['recall_at_5']:.2%}")
    print(f"  MRR:      {overall_metrics['mrr']:.2%}")
    print(f"  F1分数:   {overall_metrics['f1_score']:.2%}")
    print(f"  平均搜索延迟: {overall_metrics['avg_search_latency_ms']:.1f}ms")
    print(f"\n结果保存在: {output_dir}")

    return eval_results


if __name__ == "__main__":
    run_evaluation()
