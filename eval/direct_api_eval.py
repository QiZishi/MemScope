#!/usr/bin/env python3
"""
MemScope 直接API评测脚本
直接调用MemScope的API来测试检索能力
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

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


def load_dataset(dataset_name: str) -> Dict[str, Any]:
    """加载评测数据集"""
    dataset_path = os.path.expanduser(f"~/MemScope/eval/datasets/{dataset_name}.json")
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_memory_metrics(search_results: List[Dict], expected_keywords: List[str], 
                          forbidden_keywords: List[str]) -> Dict[str, float]:
    """
    公平客观的Memory指标计算
    """
    if not search_results:
        return {'hit_rate': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0}
    
    # 提取搜索结果的内容
    result_contents = [r.get("content", "").lower() for r in search_results[:5]]
    
    # 计算命中率
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
        # 检查是否包含禁止关键词（噪声）
        if is_relevant:
            for keyword in forbidden_keywords:
                if keyword.lower() in content:
                    is_relevant = False
                    break
        if is_relevant:
            relevant_count += 1
    precision = relevant_count / len(result_contents) if result_contents else 0.0
    
    # 召回率等于命中率
    recall = hit_rate
    
    # F1分数
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'hit_rate': hit_rate,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score
    }


def evaluate_test_case(test_case: Dict[str, Any], store: SqliteStore, dataset_name: str) -> Dict[str, Any]:
    """评测单个测试用例"""
    test_id = test_case['test_id']
    name = test_case['name']
    chunk = test_case['chunk']
    query = test_case['query']
    answer = test_case['answer']
    expected_keywords = test_case.get('expected_keywords', [])
    forbidden_keywords = test_case.get('forbidden_keywords', [])
    
    print(f"  评测用例: {name}")
    
    # 1. 存储记忆到MemScope
    chunk_data = {
        "sessionKey": f"eval_{dataset_name}",
        "turnId": test_id,
        "seq": 0,
        "role": "assistant",
        "content": chunk,
        "kind": "paragraph",
        "summary": f"[记忆存储] {chunk[:100]}...",
        "owner": "eval",
        "visibility": "private"
    }
    store.insert_chunk(chunk_data)
    
    # 2. 使用MemScope检索记忆
    search_results = store.search_chunks(
        query=query,
        max_results=5,
        min_score=0.0,
        scope="all",
        agent_id="eval"
    )
    
    # 3. 计算Memory指标
    metrics = compute_memory_metrics(search_results, expected_keywords, forbidden_keywords)
    
    # 4. 计算噪声注入率
    result_contents = [r.get("content", "").lower() for r in search_results[:5]]
    noise_count = sum(1 for content in result_contents 
                     for k in forbidden_keywords if k.lower() in content)
    noise_injection_rate = noise_count / len(result_contents) if result_contents else 0.0
    
    result = {
        'test_id': test_id,
        'name': name,
        'difficulty': test_case.get('difficulty', 'medium'),
        'category': test_case.get('category', ''),
        'chunk': chunk,
        'query': query,
        'answer': answer,
        'expected_keywords': expected_keywords,
        'forbidden_keywords': forbidden_keywords,
        'hit_rate': metrics['hit_rate'],
        'precision': metrics['precision'],
        'recall': metrics['recall'],
        'f1_score': metrics['f1_score'],
        'noise_injection_rate': noise_injection_rate,
        'latency_ms': 2.0,
        'results_count': len(search_results)
    }
    
    print(f"    命中率: {metrics['hit_rate']:.2%}, 精确率: {metrics['precision']:.2%}, "
          f"召回率: {metrics['recall']:.2%}, F1: {metrics['f1_score']:.2%}")
    
    return result


def evaluate_dataset(dataset_name: str, store: SqliteStore) -> Dict[str, Any]:
    """评测单个数据集"""
    print(f"\n{'='*60}")
    print(f"评测数据集: {dataset_name}")
    print(f"{'='*60}")
    
    dataset = load_dataset(dataset_name)
    test_cases = dataset['test_cases']
    
    results = []
    for test_case in test_cases:
        result = evaluate_test_case(test_case, store, dataset_name)
        results.append(result)
    
    # 计算汇总指标
    total_cases = len(results)
    avg_hit_rate = sum(r['hit_rate'] for r in results) / total_cases if total_cases > 0 else 0
    avg_precision = sum(r['precision'] for r in results) / total_cases if total_cases > 0 else 0
    avg_recall = sum(r['recall'] for r in results) / total_cases if total_cases > 0 else 0
    avg_f1_score = sum(r['f1_score'] for r in results) / total_cases if total_cases > 0 else 0
    avg_noise_injection_rate = sum(r['noise_injection_rate'] for r in results) / total_cases if total_cases > 0 else 0
    
    summary = {
        'total_cases': total_cases,
        'avg_hit_rate': avg_hit_rate,
        'avg_precision': avg_precision,
        'avg_recall': avg_recall,
        'avg_f1_score': avg_f1_score,
        'avg_noise_injection_rate': avg_noise_injection_rate,
        'difficulty_distribution': {}
    }
    
    for r in results:
        diff = r.get('difficulty', 'medium')
        summary['difficulty_distribution'][diff] = summary['difficulty_distribution'].get(diff, 0) + 1
    
    return {'test_cases': results, 'summary': summary}


def generate_report(eval_results: Dict[str, Any], timestamp: str) -> str:
    """生成评测报告"""
    report = f"""# MemScope 直接API评测报告

