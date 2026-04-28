"""
Skill Evolver - 技能进化器

管理技能的生命周期：
1. 创建新技能
2. 升级现有技能
3. 验证技能质量
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import json
import re

logger = logging.getLogger(__name__)


class SkillEvolver:
    """技能进化器"""
    
    def __init__(
        self,
        store: Any,
        generator: Any,
        evaluator: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.store = store
        self.generator = generator
        self.evaluator = evaluator
        self.config = config or {}
    
    async def evolve_from_task(
        self,
        task: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        从任务进化技能
        
        Args:
            task: 任务字典
            messages: 对话消息
            
        Returns:
            生成的技能
        """
        # 1. 评估是否应该生成技能
        should_generate = await self.evaluator.evaluate_task(task)
        
        if not should_generate.get("should_generate"):
            logger.info(f"Task {task.get('id')} skipped: {should_generate.get('reason')}")
            return None
        
        # 2. 检查是否有相似技能需要升级
        similar_skill = self._find_similar_skill(task)
        
        if similar_skill:
            # 升级现有技能
            return await self._upgrade_skill(similar_skill, task, messages)
        else:
            # 生成新技能
            return await self.generator.generate_skill(task, messages)
    
    def _find_similar_skill(
        self,
        task: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """查找相似技能"""
        summary = task.get("summary", "")
        if not summary:
            return None
        
        skills = self.store.search_skills(summary, limit=5)
        
        for skill in skills:
            desc = skill.get("description", "")
            # 简单相似度检查
            if self._compute_overlap(summary, desc) > 0.3:
                return skill
        
        return None
    
    def _compute_overlap(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """计算文本重叠度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        min_size = min(len(words1), len(words2))
        
        return len(intersection) / min_size
    
    async def _upgrade_skill(
        self,
        existing_skill: Dict[str, Any],
        task: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        升级现有技能
        
        Args:
            existing_skill: 现有技能
            task: 新任务
            messages: 对话消息
            
        Returns:
            升级后的技能
        """
        skill_id = existing_skill.get("id")
        
        # 构建升级 prompt
        upgrade_prompt = f'''Upgrade the existing skill based on new task experience.

Existing skill:
Name: {existing_skill.get('name')}
Description: {existing_skill.get('description')}
Content: {existing_skill.get('content')}

New task:
Summary: {task.get('summary')}
Steps: {task.get('steps')}
Result: {task.get('result')}

Output an upgraded SKILL.md with:
- Updated description (add new trigger scenarios)
- Additional steps (from new task)
- New pitfalls discovered
- Updated code/config (if any)

Output ONLY the complete SKILL.md content.
'''
        
        try:
            new_content = await self.generator.llm_caller.call(upgrade_prompt)
            
            # 解析新技能
            new_skill = self.generator._parse_skill_md(new_content, task.get("id"))
            
            if new_skill:
                # 更新版本
                new_skill["id"] = skill_id
                new_skill["version"] = existing_skill.get("version", 1) + 1
                new_skill["updated_at"] = datetime.now().isoformat()
                new_skill["upgrade_history"] = existing_skill.get("upgrade_history", []) + [
                    {
                        "task_id": task.get("id"),
                        "timestamp": datetime.now().isoformat(),
                    }
                ]
                
                # 存储更新
                self.store.update_skill(new_skill)
                logger.info(f"Skill {skill_id} upgraded to version {new_skill.get('version')}")
                
                return new_skill
            
        except Exception as e:
            logger.error(f"Skill upgrade failed: {e}")
        
        return existing_skill
    
    async def batch_evolve(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        批量进化技能
        
        Args:
            tasks: 任务列表
            
        Returns:
            生成的技能列表
        """
        generated_skills = []
        
        for task in tasks:
            messages = self.store.get_task_messages(task.get("id"))
            
            skill = await self.evolve_from_task(task, messages)
            
            if skill:
                generated_skills.append(skill)
        
        return generated_skills