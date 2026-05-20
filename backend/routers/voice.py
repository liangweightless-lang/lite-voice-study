import json
import asyncio
import websockets
from config.settings import logger
from core.asr import ASRService
from core.tts import TTSService
from providers.factory import LLMFactory

async def run_llm_tts_pipeline(
    payload, 
    websocket, 
    stop_event: asyncio.Event
):
    """
    流式对接协调管道（ASR 文本 ➔ LLM 大模型生成 ➔ TTS 实时合成音频并推送）
    """
    loop = asyncio.get_event_loop()
    
    # 1. 动态通过工厂生成当前配置的模型驱动插件
    try:
        llm_provider = LLMFactory.get_provider()
    except Exception as e:
        logger.error(f"大模型驱动加载失败: {e}")
        await websocket.send(f"错误: 无法加载模型驱动插件 ({e})")
        await websocket.send("tts stopped")
        return

    # 2. 挂载实时流式 TTS 引擎
    tts_service = TTSService(websocket, loop)
    tts_service.start()

    # 3. 规范化通用上下文
    messages = []
    if isinstance(payload, str):
        messages = [{'role': 'user', 'content': payload}]
    elif isinstance(payload, list):
        for m in payload:
            role = m.get('role')
            content = m.get('content')
            if role and content:
                messages.append({'role': role, 'content': content})
    else:
        messages = [{'role': 'user', 'content': ''}]

    cancelled = False
    try:
        # 4. 驱动多模型统一异步流生成
        async for text_chunk in llm_provider.generate_stream(messages, stop_event):
            # 随时检测用户强行打断事件
            if stop_event.is_set():
                cancelled = True
                logger.info("⚡ 业务调度捕获打断事件，停止推文")
                break
            
            # 向前端实时下发增量文字 (直接 await，高能保序，防协程暴风与乱序)
            await websocket.send(text_chunk)
            
            # 将增量文字送入 TTS 缓冲池
            tts_service.feed_text(text_chunk, stop_event)
            await asyncio.sleep(0.005)
            
    except asyncio.CancelledError:
        cancelled = True
        logger.info("❌ 异步调度流水线被取消")
    except Exception as e:
        logger.exception(f"💥 调度管道运行中发生异常: {e}")
    finally:
        # 5. 尾部音频收尾并通知结束
        if not cancelled:
            tts_service.finish_remaining(stop_event)
            tts_service.complete_streaming()
            
            # 等待底层音频硬件线程合成全部输出完毕
            await tts_service.wait_for_completion()
            await websocket.send('tts stopped')
            logger.info("✔ 业务流水线流式合成闭环结束")
        else:
            tts_service.complete_streaming()


async def run_static_tts_pipeline(
    text: str, 
    websocket, 
    stop_event: asyncio.Event
):
    """
    静态文字一键流式合成管道 (如用于催促引导语)
    """
    loop = asyncio.get_event_loop()
    safe_text = str(text or '').strip()
    if not safe_text:
        await websocket.send('')
        await websocket.send('tts stopped')
        return

    # 直接挂载 TTS 播放驱动
    tts_service = TTSService(websocket, loop)
    tts_service.start()

    try:
        # 先下发纯字片
        await websocket.send(safe_text)
        if stop_event.is_set():
            return
            
        # 整个刷入合成
        tts_service.feed_text(safe_text, stop_event)
        tts_service.finish_remaining(stop_event)
        tts_service.complete_streaming()
        
        # 挂起等待合成结束
        await tts_service.wait_for_completion()
        await websocket.send('tts stopped')
        logger.info(f"静态合成播音完毕，字数: {len(safe_text)}")
    except asyncio.CancelledError:
        logger.info("❌ 静态文字合成被打断")
        tts_service.complete_streaming()


class VoiceAgentRouter:
    """企业级长连接路由与状态管理器 (Session Agent Gateway)"""
    
    def __init__(self):
        # 异步大模型合成主句柄
        self.active_task = None
        # 物理强打断标记信号量
        self.stop_event = asyncio.Event()

    async def _safe_send(self, websocket, msg: str):
        try:
            await websocket.send(msg)
        except Exception:
            pass

    async def handle_session(self, websocket):
        """
        WebSocket 通话生命周期控制器
        """
        loop = asyncio.get_event_loop()
        
        # 1. 动态挂载专属的 ASR 麦克风识别服务
        asr_service = ASRService(websocket, loop)
        asr_service.start()

        logger.info("🌐 新客户端接入微服务网关，状态初始化就绪")

        try:
            while True:
                data = await websocket.recv()
                
                # A. 客户端实时音频帧：推送至 ASR
                if isinstance(data, bytes):
                    asr_service.send_audio_frame(data)
                    logger.debug(f"接收二进制音频帧: {len(data)} 字节")
                
                # B. 客户端控制指令：
                elif isinstance(data, str):
                    if data == 'stop':
                        logger.info("网页端发出挂断信号，主动退出交互")
                        break
                    
                    try:
                        obj = json.loads(data)
                        if not isinstance(obj, dict):
                            continue
                        
                        msg_type = obj.get('type')
                        
                        # 核心场景一：VAD 静默窗口计时到了，请求大模型和流式合成
                        if msg_type == 'llm_tts':
                            payload = obj.get('messages') or str(obj.get('text') or '')
                            
                            # 极致打断：如果前面还在播音或生成，强行取消并阻断
                            if self.active_task and not self.active_task.done():
                                self.stop_event.set()
                                self.active_task.cancel()
                                logger.info("⚡ 捕获新请求，强行阻断前一句话的生成与播音")
                            
                            self.stop_event.clear()
                            self.active_task = loop.create_task(
                                run_llm_tts_pipeline(payload, websocket, self.stop_event)
                            )
                            
                        # 核心场景二：静态催促 TTS
                        elif msg_type == 'tts_text':
                            text = str(obj.get('text') or '')
                            if text:
                                if self.active_task and not self.active_task.done():
                                    self.stop_event.set()
                                    self.active_task.cancel()
                                self.stop_event.clear()
                                self.active_task = loop.create_task(
                                    run_static_tts_pipeline(text, websocket, self.stop_event)
                                )
                        
                        # 核心场景三：VAD 强打断（检测到用户突然发声或掐断）
                        elif msg_type == 'stop_tts':
                            if self.active_task and not self.active_task.done():
                                self.stop_event.set()
                                self.active_task.cancel()
                                logger.info("⚡ 捕获开口强打断信令，已对后台大模型与语音合成流进行物理截断")
                            self.active_task = None
                            await self._safe_send(websocket, 'tts stopped')
                            
                    except json.JSONDecodeError:
                        logger.warning(f"接收到未规范化的非 JSON 控制文本: {data[:80]}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 网页端 WebSocket 连接正常断开")
        except Exception as e:
            logger.exception(f"💥 网关内部处理用户请求时发生异常: {e}")
        finally:
            logger.info("🧹 连接生命周期结束，正在执行系统资源注销...")
            
            # 关闭 ASR
            asr_service.stop()
            await asr_service.wait_for_all_events()
            
            # 关闭当前未完成的任务
            if self.active_task and not self.active_task.done():
                self.active_task.cancel()
                
            await self._safe_send(websocket, 'asr stopped')
            logger.info("✨ 会话上下文与物理硬件链接销毁完成")