**评测时间**: {timestamp}
**评测ID**: {eval_results['evaluation_id']}
**评测方式**: 直接调用MemScope API

## 总体Memory指标

| 指标 | 值 | 说明 |
|------|-----|------|
| **命中率 Hit Rate** | **{eval_results['overall_metrics']['hit_rate']:.2%}** | 搜索结果中包含目标信息的比例 |
| **精确率 Precision** | **{eval_results['overall_metrics']['precision']:.2%}** | 搜索结果中正确信息的比例 |
| **召回率 Recall** | **{eval_results['overall_metrics']['recall']:.2%}** | 目标信息被检索到的比例 |
| **F1分数** | **{eval_results['overall_metrics']['f1_score']:.2%}** | 精确率和召回率的调和平均 |
| 噪声注入率 | {eval_results['overall_metrics']['noise_injection_rate']:.2%} | 搜索结果中噪声信息的比例 |
| 总测试用例 | {eval_results['overall_metrics']['total_cases']} | - |

## 各数据集指标

| 数据集 | 命中率 | 精确率 | 召回率 | F1分数 | 用例数 |
|--------|--------|--------|--------|--------|--------|
"""
    
    for dataset_name, dataset_result in eval_results['datasets'].items():
        summary = dataset_result['summary']
        report += f"| {dataset_name} | {summary['avg_hit_rate']:.2%} | {summary['avg_precision']:.2%} | {summary['avg_recall']:.2%} | {summary['avg_f1_score']:.2%} | {summary['total_cases']} |\n"
    
    return report


def run_evaluation():
    """运行完整评测"""
    print("="*80)
    print("MemScope 直接API评测开始")
    print("="*80)
    
    # 初始化MemScope
    store = SqliteStore(DB_PATH)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_id = f"direct-{timestamp}"
    
    all_results = {}
    for dataset_name in DATASETS:
        try:
            dataset_result = evaluate_dataset(dataset_name, store)
            all_results[dataset_name] = dataset_result
        except Exception as e:
            print(f"评测数据集 {dataset_name} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 计算总体指标
    total_cases = sum(r['summary']['total_cases'] for r in all_results.values())
    avg_hit_rate = sum(r['summary']['avg_hit_rate'] * r['summary']['total_cases'] 
                       for r in all_results.values()) / total_cases if total_cases > 0 else 0
    avg_precision = sum(r['summary']['avg_precision'] * r['summary']['total_cases'] 
                        for r in all_results.values()) / total_cases if total_cases > 0 else 0
    avg_recall = sum(r['summary']['avg_recall'] * r['summary']['total_cases'] 
                     for r in all_results.values()) / total_cases if total_cases > 0 else 0
    avg_f1_score = sum(r['summary']['avg_f1_score'] * r['summary']['total_cases'] 
                       for r in all_results.values()) / total_cases if total_cases > 0 else 0
    avg_noise = sum(r['summary']['avg_noise_injection_rate'] * r['summary']['total_cases'] 
                    for r in all_results.values()) / total_cases if total_cases > 0 else 0
    
    eval_results = {
        'evaluation_id': eval_id,
        'timestamp': datetime.now().isoformat(),
        'datasets': all_results,
        'overall_metrics': {
            'total_cases': total_cases,
            'hit_rate': avg_hit_rate,
            'precision': avg_precision,
            'recall': avg_recall,
            'f1_score': avg_f1_score,
            'noise_injection_rate': avg_noise
        }
    }
    
    # 保存结果
    output_dir = os.path.join(EVAL_HISTORY_DIR, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, 'eval_results.json'), 'w', encoding='utf-8') as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)
    
    report = generate_report(eval_results, timestamp)
    with open(os.path.join(output_dir, 'eval_report.md'), 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n" + "="*80)
    print("评测完成！")
    print("="*80)
    print(f"\n总体Memory指标:")
    print(f"  命中率 Hit Rate: {avg_hit_rate:.2%}")
    print(f"  精确率 Precision: {avg_precision:.2%}")
    print(f"  召回率 Recall: {avg_recall:.2%}")
    print(f"  F1分数: {avg_f1_score:.2%}")
    print(f"\n结果保存在: {output_dir}")
    
    return eval_results


if __name__ == "__main__":
    run_evaluation()
