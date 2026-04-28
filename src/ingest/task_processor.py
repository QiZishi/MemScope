"""
Task Processor - 任务边界检测与摘要生成

检测任务边界：
1. Session 变更 → 新任务
2. 时间间隔 > 2h → 新任务
3. LLM 判断话题切换
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务处理器"""
    
    def __init__(self, store: Any, summarizer: Any, config: Optional[Dict[str, Any]] = None):
        self.store = store
        self.summarizer = summarizer
        self.config = config or {}
        
        # 配置
        self.time_gap_threshold = self.config.get("time_gap_threshold_hours", 2)
        self.on_task_completed_callback = None
    
    def on_task_completed(self, callback):
        """注册任务完成回调"""
        self.on_task_completed_callback = callback
    
    async def on_chunks_ingested(
        self,
        session_key: str,
        latest_timestamp: int,
        owner: str = "default",
    ):
        """
        新块摄入后调用，检测任务边界
        
        Args:
            session_key: 会话 key
            latest_timestamp: 最新时间戳
            owner: 所有者
        """
        logger.debug(f"TaskProcessor.on_chunks_ingested: session={session_key}, ts={latest_timestamp}")
        
        # 检查是否有活跃任务
        active_task = self.store.get_active_task(session_key, owner)
        
        if not active_task:
            # 创建新任务
            await self._create_new_task(session_key, latest_timestamp, owner)
        else:
            # 检查是否需要切换任务
            should_switch = await self._check_task_boundary(
                active_task,
                session_key,
                latest_timestamp,
                owner,
            )
            
            if should_switch:
                # 完成当前任务，创建新任务
                await self._finalize_task(active_task)
                await self._create_new_task(session_key, latest_timestamp, owner)
    
    async def _check_task_boundary(
        self,
        active_task: Dict[str, Any],
        session_key: str,
        latest_timestamp: int,
        owner: str,
    ) -> bool:
        """
        检查是否需要切换任务
        
        Returns:
            True 表示需要切换任务
        """
        # 1. Session 变更 → 新任务
        if active_task.get("session_key") != session_key:
            logger.info(f"Session changed: finalizing task={active_task.get('id')}")
            return True
        
        # 2. 时间间隔 > 2h → 新任务
        last_timestamp = active_task.get("latest_timestamp", 0)
        time_gap_hours = (latest_timestamp - last_timestamp) / (1000 * 60 * 60)
        
        if time_gap_hours > self.time_gap_threshold:
            logger.info(f"Time gap {time_gap_hours:.1f}h > {self.time_gap_threshold}h: new task")
            return True
        
        # 3. LLM 判断话题切换（可选，需要配置 summarizer）
        if self.summarizer:
            try:
                # 获取最近的对话内容
                recent_messages = self.store.get_recent_messages(session_key, limit=5)
                
                # LLM 判断是否话题切换
                is_new_topic = await self.summarizer.judge_topic_switch(
                    active_task.get("summary", ""),
                    recent_messages,
                )
                
                if is_new_topic:
                    logger.info(f"Topic switch detected: new task")
                    return True
            except Exception as e:
                logger.warning(f"Topic judgment failed: {e}")
        
        return False
    
    async def _create_new_task(
        self,
        session_key: str,
        latest_timestamp: int,
        owner: str,
    ):
        """创建新任务"""
        import uuid
        task_id = str(uuid.uuid4())
        
        task = {
            "id": task_id,
            "session_key": session_key,
            "owner": owner,
            "status": "active",
            "created_at": latest_timestamp,
            "latest_timestamp": latest_timestamp,
            "summary": "",
            "goal": "",
            "steps": [],
            "result": "",
        }
        
        self.store.create_task(task)
        logger.info(f"Created new task: {task_id}")
        
        return task
    
    async def _finalize_task(self, task: Dict[str, Any]):
        """
        完成当前任务，生成摘要
        
        Args:
            task: 任务字典
        """
        task_id = task.get("id")
        session_key = task.get("session_key")
        owner = task.get("owner")
        
        logger.info(f"Finalizing task: {task_id}")
        
        # 获取任务的所有对话内容
        messages = self.store.get_task_messages(task_id)
        
        if not messages:
            logger.warning(f"No messages for task {task_id}")
            return
        
        # 生成结构化摘要
        if self.summarizer:
            try:
                summary = await self.summarizer.summarize_task(messages)
                
                # 更新任务
                task["summary"] = summary.get("summary", "")
                task["goal"] = summary.get("goal", "")
                task["steps"] = summary.get("steps", [])
                task["result"] = summary.get("result", "")
                task["status"] = "completed"
                
                self.store.update_task(task)
                logger.info(f"Task {task_id} finalized with summary")
                
                # 回调
                if self.on_task_completed_callback:
                    self.on_task_completed_callback(task)
                    
            except Exception as e:
                logger.error(f"Task summarization failed: {e}")
                task["status"] = "completed"
                self.store.update_task(task)
        else:
            # 没有 summarizer，简单标记完成
            task["status"] = "completed"
            self.store.update_task(task)
            logger.info(f"Task {task_id} finalized (no summarizer)")
    
    async def generate_task_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        为指定任务生成摘要
        
        Args:
            task_id: 任务 ID
            
        Returns:
            摘要字典
        """
        task = self.store.get_task(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return None
        
        messages = self.store.get_task_messages(task_id)
        if not messages:
            return None
        
        if self.summarizer:
            summary = await self.summarizer.summarize_task(messages)
            
            task["summary"] = summary.get("summary", "")
            task["goal"] = summary.get("goal", "")
            task["steps"] = summary.get("steps", [])
            task["result"] = summary.get("result", "")
            
            self.store.update_task(task)
            return summary
        
        return None