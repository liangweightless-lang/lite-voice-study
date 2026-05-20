from abc import ABC, abstractmethod
from typing import AsyncGenerator
import asyncio

class BaseLLMProvider(ABC):
    """
    大模型驱动插件的抽象基类 (Base LLM Provider)
    所有扩展模型驱动（如 ChatGPT, DeepSeek, 各种开源私有LLM）都必须继承此类并实现抽象接口。
    """
    
    @abstractmethod
    async def generate_stream(
        self, 
        messages: list, 
        stop_event: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """
        以异步生成器模式流式获取大模型生成的增量文本块。
        
        :param messages: 标准的通用聊天上下文列表，如 [{'role': 'user', 'content': '...'}]
        :param stop_event: 话轮打断信号事件。一旦 stop_event.is_set() 为 True，驱动必须立即中止网络输出。
        :return: 异步生成器，依次 Yield 产生的增量字/词块 (str)。
        """
        pass
