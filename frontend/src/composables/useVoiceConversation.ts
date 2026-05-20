import { ref } from 'vue'
import PCMAudioPlayer from '../utils/pcmAudioPlayer'
import { PCMAudioRecorder } from '../utils/pcmRecorder'

// 消息定义
export interface Message {
  id: string
  role: 'user' | 'ai'
  text: string
  createdAt: number
}

// 语音状态类型
// idle: 闲置中, listening: 前端正在倾听用户说话, speaking: AI正在流式合成播放语音, processing: 后端大模型流式推理中
export type CallState = 'idle' | 'listening' | 'speaking' | 'processing'

// 智能打断的静默词，当用户说了以下词汇时，可以直接挂断或触发特定逻辑
const END_WORDS = ['拜拜', '再见', '挂了啊', '先不聊了']

export function useVoiceConversation() {
  const messages = ref<Message[]>([])
  const callState = ref<CallState>('idle')
  const aiVolume = ref(0)
  const serverOnline = ref<boolean | null>(null)
  const connectionMessage = ref('')

  let ws: WebSocket | null = null
  let recorder: PCMAudioRecorder | null = null
  const player = new PCMAudioPlayer(22050) // CosyVoice 合成的 PCM 采样率是 22050Hz
  player.connect()

  let activeUserId: string | null = null
  let activeAiId: string | null = null
  let lastVoiceTs = 0
  let llmTimer: ReturnType<typeof setTimeout> | null = null
  let pendingQuery: string | null = null
  let ignoreAI = false
  let isSpeaking = false
  let speakStart = 0
  let lastSpeakingDurationMs = 0
  let lastSpeakingMax = 0
  let duckActive = false
  let duckRecoverTimer: ReturnType<typeof setTimeout> | null = null
  let silenceCheckTimer: ReturnType<typeof setInterval> | null = null
  let silenceNudgeCount = 0
  let lastInteractionTs = 0

  let systemPrompt = '你是一个人工智能语音助手，你的回答要非常简洁、口语化，不要超过50字，以适合语音交互。'

  /**
   * 开启语音对话
   */
  async function startCall(customPrompt?: string, initialGreeting?: string) {
    if (customPrompt) systemPrompt = customPrompt
    messages.value = []
    callState.value = 'listening'
    ignoreAI = false
    lastInteractionTs = Date.now()
    silenceNudgeCount = 0

    // A. 开启每秒一次的“智能静默催促检测”：若用户 10 秒没有任何发声交互，触发静态 TTS 催促
    if (silenceCheckTimer) clearInterval(silenceCheckTimer)
    silenceCheckTimer = setInterval(() => {
      if (callState.value === 'listening' && serverOnline.value) {
        const now = Date.now()
        if (now - lastInteractionTs > 10000) {
          if (silenceNudgeCount >= 2) {
            // 催促超过 2 次，自动结束挂断，防止服务器资源空挂
            endCall()
          } else {
            silenceNudgeCount++
            lastInteractionTs = now
            if (ws && ws.readyState === WebSocket.OPEN) {
              const phrases = ['你好，还在吗？', '听得见我说话吗？', '还在听吗？']
              const text = phrases[Math.floor(Math.random() * phrases.length)]
              // 跳过 LLM 生成，直接向后端发送 tts_text 请求直接合成语音
              ws.send(JSON.stringify({ type: 'tts_text', text }))
              
              // 3秒后强制切回 listening，恢复正常话轮
              setTimeout(() => {
                if (callState.value !== 'idle') {
                  callState.value = 'listening'
                  lastInteractionTs = Date.now()
                }
              }, 3000)
            }
          }
        }
      }
    }, 1000)

    // B. 连接后端极简 WebSocket 服务 (支持协议与域名自适应，云端部署即装即用)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // 开发环境直连 9090 端口，生产环境（Docker 容器内）自动走同一个域名的 /ws 反向代理通道
    const defaultWsUrl = import.meta.env.DEV
      ? `${protocol}//${window.location.hostname}:9090`
      : `${protocol}//${window.location.host}/ws`
    const WS_URL = (import.meta.env.VITE_VOICE_WS_URL as string | undefined) ?? defaultWsUrl
    ws = new WebSocket(WS_URL)
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      serverOnline.value = true
      connectionMessage.value = ''
      console.log('语音服务 WebSocket 连接成功')
      
      // 发送初始打招呼话术
      if (initialGreeting && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'tts_text', text: initialGreeting }))
      }
    }

    ws.onerror = () => {
      serverOnline.value = false
      connectionMessage.value = '无法连接语音服务器，请检查后端是否在 9090 端口运行'
      callState.value = 'idle'
      player.stop()
      try { recorder?.stop() } catch {}
    }

    ws.onclose = () => {
      serverOnline.value = false
      connectionMessage.value = '与语音服务器的连接已断开'
      callState.value = 'idle'
      player.stop()
      try { recorder?.stop() } catch {}
    }

    ws.onmessage = (ev) => {
      if (callState.value === 'idle') return

      // B1. 如果收到的是文本数据：可能是 ASR 识别结果或大模型文字推送
      if (typeof ev.data === 'string') {
        try {
          const obj = JSON.parse(ev.data) as { text: string; is_end?: boolean }
          
          if (obj.text) {
            // ASR 识别到的文本包含挂断词，自动结束
            if (END_WORDS.some(word => obj.text.includes(word))) {
              endCall()
              return
            }

            if (obj.is_end) {
              // 1. 用户说话在句尾结束时，将其拼装进 message 列表
              if (activeUserId) {
                const idx = messages.value.findIndex((m) => m.id === activeUserId)
                if (idx >= 0) messages.value[idx].text = obj.text
              } else {
                const id = Math.random().toString(36).slice(2)
                messages.value.push({ id, role: 'user', text: obj.text, createdAt: Date.now() })
              }
              
              // 2. 话轮智能检测 (VAD) & 延迟推送大模型：依据说话的时长和音量大小，动态设置 600ms~900ms 延迟
              callState.value = 'processing'
              pendingQuery = obj.text
              if (llmTimer) clearTimeout(llmTimer)
              
              const dur = lastSpeakingDurationMs || 0
              const peak = lastSpeakingMax || 0
              let delay = 600 + Math.min(300, Math.floor((Math.min(dur, 2000) / 2000) * 180 + (Math.min(peak, 8000) / 8000) * 120))
              
              const triggerLLM = () => {
                const now = Date.now()
                // 当真正检测到用户已经保持静默超 800ms，且有待提交文本时，发送请求给 LLM + TTS 管道
                if (now - lastVoiceTs >= 800 && ws && ws.readyState === WebSocket.OPEN && pendingQuery) {
                  const history = messages.value.slice(-20).map((m) => ({
                    role: m.role === 'ai' ? 'assistant' : 'user',
                    content: m.text,
                  }))
                  
                  const payload = { 
                    type: 'llm_tts', 
                    messages: [
                      { role: 'system', content: systemPrompt }, 
                      ...history
                    ] 
                  }
                  ws.send(JSON.stringify(payload))
                  llmTimer = null
                  pendingQuery = null
                } else {
                  // 如果未达到静默判定，等待差值后重试
                  const wait = Math.max(800 - (now - lastVoiceTs), 250)
                  llmTimer = setTimeout(triggerLLM, wait)
                }
              }
              llmTimer = setTimeout(triggerLLM, delay)
              activeUserId = null
            } else {
              // 3. 说话过程中的增量 ASR 字符同步展示
              if (activeUserId) {
                const idx = messages.value.findIndex((m) => m.id === activeUserId)
                if (idx >= 0) messages.value[idx].text = obj.text
              } else {
                const id = Math.random().toString(36).slice(2)
                messages.value.push({ id, role: 'user', text: obj.text, createdAt: Date.now() })
                activeUserId = id
              }
            }
          }
        } catch {
          // 如果不是 JSON，则是大模型下发的增量大文本字符流
          const textChunk = ev.data as string
          if (textChunk === 'asr stopped') {
            activeAiId = null
            return
          }
          if (textChunk === 'tts stopped') {
            ignoreAI = false
            activeAiId = null
            callState.value = 'listening'
            lastInteractionTs = Date.now()
            return
          }

          if (ignoreAI) return

          // 增量大模型文字更新
          if (activeAiId) {
            const idx = messages.value.findIndex((m) => m.id === activeAiId)
            if (idx >= 0) messages.value[idx].text += textChunk
          } else {
            const id = Math.random().toString(36).slice(2)
            messages.value.push({ id, role: 'ai', text: textChunk, createdAt: Date.now() })
            activeAiId = id
          }
        }
      } 
      // B2. 如果收到的是二进制数据：说明是后端发回来的 22050Hz 单声道 PCM 合成音频，立刻排队播放
      else if (ev.data instanceof ArrayBuffer) {
        if (!ignoreAI) {
          player.pushPCM(ev.data)
          aiVolume.value = player.volume
          callState.value = 'speaking'
        }
      }
    }

    // C. 实例化音频采集录音类
    try {
      recorder = new PCMAudioRecorder()
      await recorder.connect((pcm) => {
        // 计算当前这一帧音频分片的瞬时音量峰值
        let peak = 0
        for (let i = 0; i < pcm.length; i++) {
          const v = pcm[i]
          const a = v >= 0 ? v : -v
          if (a > peak) peak = a
        }

        // 端上简易 VAD 判断：如果音量峰值大于 3000，判定用户在说话 (提升防噪音能力)
        const speaking = peak > 3000
        if (speaking) {
          lastVoiceTs = Date.now()
          lastInteractionTs = Date.now() // 重置静默催促计时
          silenceNudgeCount = 0

          if (!isSpeaking) {
            isSpeaking = true
            speakStart = Date.now()
            lastSpeakingMax = peak
          } else {
            if (peak > lastSpeakingMax) lastSpeakingMax = peak
          }

          // 如果在用户说话的静默窗口内，用户再次开口，取消大模型提交任务
          if (llmTimer) {
            clearTimeout(llmTimer)
            llmTimer = null
            pendingQuery = null
            callState.value = 'listening'
          }

          // 【极速打断核心逻辑】如果用户开口说话时 AI 正在合成播音 (speaking)
          if (callState.value === 'speaking') {
            // 第一步：先压低音量进行快速音量避让 (Ducking)
            if (!duckActive) {
              player.duckTo(0.3, 80) // 80ms 内音量压低到 30%
              duckActive = true
              if (duckRecoverTimer) clearTimeout(duckRecoverTimer)
              duckRecoverTimer = setTimeout(() => {
                if (duckActive && callState.value === 'speaking' && !isSpeaking) {
                  player.unduck(150) // 150ms 缓和恢复
                  duckActive = false
                }
              }, 300)
            }

            // 第二步：强打断判别。如果发声非常明显 (峰值超 6000) 或者持续说话超过 300ms，触发物理掐断
            const strongSpeaking = peak > 6000 || (Date.now() - speakStart) > 300
            if (strongSpeaking) {
              if (duckRecoverTimer) clearTimeout(duckRecoverTimer)
              duckActive = false
              player.duck(60)
              player.stop()  // 强行清空播放队列与停止当前声源播放
              activeAiId = null
              callState.value = 'listening'
              
              // 下发 stop_tts 打断信号给后端，后端瞬间 Cancel 生成和合成
              if (ws && ws.readyState === WebSocket.OPEN) {
                ignoreAI = true
                ws.send(JSON.stringify({ type: 'stop_tts' }))
              }
            }
          }
        } else {
          if (isSpeaking) {
            isSpeaking = false
            lastSpeakingDurationMs = Date.now() - speakStart
          }
        }

        // 将网页端捕获的 16000Hz 单声道 16bit 裸音频实时喂给 WebSocket (仅当录音模块激活时)
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(pcm.buffer)
        }
      })
      console.log('🎤 麦克风录音机连接成功，已开启实时语音识别模式')
    } catch (err) {
      console.warn('⚠️ 麦克风访问失败或拒绝，系统已自动切换为 [纯文本流式交互模式]:', err)
      recorder = null
    }
  }

  /**
   * 挂断并结束通话
   */
  function endCall() {
    if (silenceCheckTimer) {
      clearInterval(silenceCheckTimer)
      silenceCheckTimer = null
    }
    callState.value = 'idle'
    player.stop()
    if (recorder) {
      recorder.stop()
      recorder = null
    }
    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop_tts' }))
        ws.send('stop')
        ws.close()
      }
    } catch {}
    ws = null
    if (llmTimer) {
      clearTimeout(llmTimer)
      llmTimer = null
    }
    pendingQuery = null
    activeAiId = null
    activeUserId = null
    duckActive = false
    if (duckRecoverTimer) clearTimeout(duckRecoverTimer)
  }

  /**
   * 发送纯文字消息提问 (支持降级或打字交互)
   */
  function sendTextMessage(text: string) {
    const safeText = text.trim()
    if (!safeText) return
    
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket 尚未连接，请先点击“开始通话”建立会话链接')
      return
    }

    // 1. 瞬间强打断当前正在播音/推理的 AI 状态
    if (callState.value === 'speaking' || callState.value === 'processing') {
      ws.send(JSON.stringify({ type: 'stop_tts' }))
      player.stop()
      activeAiId = null
    }

    // 2. 将消息添加至本地聊天流
    const id = Math.random().toString(36).slice(2)
    messages.value.push({ id, role: 'user', text: safeText, createdAt: Date.now() })

    // 3. 改变状态为处理中，重置静默催促判定
    callState.value = 'processing'
    ignoreAI = false
    lastInteractionTs = Date.now()
    silenceNudgeCount = 0

    // 4. 组装上下文负载，向 WebSocket 推送
    const history = messages.value.slice(-20).map((m) => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.text,
    }))
    
    const payload = { 
      type: 'llm_tts', 
      messages: [
        { role: 'system', content: systemPrompt }, 
        ...history
      ] 
    }
    ws.send(JSON.stringify(payload))
  }

  return {
    messages,
    callState,
    startCall,
    endCall,
    sendTextMessage,
    aiVolume,
    serverOnline,
    connectionMessage,
  }
}
