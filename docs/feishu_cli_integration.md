# MemScope 飞书 CLI 集成分析

> 分析时间：2026-05-05
> 分析目标：如何让 MemScope 作为 OpenClaw/Hermes Agent 的记忆插件并作用于飞书 CLI

---

## 1. 飞书 CLI 架构概述

### 1.1 项目简介

飞书 CLI（lark-cli）是飞书官方维护的命令行工具，专为人类用户和 AI Agent 设计。

**核心特点**：
- **200+ 命令**：覆盖 17 个业务领域
- **24 个 AI Agent Skills**：结构化技能，开箱即用
- **三层架构**：Shortcuts → API Commands → Raw API
- **Agent 原生设计**：简洁参数、智能默认值、结构化输出

### 1.2 业务领域覆盖

| 领域 | 能力 |
|------|------|
| 📅 Calendar | 查看日程、创建事件、查询空闲时间 |
| 💬 Messenger | 发送/回复消息、群聊管理、消息搜索 |
| 📄 Docs | 创建/读取/更新/搜索文档 |
| 📁 Drive | 上传下载文件、搜索文档 |
| 📊 Base | 多维表格管理 |
| 📈 Sheets | 电子表格操作 |
| ✅ Tasks | 任务管理 |
| 📚 Wiki | 知识库管理 |
| 📧 Mail | 邮件管理 |
| 🎥 Meetings | 会议记录查询 |

### 1.3 三层命令系统

```
┌─────────────────────────────────────────────────────────────┐
│                    飞书 CLI 三层架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第1层：Shortcuts（快捷命令）                                │
│  - 前缀：+                                                  │
│  - 人机友好，智能默认值                                       │
│  - 示例：lark-cli calendar +agenda                          │
│                                                             │
│  第2层：API Commands（API 命令）                             │
│  - 从 OAPI 元数据自动生成                                    │
│  - 1:1 映射平台端点                                          │
│  - 示例：lark-cli calendar calendars list                   │
│                                                             │
│  第3层：Raw API（原始 API）                                  │
│  - 直接调用任意飞书 Open Platform 端点                        │
│  - 覆盖 2500+ API                                           │
│  - 示例：lark-cli api GET /open-apis/calendar/v4/calendars  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 AI Agent Skills

飞书 CLI 提供 24 个结构化技能，可与 AI 工具集成：

| Skill | 描述 |
|-------|------|
| lark-shared | 应用配置、认证登录、身份切换 |
| lark-calendar | 日历事件、日程查询 |
| lark-im | 消息发送/回复、群聊管理 |
| lark-doc | 文档创建/读取/更新 |
| lark-drive | 文件上传下载 |
| lark-sheets | 电子表格操作 |
| lark-task | 任务管理 |
| lark-wiki | 知识库管理 |
| lark-event | 实时事件订阅 |
| lark-vc | 会议记录查询 |

---

## 2. Hermes Agent 插件机制分析

### 2.1 Hermes Agent 架构

基于对 MemScope 项目代码的分析，Hermes Agent 的插件机制如下：

```
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Agent 架构                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Agent      │    │   Plugin     │    │   Memory     │  │
│  │   Runtime    │ ←→ │   System     │ ←→ │   Provider   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │          │
│         ↓                   ↓                   ↓          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  LLM 调用    │    │  Tool 路由   │    │  记忆存储    │  │
│  │  对话管理    │    │  Hook 触发   │    │  记忆检索    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 插件配置（plugin.yaml）

```yaml
name: memscope
version: 2.0.0
description: MemScope — Enterprise Long-term Collaboration Memory System
hooks:
  - on_session_start
  - on_session_end
  - pre_llm_call
  - post_llm_call
requires_env:
  - MEMOS_EMBEDDING_MODEL
config:
  db_path:
    type: string
    default: "memos/memscope.db"
  agent_id:
    type: string
    default: "default"
  # ... 更多配置
```

### 2.3 Memory Provider 接口

MemScopeProvider 实现了以下关键接口：

