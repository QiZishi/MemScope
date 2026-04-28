"""
Context Engine - 上下文引擎

自动将召回的记忆注入 assistant 消息，使用 <relevant-memories> 标签
"""

from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class ContextEngine:
    """上下文引擎"""
    
    def __init__(
        self,
        recall_engine: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.recall_engine = recall_engine
        self.config = config or {}
        
        # 配置
        self.max_memories = self.config.get("max_memories", 5)
        self.min_score = self.config.get("min_score", 0.45)
    
    def inject_memories(
        self,
        message: Dict[str, Any],
        query: str,
        agent_id: str = "default",
    ) -> Dict[str, Any]:
        """
        将召回的记忆注入消息
        
        Args:
            message: assistant 消息
            query: 用户查询
            agent_id: Agent ID
            
        Returns:
            注入记忆后的消息
        """
        # 搜索相关记忆
        search_result = self.recall_engine.search(
            query=query,
            max_results=self.max_memories,
            min_score=self.min_score,
            agent_id=agent_id,
        )
        
        hits = search_result.get("hits", [])
        
        if not hits:
            return message
        
        # 构建记忆块
        memory_block = self._build_memory_block(hits)
        
        # 注入消息
        return self._append_memory_to_message(message, memory_block)
    
    def _build_memory_block(self, hits: List[Dict[str, Any]]) -> str:
        """构建记忆块"""
        block = "\n<relevant-memories>\n"
        
        for hit in hits:
            summary = hit.get("summary", "")
            excerpt = hit.get("original_excerpt", "")
            score = hit.get("score", 0)
            role = hit.get("role", "assistant")
            ts = hit.get("source", {}).get("ts", 0)
            
            # 格式化时间
            from datetime import datetime
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts / 1000)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = str(ts)
            else:
                time_str = "unknown"
            
            block += f"""
Memory (score={score:.2f}, role={role}, time={time_str}):
{excerpt[:500]}
---
"""
        
        block += "</relevant-memories>\n"
        
        return block
    
    def _append_memory_to_message(
        self,
        message: Dict[str, Any],
        memory_block: str,
    ) -> Dict[str, Any]:
        """将记忆块附加到消息"""
        content = message.get("content", "")
        
        if isinstance(content, str):
            # 移除旧的记忆块（如果有）
            content = re.sub(
                r'\n?<relevant-memories>[\s\S]*?</relevant-memories>\n?',
                '',
                content
            )
            # 附加新的记忆块
            message["content"] = content + memory_block
        
        elif isinstance(content, list):
            # 处理多块内容
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    text = re.sub(
                        r'\n?<relevant-memories>[\s\S]*?</relevant-memories>\n?',
                        '',
                        text
                    )
                    block["text"] = text + memory_block
                    break
        
        return message
    
    def extract_memories_from_message(
        self,
        message: Dict[str, Any],
    ) -> Optional[str]:
        """从消息中提取记忆块"""
        content = message.get("content", "")
        
        if isinstance(content, str):
            match = re.search(
                r'<relevant-memories>[\s\S]*?</relevant-memories>',
                content
            )
            if match:
                return match.group()
        
        return None
    
    def should_inject(
        self,
        query: str,
        context: Dict[str, Any],
    ) -> bool:
        """
        判断是否应该注入记忆
        
        Args:
            query: 用户查询
            context: 上下文
            
        Returns:
            True 表示应该注入
        """
        # 简单的启发式规则
        
        # 1. 查询长度太短，不注入
        if len(query) < 10:
            return False
        
        # 2. 简单问候，不注入
        trivial_patterns = [
            r'^(hello|hi|hey|ok|yes|no|thanks|你好|好的|嗯)$',
        ]
        
        for pattern in trivial_patterns:
            if re.match(pattern, query.strip().lower()):
                return False
        
        # 3. 工具调用相关，不注入
        if query.startswith("/") or query.startswith("openclaw"):
            return False
        
        return True