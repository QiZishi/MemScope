"""
LLM Caller - LLM 调用器

支持多级降级：
1. 技能模型 (最高质量)
2. 摘要模型 (中等质量)
3. OpenClaw 原生模型 (最低质量)
"""

from typing import List, Dict, Any, Optional
import logging
import os
import json

logger = logging.getLogger(__name__)


class LLMCaller:
    """LLM 调用器，支持多级降级"""
    
    def __init__(
        self,
        skill_config: Optional[Dict[str, Any]] = None,
        summarizer_config: Optional[Dict[str, Any]] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        self.skill_config = skill_config
        self.summarizer_config = summarizer_config
        self.default_config = default_config
        
        # 降级链
        self.fallback_chain = [
            ("skill", skill_config),
            ("summarizer", summarizer_config),
            ("default", default_config),
        ]
    
    async def call(
        self,
        prompt: str,
        prefer_level: str = "skill",
    ) -> str:
        """
        调用 LLM
        
        Args:
            prompt: 输入 prompt
            prefer_level: 首选级别 (skill/summarizer/default)
            
        Returns:
            LLM 响应
        """
        # 根据首选级别调整降级链顺序
        chain = self._order_chain(prefer_level)
        
        # 尝试各级别
        for level, config in chain:
            if config:
                try:
                    response = await self._call_level(level, config, prompt)
                    if response:
                        logger.debug(f"LLM call succeeded at level {level}")
                        return response
                except Exception as e:
                    logger.warning(f"LLM call failed at level {level}: {e}")
        
        # 所有级别都失败
        logger.error("All LLM levels failed")
        return ""
    
    def _order_chain(
        self,
        prefer_level: str,
    ) -> List[tuple]:
        """根据首选级别排序降级链"""
        chain = []
        
        # 首选级别放第一位
        for level, config in self.fallback_chain:
            if level == prefer_level:
                chain.append((level, config))
        
        # 其他级别按原顺序
        for level, config in self.fallback_chain:
            if level != prefer_level and config:
                chain.append((level, config))
        
        return chain
    
    async def _call_level(
        self,
        level: str,
        config: Dict[str, Any],
        prompt: str,
    ) -> Optional[str]:
        """调用指定级别的 LLM"""
        provider = config.get("provider", "openai_compatible")
        
        if provider == "openai_compatible":
            return await self._call_openai_compatible(config, prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(config, prompt)
        elif provider == "openclaw_native":
            return await self._call_openclaw_native(config, prompt)
        else:
            logger.warning(f"Unknown provider: {provider}")
            return None
    
    async def _call_openai_compatible(
        self,
        config: Dict[str, Any],
        prompt: str,
    ) -> Optional[str]:
        """调用 OpenAI 兼容 API"""
        import aiohttp
        
        endpoint = config.get("endpoint", "https://api.openai.com/v1")
        api_key = config.get("apiKey", os.getenv("OPENAI_API_KEY", ""))
        model = config.get("model", "gpt-4o-mini")
        
        if not api_key:
            raise ValueError("No API key configured")
        
        url = f"{endpoint}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=60) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    raise ValueError(f"API error: {resp.status}")
    
    async def _call_anthropic(
        self,
        config: Dict[str, Any],
        prompt: str,
    ) -> Optional[str]:
        """调用 Anthropic API"""
        import aiohttp
        
        api_key = config.get("apiKey", os.getenv("ANTHROPIC_API_KEY", ""))
        model = config.get("model", "claude-3-sonnet-20240229")
        
        if not api_key:
            raise ValueError("No Anthropic API key")
        
        url = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=60) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["content"][0]["text"]
                else:
                    raise ValueError(f"Anthropic API error: {resp.status}")
    
    async def _call_openclaw_native(
        self,
        config: Dict[str, Any],
        prompt: str,
    ) -> Optional[str]:
        """调用 OpenClaw 原生模型（通过 Hermes API）"""
        # 这里假设 Hermes 有某种原生 API
        # 实际实现取决于 Hermes 的架构
        
        endpoint = config.get("endpoint", "http://localhost:8080/api/chat")
        
        import aiohttp
        
        data = {
            "message": prompt,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=data, timeout=120) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("response", "")
                else:
                    raise ValueError(f"OpenClaw native API error: {resp.status}")
    
    async def call_batch(
        self,
        prompts: List[str],
        prefer_level: str = "summarizer",
    ) -> List[str]:
        """批量调用 LLM — parallel via asyncio.gather"""
        import asyncio
        tasks = [self.call(prompt, prefer_level) for prompt in prompts]
        return await asyncio.gather(*tasks)