```python
class MemScopeProvider:
    def name(self) -> str:
        """返回插件名称"""
        return 'memscope'
    
    def is_available(self) -> bool:
        """检查插件是否可用"""
        return True
    
    def initialize(self, session_id: str, **kwargs) -> None:
        """初始化插件"""
        # 初始化存储层、检索引擎、四大方向模块
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """返回工具定义（供 Agent 调用）"""
        return [
            {'name': 'memory_search', ...},
            {'name': 'command_log', ...},
            {'name': 'decision_record', ...},
            {'name': 'preference_set', ...},
            {'name': 'knowledge_health', ...},
            # ... 14个工具
        ]
    
    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """处理工具调用"""
        # 路由到对应的处理函数
    
    def prefetch(self, query: str) -> Optional[str]:
        """LLM 调用前预取记忆"""
        # 搜索相关记忆，返回上下文
    
    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        """同步对话轮次"""
        # 提取并存储记忆
    
    def on_session_end(self) -> None:
        """会话结束时的清理"""
        # 保存会话状态
```

### 2.4 生命周期 Hook

| Hook | 触发时机 | MemScope 用途 |
|------|----------|---------------|
| on_session_start | 会话开始 | 初始化存储、加载历史记忆 |
| pre_llm_call | LLM 调用前 | prefetch() 预取相关记忆 |
| post_llm_call | LLM 调用后 | sync_turn() 同步对话 |
| on_session_end | 会话结束 | 保存会话状态、触发遗忘 |

---

## 3. MemScope 集成方案

### 3.1 集成架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MemScope + 飞书 CLI 集成架构                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      飞书 CLI (lark-cli)                      │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │  │
│  │  │ lark-im │  │lark-doc │  │lark-task│  │  ...    │         │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘         │  │
│  │       │            │            │            │               │  │
│  │       └────────────┼────────────┼────────────┘               │  │
│  │                    │            │                             │  │
│  │                    ↓            ↓                             │  │
│  │            ┌───────────────────────────┐                      │  │
│  │            │    飞书 Open API          │                      │  │
│  │            │    (消息/文档/任务...)     │                      │  │
│  │            └───────────────────────────┘                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ↓                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Hermes Agent                             │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                    Plugin System                         │  │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │  │  │
│  │  │  │   Hooks     │  │   Tools     │  │   Memory    │     │  │  │
│  │  │  │             │  │             │  │   Provider  │     │  │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘     │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                              │                                │  │
│  │                              ↓                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                    MemScope                             │  │  │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │  │
│  │  │  │ 方向A   │  │ 方向B   │  │ 方向C   │  │ 方向D   │   │  │  │
│  │  │  │ 命令    │  │ 决策    │  │ 偏好    │  │ 知识    │   │  │  │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │  │  │
│  │  │  ┌─────────────────────────────────────────────────┐   │  │  │
│  │  │  │  SqliteStore + RecallEngine + IngestPipeline   │   │  │  │
│  │  │  └─────────────────────────────────────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 集成方式

#### 方式一：作为 Hermes Agent 记忆插件（推荐）

MemScope 作为 Hermes Agent 的 memory_provider 插件运行：

1. **插件注册**：通过 `plugin.yaml` 声明插件配置
2. **Memory Provider**：实现 `MemScopeProvider` 类
3. **Tool 注册**：通过 `get_tool_schemas()` 注册 14 个工具
4. **Hook 绑定**：绑定 `on_session_start`、`pre_llm_call` 等 Hook
5. **自动激活**：Hermes Agent 启动时自动加载 MemScope

**工作流程**：
```
用户输入 → Hermes Agent → pre_llm_call Hook → MemScope.prefetch()
         → LLM 生成响应 → post_llm_call Hook → MemScope.sync_turn()
         → 返回响应给用户
```

#### 方式二：直接与飞书 CLI 集成

MemScope 直接调用飞书 CLI 命令：

```python
import subprocess

def send_feishu_message(chat_id: str, content: str):
    """通过飞书 CLI 发送消息"""
    cmd = [
        'lark-cli', 'im', '+messages-send',
        '--chat-id', chat_id,
        '--text', content,
        '--format', 'json'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def get_feishu_messages(chat_id: str, limit: int = 10):
    """通过飞书 CLI 获取消息"""
    cmd = [
        'lark-cli', 'im', '+messages-list',
        '--chat-id', chat_id,
        '--limit', str(limit),
        '--format', 'json'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)
```

