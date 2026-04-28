"""
Summarizer - 摘要生成器

生成：
1. 记忆块摘要
2. 任务结构化摘要
3. 技能描述
"""

from typing import List, Dict, Any, Optional
import logging
import json
import re

logger = logging.getLogger(__name__)


# 记忆摘要 Prompt
MEMORY_SUMMARY_PROMPT = '''Summarize the following content into a concise summary (max 200 words).

Content:
{content}

Output ONLY the summary, no other text.
'''

# 任务摘要 Prompt
TASK_SUMMARY_PROMPT = '''Analyze the following conversation and generate a structured task summary.

Conversation:
{conversation}

Output a JSON object with:
{
  "summary": "Brief task summary (1-2 sentences)",
  "goal": "What the user wanted to achieve",
  "steps": ["Step 1", "Step 2", ...],
  "result": "Final outcome",
  "success": true/false
}

Output ONLY the JSON, no other text.
'''


class Summarizer:
    """摘要生成器"""
    
    def __init__(
        self,
        llm_caller: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.llm_caller = llm_caller
        self.config = config or {}
        
        # 配置
        self.max_summary_length = self.config.get("max_summary_length", 200)
    
    async def summarize_memory(
        self,
        content: str,
    ) -> str:
        """
        生成记忆摘要
        
        Args:
            content: 记忆内容
            
        Returns:
            摘要
        """
        if not content:
            return ""
        
        # 截断过长内容
        if len(content) > 1000:
            content = content[:1000] + "..."
        
        prompt = MEMORY_SUMMARY_PROMPT.format(content=content)
        
        try:
            summary = await self.llm_caller.call(prompt)
            summary = summary.strip()
            
            # 截断过长摘要
            if len(summary) > self.max_summary_length:
                summary = summary[:self.max_summary_length] + "..."
            
            return summary
            
        except Exception as e:
            logger.warning(f"Memory summarization failed: {e}")
            
            # 回退：提取第一句话
            first_sentence = re.split(r'[.!?。！？]', content)[0]
            if len(first_sentence) > self.max_summary_length:
                first_sentence = first_sentence[:self.max_summary_length]
            
            return first_sentence
    
    async def summarize_task(
        self,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成任务结构化摘要
        
        Args:
            messages: 对话消息列表
            
        Returns:
            摘要字典 {summary, goal, steps, result, success}
        """
        # 构建对话文本
        conversation = self._build_conversation_text(messages)
        
        prompt = TASK_SUMMARY_PROMPT.format(conversation=conversation)
        
        try:
            response = await self.llm_caller.call(prompt)
            
            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                summary = json.loads(json_match.group())
                return summary
            
        except Exception as e:
            logger.warning(f"Task summarization failed: {e}")
        
        # 回退：简单摘要
        return {
            "summary": "Task completed",
            "goal": "",
            "steps": [],
            "result": "",
            "success": True,
        }
    
    async def judge_topic_switch(
        self,
        previous_summary: str,
        recent_messages: List[Dict[str, Any]],
    ) -> bool:
        """
        判断话题是否切换
        
        Args:
            previous_summary: 之前任务摘要
            recent_messages: 最近消息
            
        Returns:
            True 表示话题切换
        """
        # 构建消息文本
        recent_text = self._build_conversation_text(recent_messages[-3:])
        
        prompt = f'''Compare the previous task with recent messages and determine if the topic has changed.

Previous task summary: {previous_summary}

Recent messages: {recent_text}

Answer with ONE word: SAME (same topic) or SWITCH (different topic)

Output ONLY the word, no explanation.
'''
        
        try:
            response = await self.llm_caller.call(prompt)
            response = response.strip().upper()
            
            return response == "SWITCH"
            
        except Exception as e:
            logger.warning(f"Topic judgment failed: {e}")
            return False
    
    async def filter_relevant(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[int]:
        """
        过滤相关候选
        
        Args:
            query: 查询
            candidates: 候选列表
            
        Returns:
            相关候选的索引列表
        """
        # 构建候选列表
        candidate_list = "\n".join([
            f"[{i}] {c.get('summary', c.get('description', ''))}"
            for i, c in enumerate(candidates)
        ])
        
        prompt = f'''Select the items relevant to the query.

Query: {query}

Items:
{candidate_list}

Output a JSON array of indices: [0, 2, 5, ...]

Output ONLY the array, no other text.
'''
        
        try:
            response = await self.llm_caller.call(prompt)
            
            # 解析 JSON
            json_match = re.search(r'\[[\d\s,]*\]', response)
            if json_match:
                indices = json.loads(json_match.group())
                return indices
            
        except Exception as e:
            logger.warning(f"Relevance filtering failed: {e}")
        
        # 回退：返回所有
        return list(range(len(candidates)))
    
    def _build_conversation_text(
        self,
        messages: List[Dict[str, Any]],
    ) -> str:
        """构建对话文本"""
        lines = []
        
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if isinstance(content, str):
                if len(content) > 300:
                    content = content[:300] + "..."
                lines.append(f"[{role}] {content}")
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        if len(text) > 300:
                            text = text[:300] + "..."
                        lines.append(f"[{role}] {text}")
        
        return "\n".join(lines)