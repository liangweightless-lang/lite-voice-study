import os
import logging
from dotenv import load_dotenv

# 加载 .env 配置文件
load_dotenv()

class Settings:
    """企业级集中式配置类"""
    
    # 阿里云 DashScope ASR / TTS 秘钥
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    
    # 当前大模型供应商选择 (qwen / gemini / openai)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "qwen").lower()
    
    # 谷歌 Gemini API 密钥
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # OpenAI 及 DeepSeek 平台通用 API 密钥及配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    
    # WebSocket 监听端口及地址 (云服务器会动态分配 PORT，通过环境变量做高兼容性读取)
    SERVER_HOST: str = os.getenv("VOICE_SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("PORT", os.getenv("VOICE_SERVER_PORT", "9090")))
    
    # 全局日志级别
    LOG_LEVEL: str = os.getenv("VOICE_SERVER_LOG_LEVEL", "INFO").upper()

# 实例化全局配置对象
settings = Settings()

def init_logging() -> logging.Logger:
    """初始化微服务统一的日志管理器"""
    logger = logging.getLogger("voice_agent")
    
    # 如果已经有 handler，避免重复配置
    if not logger.handlers:
        level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
        logger.setLevel(level)
        
        # 终端标准输出流格式
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 调低三方库(如 websockets) 的杂碎日志级别
        logging.getLogger("websockets").setLevel(logging.WARNING)
        
        logger.info(f"🚀 企业级微服务日志初始化成功，日志级别: {settings.LOG_LEVEL}")
        
    return logger

# 全局共享 Logger 句柄
logger = init_logging()