### 3.3 数据流向

```
┌─────────────────────────────────────────────────────────────────┐
│                    MemScope 数据流向                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  飞书消息/CLI命令                                                │
│       │                                                         │
│       ↓                                                         │
│  ┌─────────────────┐                                            │
│  │  信息提取       │ ← 方向B: 决策提取                          │
│  │  (Ingest)       │ ← 方向C: 偏好提取                          │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │  记忆存储       │ ← SqliteStore (chunks, decisions,          │
│  │  (Store)        │    preferences, knowledge_health)          │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │  记忆检索       │ ← RecallEngine (FTS5 + 向量 + Pattern)     │
│  │  (Recall)       │ ← RRF 融合 + MMR 重排                      │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │  记忆推送       │ ← 方向A: 命令推荐                          │
│  │  (Push)         │ ← 方向B: 决策卡片                          │
│  │                 │ ← 方向D: 遗忘预警                          │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. CLI/飞书端切换方案

### 4.1 双端交互架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI/飞书端切换架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  CLI 终端       │              │  飞书端         │          │
│  │  (本地交互)     │              │  (远程交互)     │          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │                                │                   │
│           ↓                                ↓                   │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  stdin/stdout   │              │  飞书 API       │          │
│  │  命令行参数     │              │  Webhook/Event  │          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │                                │                   │
│           └────────────┬───────────────────┘                   │
│                        │                                       │
│                        ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    统一接口层                            │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  MemScopeProvider.handle_tool_call()            │   │   │
│  │  │  - 输入: {tool_name, args}                      │   │   │
│  │  │  - 输出: {result}                               │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                        │                                       │
│                        ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MemScope 核心                        │   │
│  │  - 存储层 (SqliteStore)                                │   │
│  │  - 检索层 (RecallEngine)                               │   │
│  │  - 四大方向模块                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 切换实现

#### CLI 模式

```python
# cli_mode.py
import argparse
from src import MemScopeProvider

def main():
    parser = argparse.ArgumentParser(description='MemScope CLI')
    parser.add_argument('--command', choices=['search', 'log', 'recommend', ...])
    parser.add_argument('--query', type=str)
    parser.add_argument('--user', type=str, default='local')
    args = parser.parse_args()
    
    # 初始化 MemScope
    provider = MemScopeProvider()
    provider.initialize(session_id='cli-session')
    
    # 处理命令
    if args.command == 'search':
        result = provider.handle_tool_call('memory_search', {'query': args.query})
        print(result)
    elif args.command == 'log':
        result = provider.handle_tool_call('command_log', {'command': args.query})
        print(result)
    # ...

if __name__ == '__main__':
    main()
```

#### 飞书模式

```python
# feishu_mode.py
from src import MemScopeProvider
from src.feishu.client import FeishuClient

def handle_feishu_event(event: dict):
    """处理飞书事件"""
    # 初始化 MemScope
    provider = MemScopeProvider()
    provider.initialize(session_id='feishu-session')
    
    # 提取消息
    message = event.get('event', {}).get('message', {})
    content = message.get('content', '')
    chat_id = message.get('chat_id', '')
    
    # 使用 MemScope 处理
    # 1. 提取记忆
    provider.sync_turn(content, '')
    
    # 2. 搜索相关记忆
    memories = provider.handle_tool_call('memory_search', {'query': content})
    
    # 3. 检查决策卡片
    cards = provider.handle_tool_call('decision_cards', {'message': content})
    
    # 4. 推送响应
    feishu_client = FeishuClient()
    if cards:
        feishu_client.send_card(chat_id, cards[0])
    else:
        feishu_client.send_text(chat_id, f"找到相关记忆: {memories}")
```

### 4.3 统一接口设计

```python
# unified_interface.py
from typing import Dict, Any, Optional
from src import MemScopeProvider

