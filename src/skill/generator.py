"""
Skill Generator - 技能生成器

从完成的任务中提取可复用经验，生成 SKILL.md 文件

遵循 Anthropic skill-creator 原则：
- 渐进式披露 (metadata ~100 words → body <500 lines → resources on demand)
- Description as primary trigger mechanism
- Explain WHY, not pile up MUST/NEVER
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


# Skill 生成 Prompt
SKILL_GENERATION_PROMPT = '''You are a Skill creation expert. Your job is to distill a completed task's execution record into a reusable SKILL.md file.

This Skill is special: it comes from real execution experience — every step was actually run, every pitfall was actually encountered and resolved.

## Core principles (follow strictly but do NOT include these in output)

### Progressive disclosure
- The frontmatter description (~100 words) is ALWAYS in the agent's context — it must be self-sufficient for deciding whether to use this skill.
- The SKILL.md body loads when triggered — keep it under 400 lines, focused, no fluff.

### Description as trigger mechanism
The description field decides whether the agent activates this skill. Write it "proactively":
- Don't just say what it does — list the situations, keywords, and phrasings that should trigger it.
- Bad: "How to deploy Node.js to Docker"
- Good: "How to containerize and deploy a Node.js application using Docker. Use when the user mentions Docker deployment, Dockerfile writing, container builds, multi-stage builds, port mapping, .dockerignore, image optimization, CI/CD container pipelines, or any task involving packaging a Node/JS backend into a container."

### Writing style
- Use imperative form
- Explain WHY for each step, not just HOW
- Generalize from the specific task so the skill works for similar future scenarios

### Language matching (CRITICAL)
You MUST write the ENTIRE skill in the SAME language as the user's messages in the task record.
- If the user wrote in Chinese → the skill title, description, all prose sections MUST be in Chinese
- If the user wrote in English → write in English

## Output format

Output ONLY the complete SKILL.md content. No extra text before or after.

---
name: "{NAME}"
description: "{A natural, proactive description. 60-120 words. Cover what it does + multiple phrasings/scenarios that should trigger it.}"
metadata: {{ "openclaw": {{ "emoji": "{emoji}" }} }}
---

# {Title — clear, action-oriented}

{One sentence: what this skill helps you do and why it's valuable}

## When to use this skill
{2-4 bullet points describing the scenarios}

## Steps
{Numbered steps extracted from the task}

## Pitfalls and solutions
{What went wrong during the task and how it was fixed}

## Key code and configuration
{Complete, verified code blocks and config files}

## Environment and prerequisites
{Versions, dependencies, permissions, OS requirements}

## Task record
Task title: {TITLE}
Task summary:
{SUMMARY}
'''


class SkillGenerator:
    """技能生成器"""
    
    def __init__(
        self,
        store: Any,
        llm_caller: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.store = store
        self.llm_caller = llm_caller
        self.config = config or {}
    
    async def generate_skill(
        self,
        task: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        从任务生成技能
        
        Args:
            task: 任务字典
            messages: 对话消息列表
            
        Returns:
            生成的技能字典
        """
        task_id = task.get("id")
        task_summary = task.get("summary", "")
        task_goal = task.get("goal", "")
        task_steps = task.get("steps", [])
        task_result = task.get("result", "")
        
        # 构建任务记录
        task_record = self._build_task_record(task, messages)
        
        # 检测用户语言
        user_language = self._detect_language(messages)
        
        # 构建 prompt
        prompt = self._build_prompt(task_record, user_language)
        
        # 调用 LLM 生成 SKILL.md
        try:
            skill_md = await self.llm_caller.call(prompt)
            
            # 解析 SKILL.md
            skill = self._parse_skill_md(skill_md, task_id)
            
            if skill:
                # 存储技能
                self.store.create_skill(skill)
                logger.info(f"Generated skill: {skill.get('name')}")
                return skill
            
        except Exception as e:
            logger.error(f"Skill generation failed: {e}")
        
        return None
    
    def _build_task_record(
        self,
        task: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> str:
        """构建任务记录字符串"""
        record = f"Task ID: {task.get('id')}\n"
        record += f"Task Goal: {task.get('goal', 'N/A')}\n"
        record += f"Task Summary: {task.get('summary', 'N/A')}\n"
        record += f"Task Steps:\n"
        
        for i, step in enumerate(task.get("steps", [])):
            record += f"  {i+1}. {step}\n"
        
        record += f"Task Result: {task.get('result', 'N/A')}\n"
        record += "\n--- Conversation ---\n"
        
        for msg in messages[-20:]:  # 只取最后 20 条消息
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
            record += f"[{role}] {content}\n\n"
        
        return record
    
    def _detect_language(self, messages: List[Dict[str, Any]]) -> str:
        """检测用户语言"""
        # 统计用户消息中的中文字符比例
        chinese_count = 0
        total_count = 0
        
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
                chinese_count += chinese_chars
                total_count += len(content)
        
        if total_count == 0:
            return "en"
        
        chinese_ratio = chinese_count / total_count
        
        if chinese_ratio > 0.3:
            return "zh"
        else:
            return "en"
    
    def _build_prompt(self, task_record: str, language: str) -> str:
        """构建生成 prompt"""
        prompt = SKILL_GENERATION_PROMPT
        prompt += f"\n\n## Input\n\n{task_record}\n\n## Language\n\nUse {language} for all prose sections."
        return prompt
    
    def _parse_skill_md(
        self,
        skill_md: str,
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        """解析 SKILL.md 内容"""
        import uuid
        
        try:
            # 提取 frontmatter
            frontmatter_match = re.match(
                r'^---\n(.*?)\n---\n(.*)$',
                skill_md,
                re.DOTALL
            )
            
            if not frontmatter_match:
                logger.warning("Invalid SKILL.md format: no frontmatter")
                return None
            
            frontmatter_text = frontmatter_match.group(1)
            body = frontmatter_match.group(2)
            
            # 解析 frontmatter
            name_match = re.search(r'name:\s*["\']?([^"\\'\\n]+)["\']?', frontmatter_text)
            desc_match = re.search(r'description:\s*["\'](.+?)["\']', frontmatter_text, re.DOTALL)
            
            if not name_match:
                logger.warning("Invalid SKILL.md: missing name")
                return None
            
            name = name_match.group(1).strip()
            description = desc_match.group(1).strip() if desc_match else ""
            
            # 生成技能 ID
            skill_id = str(uuid.uuid4())
            
            skill = {
                "id": skill_id,
                "name": name,
                "description": description,
                "content": body,
                "task_id": task_id,
                "owner": "default",
                "visibility": "private",
                "score": 0.8,
                "created_at": datetime.now().isoformat(),
                "version": 1,
            }
            
            return skill
            
        except Exception as e:
            logger.error(f"Failed to parse SKILL.md: {e}")
            return None