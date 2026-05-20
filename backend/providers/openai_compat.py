import asyncio
from typing import AsyncGenerator
from providers.base import BaseLLMProvider
from config.settings import settings, logger

class OpenAICompatProvider(BaseLLMProvider):
    """OpenAI / DeepSeek 通用兼容平台驱动实现 (异步引擎)"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL
        self.model_name = settings.OPENAI_MODEL_NAME
        self._client = None
        logger.debug("OpenAI 兼容驱动模块初始化完毕")

    def _get_client(self):
        """懒加载异步客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise RuntimeError("未检测到 openai 依赖包！请执行 ./start.sh 同步依赖环境")
            
            if not self.api_key or self.api_key == "your_openai_api_key_here":
                raise ValueError("缺少有效的 OPENAI_API_KEY，请检查 backend/.env 文件配置")
                
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    async def generate_stream(
        self, 
        messages: list, 
        stop_event: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """异步并发迭代请求"""
        logger.info(f"正在向 [OpenAI/DeepSeek 兼容平台] ({self.model_name}) 发出异步流式请求...")
        client = self._get_client()

        # 异步流式请求，充分释放事件循环挂起性能
        response_stream = await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True
        )

        async for chunk in response_stream:
            if stop_event.is_set():
                logger.info("捕获打断信号，优雅中止 [OpenAI/DeepSeek] 后续流式迭代")
                break
                
            if len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
