import asyncio
from typing import AsyncGenerator
from dashscope import Generation
from providers.base import BaseLLMProvider
from config.settings import logger

class QwenProvider(BaseLLMProvider):
    """通义千问大模型驱动实现"""
    
    def __init__(self):
        self.model_name = 'qwen-plus'
        logger.debug("通义千问大模型驱动初始化完毕")

    async def generate_stream(
        self, 
        messages: list, 
        stop_event: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """流式请求 Qwen 模型"""
        logger.info(f"正在向 [通义千问] 发出流式生成请求...")
        
        # 阿里云官方 SDK 目前是一个同步流式阻断对象，我们通过标准迭代并随时响应打断
        responses = Generation.call(
            model=self.model_name,
            messages=messages,
            result_format='message',
            stream=True,
            incremental_output=True,
        )

        for response in responses:
            # 随时检查网页端下发的开口说话打断信号
            if stop_event.is_set():
                logger.info("捕获打断信号，优雅中止 [通义千问] 的后续流式输出")
                break
            
            if response.status_code == 200:
                content = response.output.choices[0]['message']['content']
                if content:
                    yield content
            else:
                logger.error(f"[通义千问] 流式生成错误: {response.message} (代码: {response.status_code})")
                break
            
            # 微小休眠以让出 CPU 时间片，确保事件循环流畅
            await asyncio.sleep(0.005)
