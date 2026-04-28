"""
Skill Evaluator - 技能评估器

评估任务是否适合生成技能：
1. 是否可重复？
2. 是否有价值？
3. 是否足够复杂？
"""

from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


# 评估 Prompt
EVALUATION_PROMPT = '''Evaluate whether this task should generate a reusable skill.

## Criteria

A skill should be generated if:
1. **Repeatable**: The task can be applied to similar future scenarios (not one-time)
2. **Valuable**: The task provides meaningful value (not trivial like "hello")
3. **Complex**: The task involves multiple steps or decisions (not simple)
4. **Novel**: The task is not already covered by existing skills

## Task

Task summary: {summary}
Task goal: {goal}
Task steps: {steps}
Task result: {result}

## Output

Answer with a JSON object:
{
  "should_generate": true/false,
  "reason": "brief explanation",
  "confidence": 0.0-1.0
}

Output ONLY the JSON, no other text.
'''


# 简单任务模式（不生成技能）
TRIVIAL_PATTERNS = [
    r'^(test|testing|hello|hi|hey|ok|okay|yes|no|yeah|nope|sure|thanks|thank you|thx|ping|pong|哈哈|好的|嗯|是的|不是|谢谢|你好|测试)\s*[.!?。！？]*$',
    r'^[\s\p{P}\p{S}]*$',
]


class SkillEvaluator:
    """技能评估器"""
    
    def __init__(
        self,
        store: Any,
        llm_caller: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.store = store
        self.llm_caller = llm_caller
        self.config = config or {}
    
    def should_generate_skill(
        self,
        task: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> bool:
        """
        快速判断是否应该生成技能
        
        Args:
            task: 任务字典
            messages: 对话消息
            
        Returns:
            True 表示应该生成技能
        """
        # 1. 检查简单模式
        if self._is_trivial_task(messages):
            logger.debug(f"Task {task.get('id')} is trivial, skip skill generation")
            return False
        
        # 2. 检查任务复杂度
        steps = task.get("steps", [])
        if len(steps) < 2:
            logger.debug(f"Task {task.get('id')} has < 2 steps, skip skill generation")
            return False
        
        # 3. 检查是否已有类似技能
        if self._has_similar_skill(task):
            logger.debug(f"Task {task.get('id')} has similar skill, skip")
            return False
        
        return True
    
    async def evaluate_task(
        self,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        详细评估任务
        
        Args:
            task: 任务字典
            
        Returns:
            评估结果 {should_generate, reason, confidence}
        """
        # 快速检查
        if not self.should_generate_skill(task, []):
            return {
                "should_generate": False,
                "reason": "Task is trivial or too simple",
                "confidence": 0.9,
            }
        
        # LLM 详细评估
        prompt = EVALUATION_PROMPT.format(
            summary=task.get("summary", ""),
            goal=task.get("goal", ""),
            steps=str(task.get("steps", [])),
            result=task.get("result", ""),
        )
        
        try:
            response = await self.llm_caller.call(prompt)
            
            # 解析 JSON
            import json
            # 提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                return result
            
        except Exception as e:
            logger.warning(f"Evaluation LLM call failed: {e}")
        
        # 默认：生成技能
        return {
            "should_generate": True,
            "reason": "LLM evaluation failed, default to generate",
            "confidence": 0.5,
        }
    
    def _is_trivial_task(self, messages: List[Dict[str, Any]]) -> bool:
        """检查是否是简单任务"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                for pattern in TRIVIAL_PATTERNS:
                    if re.match(pattern, content, re.IGNORECASE):
                        return True
        return False
    
    def _has_similar_skill(self, task: Dict[str, Any]) -> bool:
        """检查是否已有类似技能"""
        # 搜索相似技能
        summary = task.get("summary", "")
        if not summary:
            return False
        
        similar_skills = self.store.search_skills(summary, limit=5)
        
        for skill in similar_skills:
            # 检查相似度
            skill_desc = skill.get("description", "")
            if self._compute_similarity(summary, skill_desc) > 0.8:
                return True
        
        return False
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单实现）"""
        # 使用 Jaccard 相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)