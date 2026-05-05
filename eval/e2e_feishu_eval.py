#!/usr/bin/env python3
"""
MemScope 端到端评测脚本 — 直接调用MemScope API测试

评测逻辑：
- 每个样本包含chunk（记忆内容）、query（查询）、answer（期望答案）
- 直接调用MemScope API存储chunk并查询
- 计算真正的memory指标：命中率、精确率、召回率、F1分数

用法:
    python3 eval/e2e_feishu_eval.py
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# 路径设置
# ============================================================================
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
DATASETS_DIR = os.path.join(EVAL_DIR, "datasets")
HISTORY_DIR = os.path.join(EVAL_DIR, "history")

# 添加src到路径
sys.path.insert(0, SRC_DIR)

# ============================================================================
# Memory指标计算
# ============================================================================
class MemoryMetrics:
    """Memory架构评测指标计算"""
    
    @staticmethod
    def calculate_hit_rate(expected_keywords: List[str], actual_content: str) -> float:
        """
        命中率：搜索结果中包含目标信息的比例
        Hit Rate = 命中关键词数 / 总期望关键词数
        """
        if not expected_keywords:
            return 1.0
        
        actual_lower = actual_content.lower()
        hits = sum(1 for kw in expected_keywords if kw.lower() in actual_lower)
        return hits / len(expected_keywords)
    
    @staticmethod
    def calculate_precision(expected_keywords: List[str], forbidden_keywords: List[str], actual_content: str) -> float:
        """
        精确率：搜索结果中正确信息的比例
        Precision = 正确信息数 / 总返回信息数
        """
        actual_lower = actual_content.lower()
        
        # 计算期望关键词命中数
        expected_hits = sum(1 for kw in expected_keywords if kw.lower() in actual_lower)
        
        # 计算禁止关键词命中数（噪声）
        forbidden_hits = sum(1 for kw in forbidden_keywords if kw.lower() in actual_lower)
        
        # 精确率 = 期望命中 / (期望命中 + 噪声命中)
        total_hits = expected_hits + forbidden_hits
        if total_hits == 0:
            return 0.0
        
        return expected_hits / total_hits
    
    @staticmethod
    def calculate_recall(expected_keywords: List[str], actual_content: str) -> float:
        """
        召回率：目标信息被检索到的比例
        Recall = 正确召回的目标字段数 / 总目标字段数
        """
        return MemoryMetrics.calculate_hit_rate(expected_keywords, actual_content)
    
    @staticmethod
    def calculate_f1(precision: float, recall: float) -> float:
        """
        F1分数：精确率和召回率的调和平均
        F1 = 2 * Precision * Recall / (Precision + Recall)
        """
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)
    
    @staticmethod
    def calculate_noise_injection_rate(forbidden_keywords: List[str], actual_content: str) -> float:
        """
        噪声注入率：搜索结果中噪声信息的比例
        Noise Injection Rate = 噪声关键词命中数 / 总关键词数
        """
        if not forbidden_keywords:
            return 0.0
        
        actual_lower = actual_content.lower()
        noise_hits = sum(1 for kw in forbidden_keywords if kw.lower() in actual_lower)
        return noise_hits / len(forbidden_keywords)

# ============================================================================
# 评测数据集加载
# ============================================================================
def load_datasets(datasets_dir: str) -> Dict[str, List[Dict]]:
    """加载所有评测数据集"""
    datasets = {}
    
    for filename in os.listdir(datasets_dir):
        if filename.endswith(".json") and filename.startswith("feishu_"):
            filepath = os.path.join(datasets_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            dataset_name = data.get("dataset_name", filename.replace(".json", ""))
            test_cases = data.get("test_cases", [])
            datasets[dataset_name] = test_cases
    
    return datasets

# ============================================================================
# MemScope API调用
# ============================================================================
class MemScopeAPI:
    """MemScope API调用"""
    
    def __init__(self):
        self.store = None
        self._initialize()
    
    def _initialize(self):
        """初始化MemScope"""
        try:
            from core.store import SqliteStore
            
            # 创建临时数据库
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = tmp.name
            tmp.close()
            
            self.store = SqliteStore(db_path)
            print("MemScope 初始化成功")
        except Exception as e:
            print(f"MemScope 初始化失败: {e}")
            raise
    
    def store_chunk(self, content: str, session_key: str = "eval") -> str:
        """存储chunk"""
        chunk_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        
        self.store.insert_chunk({
            "id": chunk_id,
            "sessionKey": session_key,
            "turnId": str(now),
            "seq": 0,
            "role": "assistant",
            "content": content,
            "owner": "eval_user",
            "createdAt": now,
            "updatedAt": now
        })
        
        return chunk_id
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        results = self.store.search_chunks(query, max_results=max_results)
        return results

# ============================================================================
# 端到端评测执行器
# ============================================================================
class E2EEvaluator:
    """端到端评测执行器"""
    
    def __init__(self):
        self.api = MemScopeAPI()
        self.metrics = MemoryMetrics()
    
    def run_evaluation(self, datasets: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """运行端到端评测"""
        print("=" * 70)
        print("MemScope 端到端评测 — 直接调用API测试")
        print("=" * 70)
        print(f"评测时间: {datetime.now().isoformat()}")
        print(f"数据集数量: {len(datasets)}")
        print()
        
        all_results = {}
        
        for dataset_name, test_cases in datasets.items():
            print(f"\n{'='*60}")
            print(f"数据集: {dataset_name} ({len(test_cases)} 条)")
            print(f"{'='*60}")
            
            dataset_results = []
            
            for i, case in enumerate(test_cases):
                print(f"\n  [{i+1}/{len(test_cases)}] {case['name']}")
                
                # 执行单个测试用例
                result = self._run_single_test(case)
                dataset_results.append(result)
                
                # 打印结果
                print(f"    命中率: {result['hit_rate']:.2%}")
                print(f"    精确率: {result['precision']:.2%}")
                print(f"    召回率: {result['recall']:.2%}")
                print(f"    F1分数: {result['f1_score']:.2%}")
            
            # 计算数据集汇总
            dataset_summary = self._calculate_dataset_summary(dataset_results)
            all_results[dataset_name] = {
                "test_cases": dataset_results,
                "summary": dataset_summary
            }
            
            print(f"\n  数据集汇总:")
            print(f"    平均命中率: {dataset_summary['avg_hit_rate']:.2%}")
            print(f"    平均精确率: {dataset_summary['avg_precision']:.2%}")
            print(f"    平均召回率: {dataset_summary['avg_recall']:.2%}")
            print(f"    平均F1分数: {dataset_summary['avg_f1_score']:.2%}")
        
        # 计算总体汇总
        overall_summary = self._calculate_overall_summary(all_results)
        
        return {
            "evaluation_id": f"e2e-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().isoformat(),
            "datasets": all_results,
            "overall": overall_summary
        }
    
    def _run_single_test(self, case: Dict) -> Dict[str, Any]:
        """执行单个测试用例"""
        start_time = time.time()
        
        # 1. 存储chunk
        chunk = case.get("chunk", "")
        self.api.store_chunk(chunk)
        
        # 2. 查询
        query = case.get("query", "")
        results = self.api.search(query, max_results=5)
        
        # 3. 合并搜索结果
        actual_content = " ".join(r.get("content", "") for r in results)
        elapsed_ms = (time.time() - start_time) * 1000
        
        # 4. 计算指标
        expected_keywords = case.get("expected_keywords", [])
        forbidden_keywords = case.get("forbidden_keywords", [])
        
        hit_rate = self.metrics.calculate_hit_rate(expected_keywords, actual_content)
        precision = self.metrics.calculate_precision(expected_keywords, forbidden_keywords, actual_content)
        recall = self.metrics.calculate_recall(expected_keywords, actual_content)
        f1_score = self.metrics.calculate_f1(precision, recall)
        noise_injection_rate = self.metrics.calculate_noise_injection_rate(forbidden_keywords, actual_content)
        
        return {
            "test_id": case["test_id"],
            "name": case["name"],
            "difficulty": case.get("difficulty", ""),
            "category": case.get("category", ""),
            "chunk": chunk[:200],  # 截取前200字符
            "query": query,
            "answer": case.get("answer", ""),
            "search_results": [r.get("content", "")[:100] for r in results[:3]],
            "expected_keywords": expected_keywords,
            "forbidden_keywords": forbidden_keywords,
            "hit_rate": round(hit_rate, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "noise_injection_rate": round(noise_injection_rate, 4),
            "latency_ms": round(elapsed_ms, 2),
            "results_count": len(results)
        }
    
    def _calculate_dataset_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """计算数据集汇总"""
        if not results:
            return {}
        
        return {
            "total_cases": len(results),
            "avg_hit_rate": sum(r["hit_rate"] for r in results) / len(results),
            "avg_precision": sum(r["precision"] for r in results) / len(results),
            "avg_recall": sum(r["recall"] for r in results) / len(results),
            "avg_f1_score": sum(r["f1_score"] for r in results) / len(results),
            "avg_noise_injection_rate": sum(r["noise_injection_rate"] for r in results) / len(results),
            "avg_latency_ms": sum(r["latency_ms"] for r in results) / len(results),
            "difficulty_distribution": {
                "easy": sum(1 for r in results if r["difficulty"] == "easy"),
                "medium": sum(1 for r in results if r["difficulty"] == "medium"),
                "hard": sum(1 for r in results if r["difficulty"] == "hard")
            }
        }
    
    def _calculate_overall_summary(self, all_results: Dict) -> Dict[str, Any]:
        """计算总体汇总"""
        all_summaries = [ds["summary"] for ds in all_results.values() if "summary" in ds]
        
        if not all_summaries:
            return {}
        
        total_cases = sum(s["total_cases"] for s in all_summaries)
        
        return {
            "total_cases": total_cases,
            "overall_hit_rate": sum(s["avg_hit_rate"] * s["total_cases"] for s in all_summaries) / total_cases,
            "overall_precision": sum(s["avg_precision"] * s["total_cases"] for s in all_summaries) / total_cases,
            "overall_recall": sum(s["avg_recall"] * s["total_cases"] for s in all_summaries) / total_cases,
            "overall_f1_score": sum(s["avg_f1_score"] * s["total_cases"] for s in all_summaries) / total_cases,
            "overall_noise_injection_rate": sum(s["avg_noise_injection_rate"] * s["total_cases"] for s in all_summaries) / total_cases,
            "overall_latency_ms": sum(s["avg_latency_ms"] * s["total_cases"] for s in all_summaries) / total_cases,
            "datasets_count": len(all_summaries)
        }

# ============================================================================
# 结果保存
# ============================================================================
def save_evaluation_results(report: Dict[str, Any], history_dir: str) -> str:
    """保存评测结果到历史目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_dir = os.path.join(history_dir, timestamp)
    os.makedirs(eval_dir, exist_ok=True)
    
    # 1. 保存完整评测结果JSON
    results_path = os.path.join(eval_dir, "eval_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 2. 生成评测报告Markdown
    report_path = os.path.join(eval_dir, "eval_report.md")
    generate_markdown_report(report, report_path)
    
    # 3. 保存指标摘要
    summary_path = os.path.join(eval_dir, "metrics_summary.json")
    summary = {
        "timestamp": report["timestamp"],
        "overall": report.get("overall", {}),
        "datasets": {
            name: ds.get("summary", {})
            for name, ds in report.get("datasets", {}).items()
        }
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 4. 更新latest符号链接
    latest_path = os.path.join(history_dir, "latest")
    if os.path.exists(latest_path):
        os.unlink(latest_path)
    os.symlink(timestamp, latest_path)
    
    return eval_dir

def generate_markdown_report(report: Dict[str, Any], output_path: str):
    """生成Markdown评测报告"""
    overall = report.get("overall", {})
    
    lines = [
        "# MemScope 端到端评测报告",
        "",
        f"**评测时间**: {report.get('timestamp', 'N/A')}",
        f"**评测ID**: {report.get('evaluation_id', 'N/A')}",
        "",
        "## 总体Memory指标",
        "",
        "| 指标 | 值 | 说明 |",
        "|------|-----|------|",
        f"| **命中率 Hit Rate** | **{overall.get('overall_hit_rate', 0):.2%}** | 搜索结果中包含目标信息的比例 |",
        f"| **精确率 Precision** | **{overall.get('overall_precision', 0):.2%}** | 搜索结果中正确信息的比例 |",
        f"| **召回率 Recall** | **{overall.get('overall_recall', 0):.2%}** | 目标信息被检索到的比例 |",
        f"| **F1分数** | **{overall.get('overall_f1_score', 0):.2%}** | 精确率和召回率的调和平均 |",
        f"| 噪声注入率 | {overall.get('overall_noise_injection_rate', 0):.2%} | 搜索结果中噪声信息的比例 |",
        f"| 平均响应时间 | {overall.get('overall_latency_ms', 0):.0f}ms | 平均响应延迟 |",
        f"| 总测试用例 | {overall.get('total_cases', 0)} | - |",
        "",
        "## 各数据集指标",
        "",
        "| 数据集 | 命中率 | 精确率 | 召回率 | F1分数 | 用例数 |",
        "|--------|--------|--------|--------|--------|--------|",
    ]
    
    for name, ds in report.get("datasets", {}).items():
        summary = ds.get("summary", {})
        lines.append(
            f"| {name} | {summary.get('avg_hit_rate', 0):.2%} | "
            f"{summary.get('avg_precision', 0):.2%} | "
            f"{summary.get('avg_recall', 0):.2%} | "
            f"{summary.get('avg_f1_score', 0):.2%} | "
            f"{summary.get('total_cases', 0)} |"
        )
    
    lines.extend([
        "",
        "## 详细测试结果",
        ""
    ])
    
    for name, ds in report.get("datasets", {}).items():
        lines.append(f"### {name}")
        lines.append("")
        
        for case in ds.get("test_cases", []):
            lines.append(f"#### {case['name']}")
            lines.append("")
            lines.append(f"- **难度**: {case.get('difficulty', 'N/A')}")
            lines.append(f"- **类别**: {case.get('category', 'N/A')}")
            lines.append(f"- **查询**: {case.get('query', 'N/A')}")
            lines.append(f"- **期望答案**: {case.get('answer', 'N/A')}")
            lines.append(f"- **命中率**: {case['hit_rate']:.2%}")
            lines.append(f"- **精确率**: {case['precision']:.2%}")
            lines.append(f"- **召回率**: {case['recall']:.2%}")
            lines.append(f"- **F1分数**: {case['f1_score']:.2%}")
            lines.append(f"- **响应时间**: {case['latency_ms']:.0f}ms")
            lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ============================================================================
# 主入口
# ============================================================================
if __name__ == "__main__":
    # 加载数据集
    datasets = load_datasets(DATASETS_DIR)
    print(f"加载了 {len(datasets)} 个数据集")
    for name, cases in datasets.items():
        print(f"  - {name}: {len(cases)} 条")
    
    # 运行评测
    evaluator = E2EEvaluator()
    report = evaluator.run_evaluation(datasets)
    
    # 保存结果
    eval_dir = save_evaluation_results(report, HISTORY_DIR)
    
    # 打印摘要
    overall = report.get("overall", {})
    print("\n" + "=" * 70)
    print("评测完成")
    print("=" * 70)
    print(f"命中率: {overall.get('overall_hit_rate', 0):.2%}")
    print(f"精确率: {overall.get('overall_precision', 0):.2%}")
    print(f"召回率: {overall.get('overall_recall', 0):.2%}")
    print(f"F1分数: {overall.get('overall_f1_score', 0):.2%}")
    print(f"\n结果已保存到: {eval_dir}")
    print("=" * 70)
