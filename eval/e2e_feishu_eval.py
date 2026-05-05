#!/usr/bin/env python3
"""
MemScope 端到端评测脚本 — 通过飞书API在memscope评估群做真实评测

评测逻辑：
- 不使用"通过/失败/错误"这种代码测试逻辑
- 计算真正的memory架构指标：命中率、召回率、F1分数、精确率
- 在飞书memscope评估群做真实评测

用法:
    python3 eval/e2e_feishu_eval.py [--chat-id CHAT_ID] [--rounds ROUNDS]
"""

import json
import os
import subprocess
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
DATASETS_DIR = os.path.join(EVAL_DIR, "datasets")
HISTORY_DIR = os.path.join(EVAL_DIR, "history")

# ============================================================================
# 飞书API客户端
# ============================================================================
class FeishuClient:
    """飞书API客户端"""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
    
    def send_message(self, text: str) -> Dict[str, Any]:
        """发送消息到飞书群聊"""
        cmd = [
            "lark-cli", "im", "+messages-send",
            "--chat-id", self.chat_id,
            "--text", text,
            "--as", "bot"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    def get_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取群聊消息"""
        cmd = [
            "lark-cli", "im", "+chat-messages-list",
            "--chat-id", self.chat_id,
            "--page-size", str(limit)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("data", {}).get("messages", [])
            return []
        except Exception:
            return []
    
    def wait_for_bot_response(self, timeout: int = 15) -> Optional[str]:
        """等待bot响应"""
        start_time = time.time()
        initial_messages = self.get_messages(limit=3)
        initial_ids = {msg.get("message_id") for msg in initial_messages}
        
        while time.time() - start_time < timeout:
            time.sleep(2)
            current_messages = self.get_messages(limit=5)
            
            for msg in current_messages:
                msg_id = msg.get("message_id")
                sender = msg.get("sender", {})
                sender_type = sender.get("sender_type", "")
                
                # 找到新的bot响应
                if msg_id not in initial_ids and sender_type == "app":
                    return msg.get("content", "")
        
        return None

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
# 飞书业务场景数据集
# ============================================================================
FEISHU_BUSINESS_DATASETS = {
    "decision_memory": [
        {
            "test_id": "feishu_dec_001",
            "name": "技术选型决策",
            "category": "技术决策",
            "setup_messages": [
                "大家讨论一下前端框架，React还是Vue？",
                "我建议React，生态更成熟，TypeScript支持好",
                "同意，我们决定用React，团队也更熟悉"
            ],
            "query": "前端框架选型",
            "expected_keywords": ["React", "前端", "框架"],
            "forbidden_keywords": ["Vue", "Angular"],
            "description": "测试从飞书群聊中提取技术选型决策的能力"
        },
        {
            "test_id": "feishu_dec_002",
            "name": "部署方案决策",
            "category": "部署决策",
            "setup_messages": [
                "部署方案大家有什么建议？",
                "我建议用Docker + K8s，标准化部署",
                "同意，我们确认用Docker容器化部署"
            ],
            "query": "部署方案",
            "expected_keywords": ["Docker", "K8s", "容器化"],
            "forbidden_keywords": ["裸机", "虚拟机"],
            "description": "测试从飞书群聊中提取部署方案决策的能力"
        },
        {
            "test_id": "feishu_dec_003",
            "name": "数据库选型决策",
            "category": "数据库决策",
            "setup_messages": [
                "数据库选型，PostgreSQL还是MySQL？",
                "PostgreSQL，JSON支持更好，适合我们的场景",
                "最终决定用PostgreSQL"
            ],
            "query": "数据库选型",
            "expected_keywords": ["PostgreSQL", "JSON"],
            "forbidden_keywords": ["MySQL", "MongoDB"],
            "description": "测试从飞书群聊中提取数据库选型决策的能力"
        }
    ],
    "preference_memory": [
        {
            "test_id": "feishu_pref_001",
            "name": "编辑器偏好",
            "category": "工具偏好",
            "setup_messages": [
                "我更喜欢用vim写代码，效率高",
                "我习惯用VSCode，插件生态好"
            ],
            "query": "编辑器偏好",
            "expected_keywords": ["vim", "VSCode"],
            "forbidden_keywords": ["Emacs", "Sublime"],
            "description": "测试从飞书群聊中提取编辑器偏好的能力"
        },
        {
            "test_id": "feishu_pref_002",
            "name": "工作时间偏好",
            "category": "时间偏好",
            "setup_messages": [
                "我一般早上9点到12点效率最高",
                "这段时间不要安排会议"
            ],
            "query": "工作时间偏好",
            "expected_keywords": ["9点", "12点", "效率"],
            "forbidden_keywords": ["下午", "晚上"],
            "description": "测试从飞书群聊中提取工作时间偏好的能力"
        },
        {
            "test_id": "feishu_pref_003",
            "name": "编码风格偏好",
            "category": "风格偏好",
            "setup_messages": [
                "我通常先写测试再写代码，TDD风格",
                "代码格式化我偏好Tab缩进"
            ],
            "query": "编码风格偏好",
            "expected_keywords": ["TDD", "Tab", "测试"],
            "forbidden_keywords": ["Space", "不用测试"],
            "description": "测试从飞书群聊中提取编码风格偏好的能力"
        }
    ],
    "knowledge_health": [
        {
            "test_id": "feishu_kh_001",
            "name": "API设计规范",
            "category": "技术规范",
            "setup_messages": [
                "API设计规范文档已经写好了",
                "RESTful风格，统一返回格式",
                "错误码规范也定义好了"
            ],
            "query": "API设计规范",
            "expected_keywords": ["RESTful", "返回格式", "错误码"],
            "forbidden_keywords": ["GraphQL", "SOAP"],
            "description": "测试团队知识健康检测API规范的能力"
        },
        {
            "test_id": "feishu_kh_002",
            "name": "安全审计流程",
            "category": "流程规范",
            "setup_messages": [
                "安全审计流程需要大家了解",
                "每月进行一次代码安全扫描",
                "发现漏洞必须在24小时内修复"
            ],
            "query": "安全审计流程",
            "expected_keywords": ["安全审计", "漏洞", "24小时"],
            "forbidden_keywords": ["忽略", "延期"],
            "description": "测试团队知识健康检测安全流程的能力"
        },
        {
            "test_id": "feishu_kh_003",
            "name": "CI/CD流水线",
            "category": "DevOps",
            "setup_messages": [
                "CI/CD流水线配置完成",
                "每次push自动运行测试",
                "部署到staging环境需要手动触发"
            ],
            "query": "CI/CD流水线",
            "expected_keywords": ["CI/CD", "测试", "staging"],
            "forbidden_keywords": ["手动部署", "跳过测试"],
            "description": "测试团队知识健康检测CI/CD流程的能力"
        }
    ]
}

# ============================================================================
# 端到端评测执行器
# ============================================================================
class E2EEvaluator:
    """端到端评测执行器"""
    
    def __init__(self, chat_id: str):
        self.client = FeishuClient(chat_id)
        self.metrics = MemoryMetrics()
        self.results = []
    
    def run_evaluation(self, datasets: Dict = None) -> Dict[str, Any]:
        """运行端到端评测"""
        if datasets is None:
            datasets = FEISHU_BUSINESS_DATASETS
        
        print("=" * 70)
        print("MemScope 端到端评测 — 飞书业务场景")
        print("=" * 70)
        print(f"评测时间: {datetime.now().isoformat()}")
        print(f"评测群聊: {self.client.chat_id}")
        print()
        
        all_results = {}
        
        for dimension, test_cases in datasets.items():
            print(f"\n{'='*60}")
            print(f"评测维度: {dimension}")
            print(f"{'='*60}")
            
            dimension_results = []
            
            for i, case in enumerate(test_cases):
                print(f"\n  [{i+1}/{len(test_cases)}] {case['name']}")
                
                # 执行单个测试用例
                result = self._run_single_test(case)
                dimension_results.append(result)
                
                # 打印结果
                print(f"    命中率: {result['hit_rate']:.2%}")
                print(f"    精确率: {result['precision']:.2%}")
                print(f"    召回率: {result['recall']:.2%}")
                print(f"    F1分数: {result['f1_score']:.2%}")
                print(f"    噪声注入率: {result['noise_injection_rate']:.2%}")
            
            # 计算维度汇总
            dimension_summary = self._calculate_dimension_summary(dimension_results)
            all_results[dimension] = {
                "test_cases": dimension_results,
                "summary": dimension_summary
            }
            
            print(f"\n  维度汇总:")
            print(f"    平均命中率: {dimension_summary['avg_hit_rate']:.2%}")
            print(f"    平均精确率: {dimension_summary['avg_precision']:.2%}")
            print(f"    平均召回率: {dimension_summary['avg_recall']:.2%}")
            print(f"    平均F1分数: {dimension_summary['avg_f1_score']:.2%}")
        
        # 计算总体汇总
        overall_summary = self._calculate_overall_summary(all_results)
        
        return {
            "evaluation_id": f"e2e-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().isoformat(),
            "chat_id": self.client.chat_id,
            "dimensions": all_results,
            "overall": overall_summary
        }
    
    def _run_single_test(self, case: Dict) -> Dict[str, Any]:
        """执行单个测试用例"""
        start_time = time.time()
        
        # 1. 发送setup消息
        for msg in case.get("setup_messages", []):
            self.client.send_message(msg)
            time.sleep(1)
        
        # 2. 发送查询
        query = case.get("query", "")
        self.client.send_message(f"查询记忆: {query}")
        
        # 3. 等待响应
        response = self.client.wait_for_bot_response(timeout=15)
        elapsed_ms = (time.time() - start_time) * 1000
        
        # 4. 计算指标
        expected_keywords = case.get("expected_keywords", [])
        forbidden_keywords = case.get("forbidden_keywords", [])
        actual_content = response or ""
        
        hit_rate = self.metrics.calculate_hit_rate(expected_keywords, actual_content)
        precision = self.metrics.calculate_precision(expected_keywords, forbidden_keywords, actual_content)
        recall = self.metrics.calculate_recall(expected_keywords, actual_content)
        f1_score = self.metrics.calculate_f1(precision, recall)
        noise_injection_rate = self.metrics.calculate_noise_injection_rate(forbidden_keywords, actual_content)
        
        return {
            "test_id": case["test_id"],
            "name": case["name"],
            "category": case.get("category", ""),
            "query": query,
            "response": actual_content[:500],  # 截取前500字符
            "expected_keywords": expected_keywords,
            "forbidden_keywords": forbidden_keywords,
            "hit_rate": round(hit_rate, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "noise_injection_rate": round(noise_injection_rate, 4),
            "latency_ms": round(elapsed_ms, 2),
            "has_response": response is not None
        }
    
    def _calculate_dimension_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """计算维度汇总"""
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
            "response_rate": sum(1 for r in results if r["has_response"]) / len(results)
        }
    
    def _calculate_overall_summary(self, all_results: Dict) -> Dict[str, Any]:
        """计算总体汇总"""
        all_summaries = [dim["summary"] for dim in all_results.values() if "summary" in dim]
        
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
            "overall_response_rate": sum(s["response_rate"] * s["total_cases"] for s in all_summaries) / total_cases
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
        "chat_id": report["chat_id"],
        "overall": report.get("overall", {}),
        "dimensions": {
            name: dim.get("summary", {})
            for name, dim in report.get("dimensions", {}).items()
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
        f"**评测群聊**: {report.get('chat_id', 'N/A')}",
        f"**评测ID**: {report.get('evaluation_id', 'N/A')}",
        "",
        "## 总体指标",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 总测试用例 | {overall.get('total_cases', 0)} |",
        f"| **命中率 Hit Rate** | **{overall.get('overall_hit_rate', 0):.2%}** |",
        f"| **精确率 Precision** | **{overall.get('overall_precision', 0):.2%}** |",
        f"| **召回率 Recall** | **{overall.get('overall_recall', 0):.2%}** |",
        f"| **F1分数** | **{overall.get('overall_f1_score', 0):.2%}** |",
        f"| 噪声注入率 | {overall.get('overall_noise_injection_rate', 0):.2%} |",
        f"| 平均响应时间 | {overall.get('overall_latency_ms', 0):.0f}ms |",
        f"| 响应率 | {overall.get('overall_response_rate', 0):.2%} |",
        "",
        "## 各维度指标",
        "",
        "| 维度 | 命中率 | 精确率 | 召回率 | F1分数 | 噪声注入率 |",
        "|------|--------|--------|--------|--------|------------|",
    ]
    
    for name, dim in report.get("dimensions", {}).items():
        summary = dim.get("summary", {})
        lines.append(
            f"| {name} | {summary.get('avg_hit_rate', 0):.2%} | "
            f"{summary.get('avg_precision', 0):.2%} | "
            f"{summary.get('avg_recall', 0):.2%} | "
            f"{summary.get('avg_f1_score', 0):.2%} | "
            f"{summary.get('avg_noise_injection_rate', 0):.2%} |"
        )
    
    lines.extend([
        "",
        "## 详细测试结果",
        ""
    ])
    
    for name, dim in report.get("dimensions", {}).items():
        lines.append(f"### {name}")
        lines.append("")
        
        for case in dim.get("test_cases", []):
            lines.append(f"#### {case['name']}")
            lines.append("")
            lines.append(f"- **查询**: {case['query']}")
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
    import argparse
    
    parser = argparse.ArgumentParser(description="MemScope 端到端评测")
    parser.add_argument("--chat-id", default="oc_ca5b7423a6cb1cb704cf46876c71aeed",
                       help="飞书群聊ID（默认: memscope评估群）")
    args = parser.parse_args()
    
    # 运行评测
    evaluator = E2EEvaluator(args.chat_id)
    report = evaluator.run_evaluation()
    
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
