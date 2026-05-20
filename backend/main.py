#!/usr/bin/env python3
import asyncio
import websockets
import dashscope
from config.settings import settings, logger
from routers.voice import VoiceAgentRouter

"""
Lite Voice Study - 企业级语音实时流式交互微服务启动器

职责：
1. 校验核心环境及 DASHSCOPE_API_KEY；
2. 绑定统一的 IP 与端口监听；
3. 将每个 WebSocket 连接安全派发给 Session Router 话轮管理器。
"""

def check_environment():
    """检测基础环境变量与 Key 的有效性 (支持无秘钥纯文字降级启动)"""
    key = settings.DASHSCOPE_API_KEY
    if not key or key == "your_dashscope_api_key_here":
        logger.warning("=================================================================")
        logger.warning("⚠️  [提示] 未检测到有效的 DASHSCOPE_API_KEY！语音识别 (ASR) 与合成 (TTS) 服务已停用。")
        logger.warning("👉 服务端已自动切换至 [纯文本流式对话模式]！")
        logger.warning("如果您配置了 GEMINI_API_KEY 或 OPENAI_API_KEY，您仍然可以通过文字顺畅交流。")
        logger.warning("=================================================================")
        dashscope.api_key = ""
        return True
    
    # 赋值全局 SDK Key
    dashscope.api_key = key
    logger.info("✔ 阿里云 DashScope SDK 基础 API-KEY 校验通过")
    logger.info(f"🧩 默认激活大模型供应商: [{settings.LLM_PROVIDER.upper()}]")
    return True


async def main():
    # 1. 运行前环境自检
    if not check_environment():
        return

    # 2. 实例化企业级长连接控制器
    session_router = VoiceAgentRouter()

    # 3. 启动端口监听
    host = settings.SERVER_HOST
    port = settings.SERVER_PORT
    
    logger.info(f"正在建立服务端 Socket 监听，绑定地址: {host}:{port}...")
    
    # 用 websockets.serve 安全包裹会话处理器
    async with websockets.serve(session_router.handle_session, host, port):
        logger.info(f"🎉 语音交互服务成功启动！WebSocket 服务正在监听地址: ws://{host}:{port}")
        # 挂起当前 Future，防止程序退出
        await asyncio.Future()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 服务端已被用户手动安全关闭")
