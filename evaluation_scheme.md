# 企业记忆引擎评估方案

> **文档版本**: v1.0  
> **创建日期**: 2026-04-28  
> **适用系统**: Hermes Agent + memos 插件  
> **竞赛要求**: 飞书 OpenClaw 大赛 — 方向 C（个人工作习惯/偏好）与方向 D（团队知识缺口/遗忘提醒）

---

## 目录

1. [总体框架](#1-总体框架)
2. [竞赛必测项](#2-竞赛必测项)
   - 2.1 抗干扰测试
   - 2.2 矛盾信息更新测试
   - 2.3 效率指标验证
3. [基线对比方案](#3-基线对比方案)
4. [方向 C 附加测试（个人工作习惯/偏好）](#4-方向-c-附加测试)
5. [方向 D 附加测试（团队知识缺口/遗忘提醒）](#5-方向-d-附加测试)
6. [参考基准与对标](#6-参考基准与对标)
7. [测试用例代码映射表](#7-测试用例代码映射表)
8. [附录：数据构造规范](#8-附录数据构造规范)

---

## 1. 总体框架

### 1.1 评估维度总览

| 维度 | 子维度 | 权重 | 数据来源 |
|------|--------|------|----------|
| 抗干扰能力 | 噪声过滤率、无关信息忽略率 | 25% | 对抗性测试集 |
| 矛盾更新能力 | 旧值覆盖率、新值采纳率、时间线正确率 | 25% | 矛盾测试集 |
| 效率指标 | 平均响应延迟、内存占用、Token消耗 | 20% | 性能监控 |
| 方向C - 个人偏好 | 偏好召回率、偏好更新准确性 | 15% | 个人工作场景 |
| 方向D - 团队知识 | 知识缺口检测率、遗忘提醒及时性 | 15% | 团队协作场景 |

### 1.2 评估流程

```
[构造测试数据] → [写入记忆系统] → [执行查询] → [计算指标] → [生成报告]
       ↓                  ↓              ↓             ↓
    数据集JSON       memos插件API    测试用例引擎    评分脚本     HTML/Markdown
```

### 1.3 评分标准

- **满分**: 100 分
- **竞赛及格线**: 70 分
- **优秀线**: 85 分
- 各维度加权计算总分

---

## 2. 竞赛必测项

### 2.1 抗干扰测试

**目标**: 验证记忆系统在大量无关对话干扰下，仍能准确召回目标信息。

#### 2.1.1 测试用例设计

**测试集结构**: 每个用例包含"目标对话"、"干扰对话序列"和"查询问题"

**用例 1.1 — 单轮干扰**
```json
{
  "test_id": "anti_interference_001",
  "category": "single_round_noise",
  "target_conversation": {
    "user": "我下周三要去客户A公司做技术方案汇报",
    "assistant": "好的，已记录。下周三（5月6日）客户A技术方案汇报。",
    "timestamp": "2026-05-01T10:00:00Z"
  },
  "noise_conversations": [
    {"user": "今天天气不错", "assistant": "是的，天气很好。", "timestamp": "2026-05-01T10:05:00Z"},
    {"user": "帮我订一杯拿铁咖啡", "assistant": "已为您下单。", "timestamp": "2026-05-01T10:10:00Z"},
    {"user": "最近有部新电影上映", "assistant": "是的，您可以看看评分。", "timestamp": "2026-05-01T10:15:00Z"},
    {"user": "明天要开会吗", "assistant": "您明天上午10点有周会。", "timestamp": "2026-05-01T10:20:00Z"}
  ],
  "query": "我下周有什么安排？",
  "expected_answer": "下周三去客户A公司做技术方案汇报",
  "expected_recall_fields": ["时间:下周三", "地点:客户A公司", "事件:技术方案汇报"],
  "evaluation_criteria": {
    "must_mention": ["客户A", "技术方案汇报", "下周三"],
    "must_not_mention": ["天气", "拿铁", "电影"]
  }
}
```

**用例 1.2 — 多轮连续干扰（20轮噪声后查询）**
```json
{
  "test_id": "anti_interference_002",
  "category": "multi_round_noise",
  "target_conversation": {
    "user": "项目B的预算已经批下来了，总共80万",
    "assistant": "收到，已记录项目B预算：80万元。",
    "timestamp": "2026-04-28T09:00:00Z"
  },
  "noise_conversations": [
    // ... 20轮无关对话，涵盖日常闲聊、天气、新闻、其他项目等
    // 每轮间隔1-3分钟
  ],
  "query": "项目B的预算是多少？",
  "expected_answer": "80万",
  "tolerance": {
    "numeric_deviation": 0,
    "allowed_variants": ["80万", "80万元", "八十万元"]
  }
}
```

**用例 1.3 — 高相似度干扰（同一项目不同信息）**
```json
{
  "test_id": "anti_interference_003",
  "category": "similar_topic_noise",
  "target_conversation": {
    "user": "项目C的技术负责人是张三",
    "assistant": "已记录，项目C技术负责人：张三。",
    "timestamp": "2026-04-28T09:00:00Z"
  },
  "noise_conversations": [
    {"user": "项目D的负责人是谁", "assistant": "项目D负责人是李四。", "timestamp": "2026-04-28T09:10:00Z"},
    {"user": "项目E的技术负责人是王五吗", "assistant": "是的，项目E技术负责人是王五。", "timestamp": "2026-04-28T09:20:00Z"},
    {"user": "项目F的测试负责人换成赵六了", "assistant": "已更新，项目F测试负责人：赵六。", "timestamp": "2026-04-28T09:30:00Z"}
  ],
  "query": "项目C的技术负责人是谁？",
  "expected_answer": "张三",
  "distractor_answers": ["李四", "王五", "赵六"]
}
```

**用例 1.4 — 时间跨度干扰**
```json
{
  "test_id": "anti_interference_004",
  "category": "temporal_spread_noise",
  "target_conversation": {
    "user": "我的飞书文档密码改成了 Herme$2026!",
    "assistant": "已安全记录（加密存储）。",
    "timestamp": "2026-01-15T14:00:00Z"
  },
  "noise_conversations": [
    // 从1月到4月，共30轮分散的无关对话
  ],
  "query": "我上次修改的飞书文档密码是什么？",
  "expected_answer": "Herme$2026!",
  "evaluation_criteria": {
    "must_retrieve": true,
    "security_note": "密码类信息应标注安全提醒"
  }
}
```

**用例 1.5 — 角色混淆干扰**
```json
{
  "test_id": "anti_interference_005",
  "category": "role_confusion_noise",
  "target_conversation": {
    "user": "我下周三去拜访客户A",
    "assistant": "好的，已记录。",
    "timestamp": "2026-05-01T10:00:00Z"
  },
  "noise_conversations": [
    {"user": "张三下周三也要去拜访客户A", "assistant": "已记录张三的行程。", "timestamp": "2026-05-01T10:05:00Z"},
    {"user": "李四下周三去客户B", "assistant": "已记录李四的行程。", "timestamp": "2026-05-01T10:10:00Z"}
  ],
  "query": "下周三谁去拜访客户A？",
  "expected_answer": "我（当前用户）去拜访客户A",
  "evaluation_criteria": {
    "must_distinguish_self": true,
    "must_not_confuse_with": ["张三"]
  }
}
```

#### 2.1.2 抗干扰指标

| 指标名 | 计算公式 | 目标值 |
|--------|----------|--------|
| **召回率 (Recall)** | 正确召回的目标字段数 / 总目标字段数 × 100% | ≥ 90% |
| **精确率 (Precision)** | 返回信息中正确字段数 / 返回总字段数 × 100% | ≥ 85% |
| **噪声引入率 (Noise Injection Rate)** | 返回信息中干扰项数量 / 返回总项数 × 100% | ≤ 5% |
| **F1-Score** | 2 × Precision × Recall / (Precision + Recall) | ≥ 87% |
| **角色区分准确率** | 正确区分用户自身与他人信息的用例数 / 总用例数 × 100% | ≥ 95% |

#### 2.1.3 测量方法

```python
# 抗干扰测试伪代码
def test_anti_interference(test_case: dict) -> dict:
    """
    输入: test_case 包含 target_conversation, noise_conversations, query, expected_answer
    输出: 测试结果字典
    """
    # Step 1: 写入目标对话到记忆系统
    memory_store.write(test_case["target_conversation"])
    
    # Step 2: 依次写入干扰对话
    for noise in test_case["noise_conversations"]:
        memory_store.write(noise)
    
    # Step 3: 执行查询
    result = memory_store.query(test_case["query"])
    
    # Step 4: 计算指标
    metrics = {
        "recall": calculate_recall(result, test_case["expected_recall_fields"]),
        "precision": calculate_precision(result, test_case["expected_recall_fields"]),
        "noise_injected": detect_noise(result, test_case["evaluation_criteria"]["must_not_mention"]),
        "response_latency_ms": result.latency_ms,
        "token_count": result.token_count
    }
    
    return metrics
```

---

### 2.2 矛盾信息更新测试

**目标**: 验证记忆系统在接收到矛盾信息时，能正确更新旧记忆、保留历史版本、按时间排序返回最新信息。

#### 2.2.1 测试用例设计

**用例 2.1 — 直接覆盖型矛盾**
```json
{
  "test_id": "contradiction_001",
  "category": "direct_override",
  "conversations": [
    {
      "user": "我的工位号是 A-305",
      "assistant": "已记录，工位号：A-305。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "我搬到新工位了，现在是 B-201",
      "assistant": "已更新，工位号：B-201。旧工位 A-305 已归档。",
      "timestamp": "2026-05-01T10:00:00Z"
    }
  ],
  "query": "我的工位号是多少？",
  "expected_answer": "B-201",
  "expected_old_value": "A-305",
  "evaluation_criteria": {
    "latest_value": "B-201",
    "history_preserved": true,
    "history_accessible_via_query": "之前/以前/旧的工位号"
  }
}
```

**用例 2.2 — 部分更新型矛盾**
```json
{
  "test_id": "contradiction_002",
  "category": "partial_update",
  "conversations": [
    {
      "user": "项目G的成员有张三、李四、王五",
      "assistant": "已记录项目G成员：张三、李四、王五。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "王五退出项目G了，赵六加入了",
      "assistant": "已更新，项目G成员变更为：张三、李四、赵六。",
      "timestamp": "2026-04-15T10:00:00Z"
    }
  ],
  "query": "项目G有哪些成员？",
  "expected_answer": ["张三", "李四", "赵六"],
  "must_not_include": ["王五"],
  "evaluation_criteria": {
    "correct_members": ["张三", "李四", "赵六"],
    "removed_members_not_in_latest": ["王五"],
    "can_query_history": true
  }
}
```

**用例 2.3 — 时间线矛盾（同一事实不同时间的表述）**
```json
{
  "test_id": "contradiction_003",
  "category": "temporal_contradiction",
  "conversations": [
    {
      "user": "每周二下午3点我们团队有周会",
      "assistant": "已记录：团队周会，每周二 15:00。",
      "timestamp": "2026-03-01T10:00:00Z"
    },
    {
      "user": "周会改到每周四上午10点了",
      "assistant": "已更新：团队周会改为每周四 10:00。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "周会又改回周二下午了，但是改到4点",
      "assistant": "已更新：团队周会改为每周二 16:00。",
      "timestamp": "2026-04-15T10:00:00Z"
    }
  ],
  "queries": [
    {
      "query": "我们团队周会是什么时候？",
      "expected_answer": "每周二 16:00",
      "description": "应返回最新时间"
    },
    {
      "query": "之前的周会是什么时候？",
      "expected_answer_contains": ["周二 15:00", "周四 10:00"],
      "description": "历史版本应可追溯"
    },
    {
      "query": "周会的时间改了几次？",
      "expected_answer": "改了2次（从周二15:00 → 周四10:00 → 周二16:00）"
    }
  ]
}
```

**用例 2.4 — 多实体并发矛盾**
```json
{
  "test_id": "contradiction_004",
  "category": "multi_entity_contradiction",
  "conversations": [
    {
      "user": "项目H预算50万，项目I预算30万",
      "assistant": "已记录：项目H预算50万，项目I预算30万。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "项目H的预算追加到70万了",
      "assistant": "已更新项目H预算为70万。项目I预算不变。",
      "timestamp": "2026-04-10T10:00:00Z"
    }
  ],
  "query": "项目H和项目I的预算分别是多少？",
  "expected_answer": "项目H：70万，项目I：30万",
  "evaluation_criteria": {
    "correct_h": "70万",
    "correct_i": "30万",
    "partial_update_preserved": true
  }
}
```

**用例 2.5 — 撤回/取消型矛盾**
```json
{
  "test_id": "contradiction_005",
  "category": "cancel_retraction",
  "conversations": [
    {
      "user": "帮我约下周一和客户A的会议",
      "assistant": "已记录，下周一与客户A的会议。",
      "timestamp": "2026-04-28T10:00:00Z"
    },
    {
      "user": "下周一和客户A的会议取消了",
      "assistant": "已取消该会议记录。",
      "timestamp": "2026-04-29T10:00:00Z"
    }
  ],
  "query": "我下周一有什么安排？",
  "expected_answer": "没有与客户A的会议安排（已取消）",
  "evaluation_criteria": {
    "cancelled_event_not_shown": true,
    "cancellation_reason_preserved": true
  }
}
```

#### 2.2.2 矛盾更新指标

| 指标名 | 计算公式 | 目标值 |
|--------|----------|--------|
| **最新值准确率 (Latest Accuracy)** | 最新值正确的查询数 / 总查询数 × 100% | ≥ 95% |
| **历史保留率 (History Preservation)** | 历史版本可正确查询的数 / 总矛盾对数 × 100% | ≥ 90% |
| **时间线排序准确率 (Temporal Sort Accuracy)** | 时间排序正确的查询数 / 涉及时间排序的查询数 × 100% | ≥ 90% |
| **部分更新保真度 (Partial Update Fidelity)** | 未修改字段保持不变的比例 × 100% | ≥ 95% |
| **取消事件检测率 (Cancellation Detection)** | 正确标记取消事件的比例 × 100% | ≥ 90% |

#### 2.2.3 测量方法

```python
def test_contradiction_update(test_case: dict) -> dict:
    """
    输入: test_case 包含多轮对话序列和查询列表
    输出: 测试结果字典
    """
    results = []
    
    # Step 1: 按时间顺序写入所有对话
    for conv in test_case["conversations"]:
        memory_store.write(conv)
    
    # Step 2: 对每个查询进行验证
    for query_case in test_case["queries"]:
        result = memory_store.query(query_case["query"])
        
        # 验证最新值
        latest_correct = verify_latest_value(result, query_case["expected_answer"])
        
        # 验证历史可追溯（如果需要）
        history_correct = True
        if "expected_answer_contains" in query_case:
            history_correct = verify_history(result, query_case["expected_answer_contains"])
        
        results.append({
            "query": query_case["query"],
            "latest_accuracy": latest_correct,
            "history_preservation": history_correct
        })
    
    return aggregate_metrics(results)
```

---

### 2.3 效率指标验证

**目标**: 验证记忆系统在工程层面的性能指标，确保满足生产可用性要求。

#### 2.3.1 测试用例设计

**用例 3.1 — 单次写入延迟**
```json
{
  "test_id": "efficiency_001",
  "category": "write_latency",
  "description": "测量单条记忆写入的端到端延迟",
  "test_data": {
    "conversation_length_chars": [50, 200, 500, 1000, 2000, 5000],
    "iterations_per_size": 10
  },
  "measurement": {
    "metric": "write_latency_p50_p95_p99_ms",
    "threshold_p50": 200,
    "threshold_p95": 500,
    "threshold_p99": 1000
  }
}
```

**用例 3.2 — 查询延迟**
```json
{
  "test_id": "efficiency_002",
  "category": "query_latency",
  "description": "测量不同记忆量级下的查询延迟",
  "setup": {
    "memory_sizes": [100, 500, 1000, 5000, 10000],
    "query_types": ["single_hop", "multi_hop", "temporal", "open_domain"],
    "queries_per_size": 20
  },
  "measurement": {
    "metric": "query_latency_p50_p95_ms",
    "threshold_p50": 300,
    "threshold_p95": 800
  }
}
```

**用例 3.3 — 内存占用**
```json
{
  "test_id": "efficiency_003",
  "category": "memory_usage",
  "description": "测量不同数据量下系统的内存占用",
  "setup": {
    "memory_sizes": [100, 1000, 5000, 10000]
  },
  "measurement": {
    "metric": "memory_usage_mb",
    "threshold_per_1000_entries": 50
  }
}
```

**用例 3.4 — Token 消耗效率**
```json
{
  "test_id": "efficiency_004",
  "category": "token_efficiency",
  "description": "测量每次查询的 Token 消耗",
  "setup": {
    "query_types": ["simple", "complex"],
    "iterations": 50
  },
  "measurement": {
    "metric": "avg_tokens_per_query",
    "threshold_simple": 500,
    "threshold_complex": 2000
  }
}
```

**用例 3.5 — 并发性能**
```json
{
  "test_id": "efficiency_005",
  "category": "concurrency",
  "description": "测量并发读写场景下的性能",
  "setup": {
    "concurrent_users": [1, 5, 10, 20, 50],
    "operations_per_user": 10,
    "read_write_ratio": 0.7
  },
  "measurement": {
    "metric": "throughput_ops_per_sec_and_latency_degradation",
    "threshold_max_latency_degradation": 2.0
  }
}
```

**用例 3.6 — 大规模数据压力测试**
```json
{
  "test_id": "efficiency_006",
  "category": "stress_test",
  "description": "测试系统在极端数据量下的稳定性",
  "setup": {
    "total_entries": 50000,
    "batch_write_size": 100,
    "query_after_each_batch": true
  },
  "measurement": {
    "metric": "stability_and_performance_consistency",
    "criteria": [
      "无崩溃或异常退出",
      "P95延迟增长不超过线性",
      "数据完整性100%"
    ]
  }
}
```

#### 2.3.2 效率指标汇总

| 指标名 | 目标值 | 测量方法 |
|--------|--------|----------|
| **写入延迟 P50** | ≤ 200ms | 高精度计时器，取中位数 |
| **写入延迟 P95** | ≤ 500ms | 高精度计时器，取第95百分位 |
| **查询延迟 P50** | ≤ 300ms | 高精度计时器，取中位数 |
| **查询延迟 P95** | ≤ 800ms | 高精度计时器，取第95百分位 |
| **内存占用/千条** | ≤ 50MB | 进程内存监控 (RSS) |
| **Token消耗（简单查询）** | ≤ 500 tokens | API返回值统计 |
| **Token消耗（复杂查询）** | ≤ 2000 tokens | API返回值统计 |
| **并发吞吐量** | ≥ 10 ops/sec (10用户) | 压测工具统计 |
| **数据完整性** | 100% | 写入后立即校验 |

#### 2.3.3 测量方法

```python
import time
import statistics
import tracemalloc

def test_write_latency(test_config: dict) -> dict:
    """测量写入延迟"""
    latencies = []
    for size in test_config["conversation_length_chars"]:
        for _ in range(test_config["iterations_per_size"]):
            conv = generate_conversation(size)
            start = time.perf_counter_ns()
            memory_store.write(conv)
            end = time.perf_counter_ns()
            latencies.append((end - start) / 1_000_000)  # 转换为毫秒
    
    return {
        "p50": statistics.median(latencies),
        "p95": sorted(latencies)[int(len(latencies) * 0.95)],
        "p99": sorted(latencies)[int(len(latencies) * 0.99)],
        "mean": statistics.mean(latencies),
        "std": statistics.stdev(latencies)
    }

def test_memory_usage(test_config: dict) -> dict:
    """测量内存占用"""
    results = {}
    for size in test_config["memory_sizes"]:
        tracemalloc.start()
        # 写入指定数量的记忆
        for i in range(size):
            memory_store.write(generate_conversation(200))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results[size] = {
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024,
            "per_entry_kb": current / size / 1024
        }
    return results

def test_token_efficiency(test_config: dict) -> dict:
    """测量Token消耗"""
    results = {}
    for query_type in test_config["query_types"]:
        token_counts = []
        for _ in range(test_config["iterations"]):
            query = generate_query(query_type)
            result = memory_store.query(query)
            token_counts.append(result.token_count)
        results[query_type] = {
            "mean": statistics.mean(token_counts),
            "p50": statistics.median(token_counts),
            "max": max(token_counts)
        }
    return results
```

---

## 3. 基线对比方案

### 3.1 对比维度

| 维度 | 无记忆系统（基线） | 有记忆系统（实验组） | 预期提升 |
|------|-------------------|---------------------|----------|
| **信息召回准确率** | 40-60%（仅依赖上下文窗口） | ≥ 90% | +30-50% |
| **多轮对话一致性** | 30-50%（长对话中容易遗忘） | ≥ 85% | +35-55% |
| **用户重复提问率** | 20-40%（系统无法记住之前的回答） | ≤ 5% | -15-35% |
| **平均响应相关性** | 60-70% | ≥ 90% | +20-30% |
| **查询延迟** | 100-200ms（无记忆检索） | 300-800ms（含检索） | 可接受范围 |
| **Token消耗** | 基准值 | 基准值 × 1.2-1.5 | 可接受范围 |

### 3.2 基线测试用例

**用例 B.1 — 无记忆系统的信息召回**
```json
{
  "test_id": "baseline_001",
  "description": "无记忆系统时的信息召回能力",
  "setup": {
    "conversation_history": [
      {"user": "项目X的deadline是5月15日", "assistant": "好的，已了解。", "timestamp": "2026-04-01T10:00:00Z"}
    ],
    "noise_after": 50,
    "use_memory_system": false
  },
  "query": "项目X的deadline是什么时候？",
  "measurement": ["answer_correctness", "answer_confidence", "response_latency"]
}
```

**用例 B.2 — 有记忆系统的信息召回**
```json
{
  "test_id": "baseline_002",
  "description": "有记忆系统时的信息召回能力",
  "setup": {
    "conversation_history": [
      {"user": "项目X的deadline是5月15日", "assistant": "已记录。", "timestamp": "2026-04-01T10:00:00Z"}
    ],
    "noise_after": 50,
    "use_memory_system": true
  },
  "query": "项目X的deadline是什么时候？",
  "measurement": ["answer_correctness", "answer_confidence", "response_latency"]
}
```

### 3.3 基线评估指标对比表

| 指标 | 计算方法 | 无记忆基线预期 | 有记忆系统目标 | 提升幅度要求 |
|------|----------|---------------|---------------|-------------|
| **单跳检索准确率** | 单一事实查询的正确率 | 55% | ≥ 92% | +37% |
| **多跳检索准确率** | 需关联多条记忆的查询正确率 | 20% | ≥ 80% | +60% |
| **时序推理准确率** | 涉及时间排序的查询正确率 | 15% | ≥ 85% | +70% |
| **开放域问答相关性** | 通用问题的回答相关性（1-5分） | 3.0 | ≥ 4.2 | +1.2分 |
| **用户满意度模拟** | 模拟用户对回答的满意程度（1-5分） | 2.8 | ≥ 4.0 | +1.2分 |

---

## 4. 方向 C 附加测试（个人工作习惯/偏好）

### 4.1 测试目标

验证系统能够：
- 学习并记住用户的个人工作习惯
- 根据偏好提供个性化建议
- 在偏好发生变化时及时更新
- 区分工作偏好与个人偏好

### 4.2 测试用例设计

**用例 C.1 — 工作习惯识别**
```json
{
  "test_id": "direction_c_001",
  "category": "work_habit_recognition",
  "conversations": [
    {
      "user": "我一般早上先处理邮件，再写代码",
      "assistant": "已记录您的工作习惯：早间优先处理邮件，然后写代码。",
      "timestamp": "2026-04-01T09:00:00Z"
    },
    {
      "user": "我习惯用番茄工作法，25分钟一个周期",
      "assistant": "已记录：您使用番茄工作法，25分钟/周期。",
      "timestamp": "2026-04-02T09:00:00Z"
    },
    {
      "user": "我午休一般从12点到1点半",
      "assistant": "已记录：午休时间 12:00-13:30。",
      "timestamp": "2026-04-03T09:00:00Z"
    }
  ],
  "queries": [
    {
      "query": "我一般怎么安排上午的工作？",
      "expected_elements": ["先处理邮件", "再写代码", "番茄工作法"],
      "evaluation": "应综合多条记忆给出个性化回答"
    },
    {
      "query": "午饭后适合安排什么？",
      "expected_elements": ["1点半后", "开始工作"],
      "evaluation": "应结合午休习惯给出建议"
    }
  ]
}
```

**用例 C.2 — 沟通偏好**
```json
{
  "test_id": "direction_c_002",
  "category": "communication_preference",
  "conversations": [
    {
      "user": "跟客户沟通时我喜欢先说结论再说原因",
      "assistant": "已记录：您的沟通偏好——结论先行。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "写周报的时候我喜欢用数据说话",
      "assistant": "已记录：周报偏好——数据驱动。",
      "timestamp": "2026-04-05T10:00:00Z"
    },
    {
      "user": "我比较不喜欢在会议上即兴发言",
      "assistant": "已记录：偏好——不喜欢即兴会议发言，倾向于提前准备。",
      "timestamp": "2026-04-10T10:00:00Z"
    }
  ],
  "queries": [
    {
      "query": "帮我准备一下明天和客户的沟通要点",
      "expected_style": "结论先行",
      "expected_elements": ["先给出核心结论", "再展开原因"],
      "evaluation": "回复风格应体现结论先行偏好"
    },
    {
      "query": "帮我写本周的周报大纲",
      "expected_style": "数据驱动",
      "expected_elements": ["包含数据指标", "量化成果"],
      "evaluation": "大纲应体现数据驱动偏好"
    },
    {
      "query": "明天的会议我需要发言，帮我准备一下",
      "expected_elements": ["提前准备", "发言稿/要点"],
      "evaluation": "应提醒提前准备而非即兴"
    }
  ]
}
```

**用例 C.3 — 偏好更新**
```json
{
  "test_id": "direction_c_003",
  "category": "preference_update",
  "conversations": [
    {
      "user": "我现在开始用 Notion 做任务管理了",
      "assistant": "已更新：任务管理工具从待确认变为 Notion。",
      "timestamp": "2026-04-20T10:00:00Z"
    },
    {
      "user": "我不用番茄工作法了，现在用时间块的方式",
      "assistant": "已更新：工作方法从番茄工作法变更为时间块管理。",
      "timestamp": "2026-04-25T10:00:00Z"
    }
  ],
  "queries": [
    {
      "query": "我现在用什么工具管理任务？",
      "expected_answer": "Notion",
      "must_not_mention": ["旧工具"]
    },
    {
      "query": "我之前用什么方法管理时间？",
      "expected_answer": "番茄工作法",
      "evaluation": "应能追溯历史偏好"
    }
  ]
}
```

**用例 C.4 — 上下文感知推荐**
```json
{
  "test_id": "direction_c_004",
  "category": "context_aware_recommendation",
  "conversations": [
    {"user": "我一般周三下午不安排会议", "assistant": "已记录。", "timestamp": "2026-04-01T10:00:00Z"},
    {"user": "我做代码审查喜欢逐文件review", "assistant": "已记录。", "timestamp": "2026-04-02T10:00:00Z"},
    {"user": "我习惯在周五下午做一周总结", "assistant": "已记录。", "timestamp": "2026-04-03T10:00:00Z"}
  ],
  "queries": [
    {
      "query": "帮我安排下周的工作",
      "expected_elements": ["周三下午留空", "周五下午安排总结"],
      "evaluation": "应自动结合用户习惯进行安排"
    },
    {
      "query": "这个PR需要review，帮我制定review计划",
      "expected_elements": ["逐文件review"],
      "evaluation": "应体现用户的review偏好"
    }
  ]
}
```

### 4.3 方向 C 指标

| 指标名 | 计算公式 | 目标值 |
|--------|----------|--------|
| **偏好召回率** | 正确召回的偏好数 / 存储的偏好总数 × 100% | ≥ 90% |
| **偏好更新准确率** | 最新偏奔回答正确的查询数 / 总查询数 × 100% | ≥ 95% |
| **历史偏好追溯率** | 能正确回答历史偏好的查询数 / 总历史查询数 × 100% | ≥ 85% |
| **上下文感知得分** | 推荐结果与用户习惯的匹配度（人工评分1-5分） | ≥ 4.0 |
| **偏好区分准确率** | 正确区分不同类别偏好的比例 | ≥ 90% |

---

## 5. 方向 D 附加测试（团队知识缺口/遗忘提醒）

### 5.1 测试目标

验证系统能够：
- 检测团队知识覆盖缺口
- 识别关键信息的遗忘风险
- 提供及时的遗忘提醒
- 支持团队知识共享与同步

### 5.2 测试用例设计

**用例 D.1 — 知识缺口检测**
```json
{
  "test_id": "direction_d_001",
  "category": "knowledge_gap_detection",
  "team_members": ["张三", "李四", "王五", "赵六"],
  "conversations": [
    {
      "user": "张三",
      "content": "项目K使用 React + TypeScript 技术栈",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "张三",
      "content": "项目K的部署用的是 AWS ECS",
      "timestamp": "2026-04-02T10:00:00Z"
    },
    {
      "user": "李四",
      "content": "项目K的前端用的是 Vue",
      "timestamp": "2026-04-03T10:00:00Z",
      "note": "注意：这里有知识冲突——张三说是React，李四说是Vue"
    }
  ],
  "queries": [
    {
      "query": "团队对项目K的技术栈了解情况如何？",
      "expected_elements": [
        "张三了解前端技术栈（React）",
        "李四了解前端技术栈（Vue）——与张三认知不一致",
        "王五、赵六可能不了解",
        "存在信息不一致"
      ],
      "evaluation": "应检测出知识缺口和认知冲突"
    }
  ]
}
```

**用例 D.2 — 遗忘提醒测试**
```json
{
  "test_id": "direction_d_002",
  "category": "forgetting_alert",
  "conversations": [
    {
      "user": "项目L的安全审计要在6月1日前完成",
      "assistant": "已记录。安全审计截止日：6月1日。",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "项目L的数据库备份策略需要更新",
      "assistant": "已记录。待办：更新数据库备份策略。",
      "timestamp": "2026-04-05T10:00:00Z"
    }
  ],
  "time_advancement_days": 45,
  "queries": [
    {
      "query": "项目L有什么需要注意的事项？",
      "expected_elements": [
        "安全审计即将到期（6月1日）",
        "数据库备份策略待更新"
      ],
      "evaluation": "应主动提醒即将到期的事项"
    }
  ]
}
```

**用例 D.3 — 团队知识同步**
```json
{
  "test_id": "direction_d_003",
  "category": "team_knowledge_sync",
  "conversations": [
    {
      "user": "张三",
      "content": "项目M的API文档在Confluence上",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "user": "李四",
      "content": "项目M的API文档迁移到Notion了",
      "timestamp": "2026-04-15T10:00:00Z"
    }
  ],
  "queries": [
    {
      "query": "项目M的API文档在哪里？",
      "expected_answer": "Notion（已从Confluence迁移）",
      "evaluation": "应使用最新信息并告知迁移历史"
    },
    {
      "query": "谁可能还在用旧的文档地址？",
      "expected_answer": "在4月15日之前了解文档位置的成员可能还在用Confluence",
      "evaluation": "应能推断潜在的知识不同步"
    }
  ]
}
```

**用例 D.4 — 关键知识遗忘检测**
```json
{
  "test_id": "direction_d_004",
  "category": "critical_knowledge_forgetting",
  "conversations": [
    {
      "user": "项目N的数据库root密码是 SecretP@ss123",
      "assistant": "已安全记录（加密存储）。建议使用密钥管理服务。",
      "timestamp": "2026-03-01T10:00:00Z"
    }
  ],
  "time_advancement_days": 90,
  "queries": [
    {
      "query": "项目N的数据库密码是什么？",
      "expected_elements": [
        "信息已记录但已超过90天",
        "安全提醒：建议轮换密码",
        "提醒使用密钥管理服务"
      ],
      "evaluation": "应提醒密码可能需要更新，提供安全建议"
    }
  ]
}
```

**用例 D.5 — 团队知识覆盖率评估**
```json
{
  "test_id": "direction_d_005",
  "category": "team_knowledge_coverage",
  "team_members": ["张三", "李四", "王五", "赵六", "钱七"],
  "knowledge_domains": ["前端", "后端", "数据库", "DevOps", "安全", "产品"],
  "conversations_by_member": {
    "张三": [
      {"content": "前端用React", "domain": "前端"},
      {"content": "后端用Go", "domain": "后端"}
    ],
    "李四": [
      {"content": "数据库用PostgreSQL", "domain": "数据库"}
    ],
    "王五": [
      {"content": "部署用Kubernetes", "domain": "DevOps"}
    ]
    // 赵六、钱七没有相关知识贡献
  },
  "queries": [
    {
      "query": "团队在安全和产品领域的知识覆盖情况如何？",
      "expected_answer": "安全领域和产品领域没有明确的团队成员覆盖，存在知识缺口",
      "expected_recommendations": [
        "建议安排安全培训或引入安全顾问",
        "建议安排产品知识分享"
      ]
    }
  ]
}
```

### 5.3 方向 D 指标

| 指标名 | 计算公式 | 目标值 |
|--------|----------|--------|
| **知识缺口检测率** | 正确检测的缺口数 / 实际缺口总数 × 100% | ≥ 80% |
| **遗忘提醒及时性** | 在截止日前N天提醒的比率 × 100%（N≥7天） | ≥ 90% |
| **知识冲突识别率** | 识别出的矛盾知识对数 / 实际矛盾对总数 × 100% | ≥ 85% |
| **知识覆盖率计算准确率** | 覆盖率报告的准确度（与人工评估对比） | ≥ 85% |
| **安全信息处理合规率** | 安全类信息正确加密存储/提醒的比例 | 100% |
| **团队同步建议质量** | 建议的相关性和可执行性（1-5分） | ≥ 3.8 |

---

## 6. 参考基准与对标

### 6.1 LOCOMO 基准对标

| LOCOMO维度 | 我们的设计对标 | 目标值 |
|------------|---------------|--------|
| 单跳检索 (Single-hop) | 用例 1.1-1.5, 2.1-2.2 | ≥ 92% F1 |
| 多跳检索 (Multi-hop) | 用例 2.4, C.1, D.1 | ≥ 80% F1 |
| 时序推理 (Temporal) | 用例 2.3, 1.4 | ≥ 85% F1 |
| 开放域问答 (Open-domain) | 用例 C.4, D.5 | ≥ 82% 相关性 |

### 6.2 LongMemEval 基准对标

| LongMemEval维度 | 我们的设计对标 | 目标值 |
|-----------------|---------------|--------|
| 信息提取 (Info Extraction) | 用例 1.1-1.5 | ≥ 90% 准确率 |
| 多会话推理 (Multi-session Reasoning) | 用例 2.3-2.5, C.1 | ≥ 82% 准确率 |
| 知识更新 (Knowledge Update) | 用例 2.1-2.5 | ≥ 95% 准确率 |
| 时序推理 (Temporal Reasoning) | 用例 2.3, 1.4 | ≥ 85% 准确率 |

---

## 7. 测试用例代码映射表

| 测试用例ID | 测试文件名 | 测试函数名 | 优先级 |
|------------|-----------|-----------|--------|
| anti_interference_001 | test_anti_interference.py | test_single_round_noise | P0 |
| anti_interference_002 | test_anti_interference.py | test_multi_round_noise | P0 |
| anti_interference_003 | test_anti_interference.py | test_similar_topic_noise | P0 |
| anti_interference_004 | test_anti_interference.py | test_temporal_spread_noise | P1 |
| anti_interference_005 | test_anti_interference.py | test_role_confusion_noise | P0 |
| contradiction_001 | test_contradiction.py | test_direct_override | P0 |
| contradiction_002 | test_contradiction.py | test_partial_update | P0 |
| contradiction_003 | test_contradiction.py | test_temporal_contradiction | P0 |
| contradiction_004 | test_contradiction.py | test_multi_entity_contradiction | P1 |
| contradiction_005 | test_contradiction.py | test_cancel_retraction | P1 |
| efficiency_001 | test_efficiency.py | test_write_latency | P0 |
| efficiency_002 | test_efficiency.py | test_query_latency | P0 |
| efficiency_003 | test_efficiency.py | test_memory_usage | P1 |
| efficiency_004 | test_efficiency.py | test_token_efficiency | P1 |
| efficiency_005 | test_efficiency.py | test_concurrency | P1 |
| efficiency_006 | test_efficiency.py | test_stress | P2 |
| direction_c_001 | test_direction_c.py | test_work_habit_recognition | P0 |
| direction_c_002 | test_direction_c.py | test_communication_preference | P0 |
| direction_c_003 | test_direction_c.py | test_preference_update | P1 |
| direction_c_004 | test_direction_c.py | test_context_aware_recommendation | P1 |
| direction_d_001 | test_direction_d.py | test_knowledge_gap_detection | P0 |
| direction_d_002 | test_direction_d.py | test_forgetting_alert | P0 |
| direction_d_003 | test_direction_d.py | test_team_knowledge_sync | P1 |
| direction_d_004 | test_direction_d.py | test_critical_knowledge_forgetting | P1 |
| direction_d_005 | test_direction_d.py | test_team_knowledge_coverage | P2 |

---

## 8. 附录：数据构造规范

### 8.1 对话数据格式

```json
{
  "conversation_id": "string",
  "user_id": "string",
  "user_name": "string",
  "timestamp": "ISO-8601",
  "messages": [
    {
      "role": "user|assistant",
      "content": "string",
      "timestamp": "ISO-8601"
    }
  ],
  "metadata": {
    "source": "feishu_chat|manual|api",
    "project": "string (optional)",
    "tags": ["string"] (optional)
  }
}
```

### 8.2 测试结果格式

```json
{
  "test_id": "string",
  "test_name": "string",
  "timestamp": "ISO-8601",
  "status": "pass|fail|skip|error",
  "metrics": {
    "metric_name": {
      "value": 0.0,
      "target": 0.0,
      "passed": true
    }
  },
  "latency_ms": 0.0,
  "token_count": 0,
  "details": "string (optional)",
  "error_message": "string (if failed)"
}
```

### 8.3 评估报告格式

```json
{
  "report_id": "string",
  "run_timestamp": "ISO-8601",
  "system_version": "string",
  "summary": {
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "overall_score": 0.0
  },
  "dimension_scores": {
    "anti_interference": 0.0,
    "contradiction_update": 0.0,
    "efficiency": 0.0,
    "direction_c": 0.0,
    "direction_d": 0.0
  },
  "baseline_comparison": {
    "without_memory": {...},
    "with_memory": {...},
    "improvement": {...}
  },
  "detailed_results": [...],
  "recommendations": ["string"]
}
```

### 8.4 评分权重配置

```yaml
scoring_weights:
  anti_interference: 0.25
  contradiction_update: 0.25
  efficiency: 0.20
  direction_c: 0.15
  direction_d: 0.15

sub_dimension_weights:
  anti_interference:
    recall: 0.30
    precision: 0.30
    noise_injection_rate: 0.20
    f1_score: 0.20
  contradiction_update:
    latest_accuracy: 0.35
    history_preservation: 0.25
    temporal_sort: 0.20
    partial_update_fidelity: 0.20
  efficiency:
    write_latency: 0.25
    query_latency: 0.30
    memory_usage: 0.15
    token_efficiency: 0.15
    concurrency: 0.15
  direction_c:
    preference_recall: 0.25
    preference_update_accuracy: 0.25
    history_traceability: 0.20
    context_awareness: 0.15
    preference_distinction: 0.15
  direction_d:
    gap_detection_rate: 0.25
    alert_timeliness: 0.25
    conflict_identification: 0.20
    coverage_accuracy: 0.15
    security_compliance: 0.15
```

---

## 测试执行流程

### 执行顺序

```
Phase 1: 基线测试（无记忆系统）
  ├── baseline_001: 无记忆信息召回
  └── 记录基线指标

Phase 2: 竞赛必测项
  ├── Phase 2a: 抗干扰测试 (5个用例)
  ├── Phase 2b: 矛盾更新测试 (5个用例)
  └── Phase 2c: 效率指标测试 (6个用例)

Phase 3: 方向C测试
  ├── Phase 3a: 工作习惯识别
  ├── Phase 3b: 沟通偏好
  ├── Phase 3c: 偏好更新
  └── Phase 3d: 上下文感知推荐

Phase 4: 方向D测试
  ├── Phase 4a: 知识缺口检测
  ├── Phase 4b: 遗忘提醒
  ├── Phase 4c: 知识同步
  ├── Phase 4d: 关键知识遗忘
  └── Phase 4e: 知识覆盖率

Phase 5: 有记忆系统的对照测试
  ├── 重复 Phase 1 的测试用例（使用记忆系统）
  └── 计算对比提升

Phase 6: 生成评估报告
  ├── 汇总所有测试结果
  ├── 计算加权总分
  ├── 生成基线对比图
  └── 输出改进建议
```

### 自动化执行脚本框架

```python
# run_evaluation.py 框架
class EvaluationRunner:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.results = []
    
    def run_all(self):
        """执行全部测试"""
        phases = [
            ("baseline", self.run_baseline),
            ("anti_interference", self.run_anti_interference),
            ("contradiction", self.run_contradiction),
            ("efficiency", self.run_efficiency),
            ("direction_c", self.run_direction_c),
            ("direction_d", self.run_direction_d),
            ("comparison", self.run_comparison),
        ]
        
        for phase_name, runner in phases:
            print(f"\n{'='*60}")
            print(f"执行阶段: {phase_name}")
            print(f"{'='*60}")
            phase_results = runner()
            self.results.extend(phase_results)
        
        self.generate_report()
    
    def generate_report(self):
        """生成评估报告"""
        report = {
            "summary": calculate_summary(self.results),
            "dimension_scores": calculate_dimension_scores(self.results),
            "baseline_comparison": calculate_comparison(self.results),
            "recommendations": generate_recommendations(self.results)
        }
        save_report(report, "evaluation_report.json")
```

---

*文档结束 — 企业记忆引擎评估方案 v1.0*
