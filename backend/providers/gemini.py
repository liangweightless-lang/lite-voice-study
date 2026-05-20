import os
import asyncio
from typing import AsyncGenerator
from providers.base import BaseLLMProvider
from config.settings import settings, logger

class GeminiProvider(BaseLLMProvider):
    """谷歌官方 Gemini 大模型驱动实现"""
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = 'gemini-2.5-flash'
        self._client = None
        logger.debug("谷歌 Gemini 大模型驱动初始化完毕")

    def _get_client(self):
        """懒加载客户端，防止在未配置秘钥时在导入阶段报错"""
        if self._client is None:
            try:
                from google import genai
            except ImportError:
                raise RuntimeError("未检测到 google-genai 库！请执行 ./start.sh 同步依赖环境")
            
            if not self.api_key or self.api_key == "your_gemini_api_key_here":
                raise ValueError("缺少有效的 GEMINI_API_KEY，请检查 backend/.env 文件配置")
                
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_stream(
        self, 
        messages: list, 
        stop_event: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """流式请求 Gemini 2.5 Flash"""
        from google.genai import types
        
        logger.info(f"正在向 [谷歌 Gemini] 发出流式生成请求...")
        client = self._get_client()

        # 智能翻译通用聊天格式为 Gemini 专有格式
        contents = []
        system_instruction = "你是一个人工智能语音助手，你的回答要非常简洁、口语化，不要超过50字。"
        
        for m in messages:
            role = m.get('role')
            content = m.get('content', '')
            if role == 'system':
                system_instruction = content
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=content)]
                    )
                )
        
        if not contents:
            contents = [types.Content(role="user", parts=[types.Part.from_text(text="你好")])]

        # 发送请求
        responses = client.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

        for chunk in responses:
            if stop_event.is_set():
                logger.info("捕获打断信号，优雅中止 [谷歌 Gemini] 后续输出")
                break
                
            if chunk.text:
                yield chunk.text
                
            await asyncio.sleep(0.005)
