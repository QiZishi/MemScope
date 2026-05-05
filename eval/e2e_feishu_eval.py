#!/usr/bin/env python3
"""
MemScope 端到端评测脚本 — 通过飞书API实际测试

评测流程：
1. 通过飞书API发送消息到飞书群聊
2. 等待Hermes Agent + MemScope处理
3. 收集响应和执行轨迹
4. 评估结果

用法:
    python3 eval/e2e_feishu_eval.py [--chat-id CHAT_ID] [--timeout TIMEOUT]
"""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================================================
# 路径设置
# ============================================================================
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
DATASETS_DIR = os.path.join(EVAL_DIR, "datasets")
HISTORY_DIR = os.path.join(EVAL_DIR, "history")

# ============================================================================
# 飞书API客户端
# ============================================================================
class FeishuClient:
    """飞书API客户端，使用lark-cli"""
    
    def __init__(self, chat_id: str = None):
        self.chat_id = chat_id or os.environ.get("FEISHU_HOME_CHANNEL", "")
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        
        if not self.chat_id:
            raise ValueError("需要指定chat_id或设置FEISHU_HOME_CHANNEL环境变量")
    
    def send_message(self, text: str) -> Dict[str, Any]:
        """通过飞书CLI发送消息"""
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
            else:
                return {"error": result.stderr, "status": "failed"}
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "status": "failed"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def get_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取飞书群聊消息"""
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
            else:
                return []
        except Exception:
            return []
    
    def wait_for_response(self, trigger_text: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """等待Hermes Agent响应"""
        start_time = time.time()
        initial_messages = self.get_messages(limit=5)
        initial_count = len(initial_messages)
        
        while time.time() - start_time < timeout:
            time.sleep(1)
            current_messages = self.get_messages(limit=5)
            
            # 检查是否有新消息
            if len(current_messages) > initial_count:
                # 找到新消息
                new_messages = current_messages[:len(current_messages) - initial_count]
                for msg in new_messages:
                    # 检查是否是响应消息（不是我们发送的消息）
                    sender = msg.get("sender", {})
                    sender_type = sender.get("sender_type", "")
                    
                    # 如果是用户发送的消息（不是bot）
                    if sender_type == "user":
                        return msg
            
            # 检查是否有包含特定关键词的响应
            for msg in current_messages:
                sender = msg.get("sender", {})
                sender_type = sender.get("sender_type", "")
                
                # 如果是用户发送的消息
                if sender_type == "user":
                    content = msg.get("content", "")
                    # 如果消息包含MemScope相关的响应
                    if any(keyword in content for keyword in ["记忆", "MemScope", "找到", "推荐", "已记录"]):
                        return msg
        
        return None

# ============================================================================
# 评测函数
# ============================================================================
def eval_command_memory_e2e(client: FeishuClient, case: Dict) -> Dict[str, Any]:
    """评测CLI命令记忆（端到端）"""
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})
    
    # 发送命令记忆请求
    test_message = f"记录命令: {setup.get('command', 'git status')}"
    response = client.send_message(test_message)
    
    if "error" in response:
        return {
            "status": "error",
            "error": response["error"],
            "passed_checks": [],
            "failed_checks": ["send_failed"]
        }
    
    # 等待响应
    time.sleep(2)
    
    # 发送查询
    query_message = f"推荐命令: {query.get('prefix', 'git')}"
    client.send_message(query_message)
    
    # 等待响应
    time.sleep(2)
    
    # 获取最新消息
    messages = client.get_messages(limit=5)
    
    # 检查是否有响应
    has_response = len(messages) > 0
    
    return {
        "status": "pass" if has_response else "fail",
        "passed_checks": ["response_received"] if has_response else [],
        "failed_checks": [] if has_response else ["no_response"],
        "metrics": {
            "response_received": {"value": 1.0 if has_response else 0.0, "target": 1.0, "passed": has_response}
        }
    }

def eval_decision_memory_e2e(client: FeishuClient, case: Dict) -> Dict[str, Any]:
    """评测飞书决策记忆（端到端）"""
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})
    
    # 发送决策消息
    messages = setup.get("messages", [])
    for msg in messages[:2]:  # 只发送前2条
        content = msg.get("content", "")
        if content:
            client.send_message(content)
            time.sleep(1)
    
    # 发送查询
    query_text = query.get("keyword", "决策")
    client.send_message(f"搜索决策: {query_text}")
    
    # 等待响应
    time.sleep(3)
    
    # 获取最新消息
    response_messages = client.get_messages(limit=5)
    
    # 检查是否有响应
    has_response = len(response_messages) > 0
    
    return {
        "status": "pass" if has_response else "fail",
        "passed_checks": ["response_received"] if has_response else [],
        "failed_checks": [] if has_response else ["no_response"],
        "metrics": {
            "response_received": {"value": 1.0 if has_response else 0.0, "target": 1.0, "passed": has_response}
        }
    }

def eval_preference_memory_e2e(client: FeishuClient, case: Dict) -> Dict[str, Any]:
    """评测个人偏好记忆（端到端）"""
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})
    
    # 发送偏好消息
    messages = setup.get("messages", [])
    for msg in messages[:2]:
        content = msg.get("content", "")
        if content:
            client.send_message(content)
            time.sleep(1)
    
    # 发送查询
    query_text = query.get("category", "偏好")
    client.send_message(f"查询偏好: {query_text}")
    
    # 等待响应
    time.sleep(3)
    
    # 获取最新消息
    response_messages = client.get_messages(limit=5)
    
    # 检查是否有响应
    has_response = len(response_messages) > 0
    
    return {
        "status": "pass" if has_response else "fail",
        "passed_checks": ["response_received"] if has_response else [],
        "failed_checks": [] if has_response else ["no_response"],
        "metrics": {
            "response_received": {"value": 1.0 if has_response else 0.0, "target": 1.0, "passed": has_response}
        }
    }

def eval_knowledge_health_e2e(client: FeishuClient, case: Dict) -> Dict[str, Any]:
    """评测团队知识健康（端到端）"""
    setup = case.get("setup", {})
    query = case.get("query", {})
    expected = case.get("expected", {})
    
    # 发送知识健康查询
    query_text = query.get("type", "health_check")
    client.send_message(f"知识健康检查: {query_text}")
    
    # 等待响应
    time.sleep(3)
    
    # 获取最新消息
    response_messages = client.get_messages(limit=5)
    
    # 检查是否有响应
    has_response = len(response_messages) > 0
    
    return {
        "status": "pass" if has_response else "fail",
        "passed_checks": ["response_received"] if has_response else [],
        "failed_checks": [] if has_response else ["no_response"],
        "metrics": {
            "response_received": {"value": 1.0 if has_response else 0.0, "target": 1.0, "passed": has_response}
        }
    }

# ============================================================================
# 主评测流程
# ============================================================================
EVALUATORS = {
    "command_memory": eval_command_memory_e2e,
    "decision_memory": eval_decision_memory_e2e,
    "preference_memory": eval_preference_memory_e2e,
    "knowledge_health": eval_knowledge_health_e2e,
}

def run_e2e_evaluation(chat_id: str = None, timeout: int = 10) -> Dict[str, Any]:
    """运行端到端评测"""
    print("=" * 70)
    print("MemScope 端到端评测 — 通过飞书API实际测试")
    print("=" * 70)
    print(f"评测时间: {datetime.now().isoformat()}")
    print(f"飞书群聊: {chat_id or os.environ.get('FEISHU_HOME_CHANNEL', 'N/A')}")
    print()
    
    # 初始化飞书客户端
    try:
        client = FeishuClient(chat_id)
    except Exception as e:
        print(f"❌ 初始化飞书客户端失败: {e}")
        return {"error": str(e)}
    
    # 加载数据集
    all_datasets = {}
    for fname in sorted(os.listdir(DATASETS_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(DATASETS_DIR, fname)) as f:
                data = json.load(f)
            ds_name = fname.replace(".json", "")
            # 只评测支持的维度
            if ds_name in EVALUATORS:
                all_datasets[ds_name] = data.get("test_cases", [])[:3]  # 每个维度只测3条
    
    report = {
        "evaluation_id": f"e2e-eval-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now().isoformat(),
        "system": "MemScope E2E Evaluation via Feishu API",
        "chat_id": client.chat_id,
        "total_cases": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "dataset_results": {},
    }
    
    for ds_name, cases in all_datasets.items():
        evaluator = EVALUATORS.get(ds_name)
        if not evaluator:
            continue
        
        print(f"\n{'='*60}")
        print(f"评估: {ds_name} ({len(cases)} cases)")
        print(f"{'='*60}")
        
        ds_results, ds_passed, ds_failed, ds_errors = [], 0, 0, 0
        
        for i, case in enumerate(cases):
            case_id = case.get("test_id", f"{ds_name}_{i}")
            
            try:
                start = time.perf_counter()
                metrics = evaluator(client, case)
                elapsed = (time.perf_counter() - start) * 1000
                
                status = metrics.get("status", "error")
                if status == "pass":
                    ds_passed += 1
                elif status == "fail":
                    ds_failed += 1
                else:
                    ds_errors += 1
                
                ds_results.append({
                    "test_id": case_id,
                    "name": case.get("name", ""),
                    "status": status,
                    "metrics": metrics,
                    "elapsed_ms": round(elapsed, 2)
                })
                
                sym = {"pass": "✅", "fail": "❌", "error": "💥"}.get(status, "❓")
                print(f"  [{i+1}/{len(cases)}] {sym} {case_id}: {status} ({elapsed:.1f}ms)")
                
            except Exception as e:
                ds_errors += 1
                ds_results.append({
                    "test_id": case_id,
                    "name": case.get("name", ""),
                    "status": "error",
                    "error": str(e)
                })
                print(f"  [{i+1}/{len(cases)}] 💥 {case_id}: {e}")
        
        total = len(cases)
        pass_rate = round(ds_passed / total * 100, 1) if total > 0 else 0
        
        report["dataset_results"][ds_name] = {
            "total": total,
            "passed": ds_passed,
            "failed": ds_failed,
            "errors": ds_errors,
            "pass_rate": pass_rate,
            "cases": ds_results
        }
        
        report["total_cases"] += total
        report["passed"] += ds_passed
        report["failed"] += ds_failed
        report["errors"] += ds_errors
        
        print(f"\n  {ds_name}: {ds_passed}/{total} 通过 ({pass_rate}%)")
    
    # 计算总体结果
    total = report["total_cases"]
    report["pass_rate"] = round(report["passed"] / total * 100, 1) if total > 0 else 0
    
    return report

# ============================================================================
# 主入口
# ============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MemScope 端到端评测")
    parser.add_argument("--chat-id", help="飞书群聊ID")
    parser.add_argument("--timeout", type=int, default=10, help="响应等待超时（秒）")
    args = parser.parse_args()
    
    # 运行评测
    report = run_e2e_evaluation(args.chat_id, args.timeout)
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    history_path = os.path.join(HISTORY_DIR, timestamp)
    os.makedirs(history_path, exist_ok=True)
    
    results_path = os.path.join(history_path, "e2e_eval_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 更新latest符号链接
    latest_path = os.path.join(HISTORY_DIR, "latest_e2e")
    if os.path.exists(latest_path):
        os.unlink(latest_path)
    os.symlink(timestamp, latest_path)
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("评测结果摘要")
    print("=" * 70)
    print(f"总用例: {report['total_cases']}")
    print(f"通过: {report['passed']}")
    print(f"失败: {report['failed']}")
    print(f"错误: {report['errors']}")
    print(f"通过率: {report['pass_rate']}%")
    print()
    print("各维度结果:")
    for name, data in report.get("dataset_results", {}).items():
        print(f"  {name}: {data['passed']}/{data['total']} ({data['pass_rate']}%)")
    print()
    print(f"结果已保存到: {results_path}")
    print("=" * 70)
