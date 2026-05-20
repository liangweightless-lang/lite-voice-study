import asyncio
import dashscope
from dashscope.audio.tts_v2 import *
from config.settings import logger

class TTSCallback(ResultCallback):
    """
    TTS (流式语音合成服务) 回调类
    接收由 CosyVoice 线程并发产出的 PCM 裸流音频帧，通过 WebSocket 异步回传至浏览器前端。
    """
    def __init__(self, websocket, loop: asyncio.AbstractEventLoop):
        self.websocket = websocket
        self.loop = loop
        self.completed = asyncio.Queue()  # 合成彻底结束的信号量通知

    def on_open(self):
        logger.debug("TTS 后台物理合成会话启动")

    def on_complete(self):
        logger.debug("TTS 后台物理合成全部完成")
        self.loop.call_soon_threadsafe(self.completed.put_nowait, True)

    def on_error(self, message: str):
        logger.error(f"TTS 底层错误引发报错: {message}")
        self.loop.call_soon_threadsafe(self.completed.put_nowait, True)

    def on_close(self):
        logger.debug("TTS 后台物理会话正常关闭")

    def on_event(self, message):
        pass

    def on_data(self, data: bytes) -> None:
        """核心回调：当合成出音频裸数据时，直接线程安全地分块推送给客户端"""
        logger.debug(f"接收到 TTS 合成裸音频: {len(data)} 字节，正在回传前端...")
        self.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.websocket.send(data)
        )


class TTSService:
    """TTS 语音合成服务控制器"""
    def __init__(self, websocket, loop: asyncio.AbstractEventLoop):
        self.websocket = websocket
        self.loop = loop
        self.callback = TTSCallback(websocket, loop)
        self.synthesizer = None
        self.buffer = ""
        self.punct_set = set('，。！？,.!?;；：:')

    def start(self):
        """开启并准备流式合成管道"""
        if not dashscope.api_key:
            logger.warning("TTS 语音合成器跳过初始化 (未配置 DASHSCOPE_API_KEY，降级为纯文本流式对话模式)")
            return

        try:
            logger.debug("正在拉起 CosyVoice 语音合成芯片...")
            self.synthesizer = SpeechSynthesizer(
                model='cosyvoice-v2',
                voice='longlaotie_v2',
                format=AudioFormat.PCM_22050HZ_MONO_16BIT,  # 统一 22.05kHz 裸音频
                callback=self.callback,
            )
            self.buffer = ""
            logger.info("CosyVoice 实时流式合成器准备完毕")
        except Exception as e:
            logger.error(f"TTS 语音合成器初始化失败: {e}")

    def feed_text(self, text_chunk: str, stop_event: asyncio.Event) -> bool:
        """
        向合成器输入增量文字分片。
        采用双阈值缓冲模型：句子攒够 20 字，或者遇到标点符号时，立即刷入合成。
        
        :return: True 表示有数据刷入合成器，False 表示继续在缓冲区累积
        """
        if stop_event.is_set():
            return False
            
        self.buffer += text_chunk
        need_flush = False
        
        # 1. 累积字数达到20字
        if len(self.buffer) >= 20:
            need_flush = True
        else:
            # 2. 遇到语义中断标点
            for ch in text_chunk:
                if ch in self.punct_set:
                    need_flush = True
                    break
        
        if need_flush:
            text_to_synthesize = self.buffer.strip()
            if text_to_synthesize:
                if self.synthesizer:
                    logger.debug(f"双阈值缓冲命中，刷入 TTS 语音引擎: '{text_to_synthesize}'")
                    self.synthesizer.streaming_call(text_to_synthesize)
                else:
                    logger.debug(f"[纯文本流] 字片刷新: '{text_to_synthesize}'")
                self.buffer = ""
                return True
        return False

    def finish_remaining(self, stop_event: asyncio.Event):
        """处理句子结尾残留的尾部文字"""
        if stop_event.is_set():
            return
            
        remaining = self.buffer.strip()
        if remaining:
            if self.synthesizer:
                try:
                    self.synthesizer.streaming_call(remaining)
                except Exception as e:
                    logger.warning(f"尾音写入失败 (可能打断中): {e}")
            else:
                logger.debug(f"[纯文本流] 尾音刷新: '{remaining}'")
            self.buffer = ""

    def complete_streaming(self):
        """通知合成器当前流数据传输完毕"""
        if self.synthesizer:
            try:
                self.synthesizer.async_streaming_complete()
            except Exception as e:
                logger.debug(f"TTS 结束信号发送失败: {e}")
        else:
            # [关键降级技巧] 如果没有实体合成器，直接向 completed 信号队列推入结束信号，秒级释放阻塞
            self.callback.completed.put_nowait(True)

    async def wait_for_completion(self):
        """挂起当前协程，阻塞等待合成线程彻底输出完毕"""
        while True:
            if not self.callback.completed.empty():
                break
            await asyncio.sleep(0.05)
