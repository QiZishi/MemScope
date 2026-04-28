"""
Chunker - 语义分块器

将对话内容分块，每块包含完整的语义单元
"""

from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class Chunker:
    """语义分块器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 配置
        self.max_chunk_size = self.config.get("max_chunk_size", 2000)
        self.min_chunk_size = self.config.get("min_chunk_size", 100)
        self.overlap_size = self.config.get("overlap_size", 50)
    
    def chunk_messages(
        self,
        messages: List[Dict[str, Any]],
        session_key: str,
    ) -> List[Dict[str, Any]]:
        """
        将消息列表分块
        
        Args:
            messages: 消息列表
            session_key: 会话 key
            
        Returns:
            分块列表
        """
        chunks = []
        
        # 按 turn 分组
        turns = self._group_by_turn(messages)
        
        for turn_idx, turn_messages in enumerate(turns):
            # 合并 turn 内容
            turn_content = self._merge_turn_content(turn_messages)
            
            if len(turn_content) < self.min_chunk_size:
                # 太短，合并到下一个 turn
                continue
            
            # 分块
            if len(turn_content) > self.max_chunk_size:
                # 需要分割
                sub_chunks = self._split_chunk(turn_content, self.max_chunk_size)
                
                for sub_idx, sub_content in enumerate(sub_chunks):
                    chunk = self._create_chunk(
                        sub_content,
                        session_key,
                        turn_messages[0],
                        turn_idx,
                        sub_idx,
                    )
                    chunks.append(chunk)
            else:
                # 单个块
                chunk = self._create_chunk(
                    turn_content,
                    session_key,
                    turn_messages[0],
                    turn_idx,
                    0,
                )
                chunks.append(chunk)
        
        return chunks
    
    def _group_by_turn(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        """按 turn 分组消息"""
        turns = []
        current_turn = []
        
        for msg in messages:
            role = msg.get("role", "")
            
            # user 开始新 turn
            if role == "user" and current_turn:
                turns.append(current_turn)
                current_turn = []
            
            current_turn.append(msg)
        
        # 最后一个 turn
        if current_turn:
            turns.append(current_turn)
        
        return turns
    
    def _merge_turn_content(
        self,
        turn_messages: List[Dict[str, Any]],
    ) -> str:
        """合并 turn 内容"""
        content_parts = []
        
        for msg in turn_messages:
            role = msg.get("role", "")
            msg_content = msg.get("content", "")
            
            if isinstance(msg_content, str):
                content_parts.append(f"[{role}] {msg_content}")
            elif isinstance(msg_content, list):
                for block in msg_content:
                    if block.get("type") == "text":
                        content_parts.append(f"[{role}] {block.get('text', '')}")
        
        return "\n".join(content_parts)
    
    def _split_chunk(
        self,
        content: str,
        max_size: int,
    ) -> List[str]:
        """分割大块"""
        chunks = []
        
        # 按句子分割
        sentences = re.split(r'([.!?。！？]\s*)', content)
        sentences = [s for s in sentences if s.strip()]
        
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > max_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _create_chunk(
        self,
        content: str,
        session_key: str,
        first_msg: Dict[str, Any],
        turn_idx: int,
        sub_idx: int,
    ) -> Dict[str, Any]:
        """创建分块"""
        import uuid
        
        chunk_id = str(uuid.uuid4())
        
        chunk = {
            "id": chunk_id,
            "session_key": session_key,
            "content": content,
            "summary": "",  # 后续由 LLM 生成
            "role": first_msg.get("role", "assistant"),
            "turn_id": first_msg.get("turnId", ""),
            "seq": turn_idx,
            "sub_seq": sub_idx,
            "createdAt": first_msg.get("timestamp", 0),
            "owner": "default",
            "visibility": "private",
        }
        
        return chunk