class MemScopeInterface:
    """MemScope 统一接口，支持 CLI 和飞书双端"""
    
    def __init__(self):
        self.provider = MemScopeProvider()
        self.provider.initialize(session_id='unified')
    
    def process(self, input_data: Dict[str, Any], source: str = 'cli') -> Dict[str, Any]:
        """
        统一处理接口
        
        Args:
            input_data: 输入数据
            source: 来源 ('cli' 或 'feishu')
        
        Returns:
            处理结果
        """
        action = input_data.get('action')
        args = input_data.get('args', {})
        
        # 调用 MemScope
        result = self.provider.handle_tool_call(action, args)
        
        # 根据来源格式化输出
        if source == 'cli':
            return self._format_for_cli(result)
        else:
            return self._format_for_feishu(result)
    
    def _format_for_cli(self, result: str) -> Dict[str, Any]:
        """CLI 格式化"""
        return {'output': result, 'format': 'text'}
    
    def _format_for_feishu(self, result: str) -> Dict[str, Any]:
        """飞书格式化"""
        import json
        data = json.loads(result)
        
        # 如果有决策卡片，返回卡片格式
        if 'cards' in data:
            return {'type': 'card', 'content': data['cards']}
        
        # 否则返回文本格式
        return {'type': 'text', 'content': result}
```

---

## 5. 关键接口和代码路径

### 5.1 核心文件

| 文件 | 用途 |
|------|------|
| `plugin.yaml` | 插件配置声明 |
| `src/__init__.py` | MemScopeProvider 主入口 |
| `src/core/store.py` | SQLite 存储层 |
| `src/recall/engine.py` | 混合检索引擎 |
| `src/feishu/client.py` | 飞书 API 客户端 |
| `src/feishu/pipeline.py` | 飞书消息处理管线 |

### 5.2 关键接口

| 接口 | 调用方 | 用途 |
|------|--------|------|
| `MemScopeProvider.initialize()` | Hermes Agent | 初始化插件 |
| `MemScopeProvider.get_tool_schemas()` | Hermes Agent | 获取工具定义 |
| `MemScopeProvider.handle_tool_call()` | Hermes Agent / CLI / 飞书 | 处理工具调用 |
| `MemScopeProvider.prefetch()` | Hermes Agent (pre_llm_call) | 预取记忆 |
| `MemScopeProvider.sync_turn()` | Hermes Agent (post_llm_call) | 同步对话 |
| `MemScopeProvider.on_session_end()` | Hermes Agent (on_session_end) | 会话结束 |

### 5.3 飞书 CLI 命令映射

| MemScope 功能 | 飞书 CLI 命令 | 用途 |
|---------------|---------------|------|
| 发送决策卡片 | `lark-cli im +messages-send --type interactive` | 推送决策卡片 |
| 获取群聊消息 | `lark-cli im +messages-list` | 获取飞书对话 |
| 搜索消息 | `lark-cli im +messages-search` | 搜索历史消息 |
| 发送预警 | `lark-cli im +messages-send` | 推送知识健康预警 |

---

## 6. 实施建议

### 6.1 优先级

1. **P0**：确保 MemScopeProvider 正确实现 memory_provider 接口
2. **P0**：确保 plugin.yaml 正确声明 hooks 和 tools
3. **P1**：实现 CLI 模式的统一接口
4. **P1**：实现飞书模式的消息处理管线
5. **P2**：实现 CLI/飞书端切换机制

### 6.2 验证清单

- [ ] MemScopeProvider 实现了 `name()`、`is_available()`、`initialize()` 方法
- [ ] MemScopeProvider 实现了 `get_tool_schemas()` 返回 14 个工具定义
- [ ] MemScopeProvider 实现了 `handle_tool_call()` 路由到正确处理函数
- [ ] MemScopeProvider 实现了 `prefetch()`、`sync_turn()`、`on_session_end()` 生命周期
- [ ] plugin.yaml 声明了 `on_session_start`、`on_session_end`、`pre_llm_call`、`post_llm_call` hooks
- [ ] 飞书客户端使用真实 API（非 mock）
- [ ] CLI 模式可以独立运行
- [ ] 飞书模式可以接收消息并响应

---

## 参考资料

1. 飞书 CLI GitHub: https://github.com/larksuite/cli
2. 飞书 Open Platform: https://open.feishu.cn/
3. MemScope 架构设计: docs/architecture_design.md
4. MemScope 评测方案: docs/evaluation_scheme_v2.md
