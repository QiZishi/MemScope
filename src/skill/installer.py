"""
Skill Installer - 技能安装器

将技能安装到工作区：
1. 创建 SKILL.md 文件
2. 创建 scripts/ 目录（如果有）
3. 创建 references/ 目录（如果有）
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import os
import re

logger = logging.getLogger(__name__)


class SkillInstaller:
    """技能安装器"""
    
    def __init__(
        self,
        workspace_path: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.workspace_path = workspace_path
        self.config = config or {}
    
    def install_skill(
        self,
        skill: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        安装技能到工作区
        
        Args:
            skill: 技能字典
            
        Returns:
            安装结果 {success, path, error}
        """
        skill_name = skill.get("name", "unnamed-skill")
        skill_content = skill.get("content", "")
        
        # 清理名称
        safe_name = self._sanitize_name(skill_name)
        
        # 创建技能目录
        skill_dir = os.path.join(self.workspace_path, "skills", safe_name)
        
        try:
            os.makedirs(skill_dir, exist_ok=True)
            
            # 写入 SKILL.md
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            
            # 构建完整 SKILL.md 内容
            full_content = self._build_skill_md(skill)
            
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            
            # 创建 scripts 目录
            scripts_dir = os.path.join(skill_dir, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            
            # 创建 references 目录
            references_dir = os.path.join(skill_dir, "references")
            os.makedirs(references_dir, exist_ok=True)
            
            # 提取并写入脚本（如果有）
            scripts = self._extract_scripts(skill_content)
            for script_name, script_content in scripts.items():
                script_path = os.path.join(scripts_dir, script_name)
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script_content)
            
            logger.info(f"Skill installed: {skill_dir}")
            
            return {
                "success": True,
                "path": skill_dir,
                "skill_md": skill_md_path,
            }
            
        except Exception as e:
            logger.error(f"Skill installation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def uninstall_skill(
        self,
        skill_name: str,
    ) -> Dict[str, Any]:
        """
        卸载技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            卸载结果
        """
        safe_name = self._sanitize_name(skill_name)
        skill_dir = os.path.join(self.workspace_path, "skills", safe_name)
        
        try:
            import shutil
            if os.path.exists(skill_dir):
                shutil.rmtree(skill_dir)
                logger.info(f"Skill uninstalled: {skill_dir}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Skill uninstall failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _sanitize_name(
        self,
        name: str,
    ) -> str:
        """清理技能名称"""
        # 移除特殊字符
        safe = re.sub(r'[^\w\-]', '-', name.lower())
        # 移除多余连字符
        safe = re.sub(r'-+', '-', safe)
        # 截断
        safe = safe[:50]
        return safe
    
    def _build_skill_md(
        self,
        skill: Dict[str, Any],
    ) -> str:
        """构建完整的 SKILL.md 内容"""
        frontmatter = f'''---
name: "{skill.get('name')}"
description: "{skill.get('description')}"
metadata:
  openclaw:
    emoji: "✨"
    version: {skill.get('version', 1)}
    created: {skill.get('created_at', datetime.now().isoformat())}
    task_id: {skill.get('task_id', '')}
---
'''
        
        body = skill.get("content", "")
        
        return frontmatter + "\n" + body
    
    def _extract_scripts(
        self,
        content: str,
    ) -> Dict[str, str]:
        """从内容中提取脚本"""
        scripts = {}
        
        # 提取代码块
        code_blocks = re.findall(
            r'```(\w+)\n([\s\S]*?)```',
            content
        )
        
        for i, (lang, code) in enumerate(code_blocks):
            # 根据语言生成文件名
            if lang in ["bash", "shell", "sh"]:
                ext = ".sh"
            elif lang in ["python", "py"]:
                ext = ".py"
            elif lang in ["javascript", "js"]:
                ext = ".js"
            elif lang in ["typescript", "ts"]:
                ext = ".ts"
            else:
                ext = f".{lang}"
            
            script_name = f"script_{i+1}{ext}"
            scripts[script_name] = code
        
        return scripts
    
    def list_installed_skills(
        self,
    ) -> List[str]:
        """列出已安装的技能"""
        skills_dir = os.path.join(self.workspace_path, "skills")
        
        if not os.path.exists(skills_dir):
            return []
        
        skills = []
        for name in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, name)
            skill_md = os.path.join(skill_path, "SKILL.md")
            
            if os.path.isfile(skill_md):
                skills.append(name)
        
        return skills