import json
import asyncio
import dashscope
from dashscope.audio.asr import *
from config.settings import settings, logger

class ASRCallback(RecognitionCallback):
    """
    ASR (实时识别服务) 回调类
    接收阿里 ASR 的流式返回结果，并通过事件循环安全的机制向 WebSocket 发送。
    """
    def __init__(self, websocket, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self.websocket = websocket
        self.loop = loop
        self.send_events = []

    def on_open(self) -> None:
        logger.info("ASR 实时语音识别连接已开启")

    def on_complete(self) -> None:
        logger.info("ASR 识别完成")

    def on_error(self, result: RecognitionResult) -> None:
        logger.error(f"ASR 发生底层错误: {result.message} (请求ID: {result.request_id})")

    async def _async_send(self, payload: str, event: asyncio.Event) -> None:
        try:
            await self.websocket.send(payload)
        except Exception as e:
            logger.debug(f"ASR 推送客户端失败 (连接已断开): {e}")
        finally:
            event.set()

    def on_event(self, result: RecognitionResult) -> None:
        """增量识别结果到达"""
        sentence = result.get_sentence()
        if 'text' in sentence:
            is_end = RecognitionResult.is_sentence_end(sentence)
            raw_text = sentence['text']
            
            logger.debug(f"ASR 识别文本: {raw_text} (是否句尾: {is_end})")
            
            msg = {'text': raw_text, 'is_end': is_end}
            event = asyncio.Event()
            self.send_events.append(event)
            
            # 安全线程投递
            self.loop.call_soon_threadsafe(
                asyncio.create_task,
                self._async_send(json.dumps(msg), event)
            )

    def on_close(self) -> None:
        logger.info("ASR 识别连接已关闭")


class ASRService:
    """ASR 服务控制器"""
    def __init__(self, websocket, loop: asyncio.AbstractEventLoop):
        self.websocket = websocket
        self.loop = loop
        self.callback = ASRCallback(websocket, loop)
        self.recognition = None

    def start(self):
        """拉起 ASR 并监听麦克风"""
        if not dashscope.api_key:
            logger.warning("ASR 语音识别服务跳过启动 (未配置 DASHSCOPE_API_KEY)")
            return
            
        try:
            logger.debug("正在启动 ASR 语音识别模块...")
            self.recognition = Recognition(
                model='paraformer-realtime-v2',
                format='pcm',
                sample_rate=16000,
                language_hints=['zh'],
                semantic_punctuation_enabled=False,
                callback=self.callback
            )
            self.recognition.start()
            logger.info("ASR 服务成功挂载并开始倾听麦克风输入")
        except Exception as e:
            logger.error(f"ASR 服务启动失败: {e}")

    def send_audio_frame(self, data: bytes):
        """传入前端采集的 16kHz 音频帧"""
        if self.recognition:
            try:
                self.recognition.send_audio_frame(data)
            except Exception as e:
                logger.warning(f"⚠️ ASR 实时帧写入失败 (可能连接已被阿里端中断): {e}")
                self.recognition = None

    def stop(self):
        """释放 ASR 物理句柄并安全断开"""
        if self.recognition:
            try:
                self.recognition.stop()
                logger.info("ASR 识别服务已安全释放")
            except Exception as e:
                logger.debug(f"ASR 关闭释放时忽略的正常阻尼: {e}")
            finally:
                self.recognition = None

    async def wait_for_all_events(self):
        """等待所有已发送事件被前端确认"""
        for event in self.callback.send_events:
            try:
                await event.wait()
            except Exception:
                pass
