from providers.base import BaseLLMProvider
from providers.qwen import QwenProvider
from providers.gemini import GeminiProvider
from providers.openai_compat import OpenAICompatProvider
from config.settings import settings, logger

class LLMFactory:
    """动态驱动管理器工厂 (Hot-Swappable LLM Driver Factory)"""
    
    @staticmethod
    def get_provider() -> BaseLLMProvider:
        """
        根据全局配置中的 LLM_PROVIDER 返回相应的大模型驱动实例。
        如果需要增加第三方服务，只需在此处注册对应的新类即可。
        """
        provider_name = settings.LLM_PROVIDER
        logger.info(f"🧩 模型工厂正在匹配驱动，当前目标: {provider_name.upper()}")
        
        if provider_name == 'qwen':
            return QwenProvider()
        elif provider_name == 'gemini':
            return GeminiProvider()
        elif provider_name == 'openai':
            return OpenAICompatProvider()
        else:
            logger.warning(f"⚠️ 未知的提供商 '{provider_name}'，自动降级回 [通义千问] 驱动")
            return QwenProvider()
