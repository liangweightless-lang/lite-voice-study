<template>
  <n-config-provider :theme="darkTheme">
    <div class="voice-app-container">
      <div class="voice-app-card">
        <!-- 头部标题区 -->
        <div class="voice-header">
          <div class="logo-area">
            <span class="pulse-dot" :class="callState"></span>
            <h1>Lite Voice Study</h1>
          </div>
          <div class="status-tags">
            <n-tag v-if="serverOnline" type="success" size="small" round>
              服务已连接
            </n-tag>
            <n-tag v-else-if="serverOnline === false" type="error" size="small" round>
              服务离线
            </n-tag>
            <n-tag v-else type="warning" size="small" round>
              未连接
            </n-tag>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="connectionMessage" class="error-alert">
          <n-alert title="连接警告" type="error" closable>
            {{ connectionMessage }}
          </n-alert>
        </div>

        <!-- 核心视觉动画区 -->
        <div class="visualizer-section">
          <!-- 1. 空闲态 -->
          <div v-if="callState === 'idle'" class="visualizer-circle idle" @click="handleStart">
            <div class="icon-ring">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="mic-svg">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              </svg>
            </div>
            <span class="click-tip">点击开始对话</span>
          </div>

          <!-- 2. 倾听态 (用户说话) -->
          <div v-else-if="callState === 'listening'" class="visualizer-circle listening">
            <div class="radar-wave wave1"></div>
            <div class="radar-wave wave2"></div>
            <div class="radar-wave wave3"></div>
            <div class="icon-ring pulse">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="mic-svg active-mic">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              </svg>
            </div>
            <span class="click-tip green">请说话，我正在听...</span>
          </div>

          <!-- 3. 后端大模型推理中 -->
          <div v-else-if="callState === 'processing'" class="visualizer-circle processing">
            <div class="loading-ring"></div>
            <div class="icon-ring">
              <div class="thinking-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
            <span class="click-tip blue">正在思考并组织语言...</span>
          </div>

          <!-- 4. AI 实时播音态 (展示随音量起伏跳动的高科技音柱) -->
          <div v-else-if="callState === 'speaking'" class="visualizer-circle speaking">
            <div class="music-wave">
              <span v-for="i in 12" :key="i" class="bar" :style="getBarStyle(i)"></span>
            </div>
            <span class="click-tip purple">AI 正在说话 (说话时开口可直接打断)</span>
          </div>
        </div>

        <!-- 文本对话实时流展示 -->
        <div class="chat-feed-container">
          <div class="chat-feed-header">对话实时字幕</div>
          <n-scrollbar ref="scrollbarRef" class="chat-feed-scroll">
            <div class="message-list">
              <div v-if="messages.length === 0" class="empty-chat">
                暂无对话内容，点击上方麦克风即可开始实时文字与语音交互。
              </div>
              <div 
                v-for="msg in messages" 
                :key="msg.id" 
                class="msg-bubble-wrapper"
                :class="msg.role"
              >
                <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
                <div class="msg-bubble">
                  {{ msg.text }}
                </div>
              </div>
            </div>
          </n-scrollbar>
          
          <!-- 新增高科技文字流输入条 -->
          <div v-if="callState !== 'idle'" class="text-chat-input-bar">
            <n-input
              v-model:value="textMsgInput"
              type="text"
              placeholder="打字提问并按回车发送..."
              @keyup.enter="handleSendText"
              round
              clearable
            >
              <template #suffix>
                <n-button 
                  text 
                  type="primary" 
                  @click="handleSendText"
                  style="cursor: pointer; font-weight: 600;"
                >
                  发送
                </n-button>
              </template>
            </n-input>
          </div>
        </div>

        <!-- 控制台参数配置区 -->
        <div class="control-panel">
          <div class="panel-section">
            <label>AI 系统设定 (Prompt)</label>
            <n-input
              v-model:value="customPrompt"
              type="textarea"
              placeholder="设定AI人设、性格、语言要求等..."
              :disabled="callState !== 'idle'"
              rows="2"
            />
          </div>
          <div class="panel-section">
            <label>AI 欢迎语 (Greeting)</label>
            <n-input
              v-model:value="initialGreeting"
              type="text"
              placeholder="连接成功后AI说出的第一句话..."
              :disabled="callState !== 'idle'"
            />
          </div>
        </div>

        <!-- 底部控制按钮 -->
        <div class="action-bar">
          <n-button 
            v-if="callState === 'idle'" 
            type="primary" 
            size="large" 
            block 
            round
            @click="handleStart"
          >
            开启实时语音通话
          </n-button>
          <n-button 
            v-else 
            type="error" 
            size="large" 
            block 
            round
            @click="handleStop"
          >
            挂断通话
          </n-button>
        </div>
      </div>
    </div>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { 
  NConfigProvider, 
  darkTheme, 
  NTag, 
  NInput, 
  NButton, 
  NAlert, 
  NScrollbar 
} from 'naive-ui'
import { useVoiceConversation } from './composables/useVoiceConversation'

const {
  messages,
  callState,
  startCall,
  endCall,
  sendTextMessage,
  aiVolume,
  serverOnline,
  connectionMessage
} = useVoiceConversation()

const customPrompt = ref('你是一个温暖体贴的人工智能语音伴侣。说话要温柔、幽默、口语化，不要超过50字，以适合语音交互。')
const initialGreeting = ref('你好呀！我是你的AI语音助手，很高兴和你聊天，我们开始吧！')
const textMsgInput = ref('')
const scrollbarRef = ref<any>(null)

// 触发发送文字消息并重置输入
const handleSendText = () => {
  const txt = textMsgInput.value.trim()
  if (txt) {
    sendTextMessage(txt)
    textMsgInput.value = ''
  }
}

// 触发呼叫连接
const handleStart = async () => {
  try {
    await startCall(customPrompt.value, initialGreeting.value)
  } catch (e) {
    console.error(e)
  }
}

// 挂断通话
const handleStop = () => {
  endCall()
}

// 滚动条自动滚到底部
watch(() => messages.value, () => {
  nextTick(() => {
    if (scrollbarRef.value) {
      scrollbarRef.value.scrollTo({ position: 'bottom', silent: true })
    }
  })
}, { deep: true })

// 实时计算播音态音柱高度
const getBarStyle = (index: number) => {
  // 利用音量 aiVolume (0~1) 动态生成每个柱子的高度和弹性参数
  const vol = aiVolume.value || 0
  const randomFactor = Math.sin(index * 1.5) * 0.15 + 0.85
  const baseHeight = 10
  const activeHeight = vol * 110 * randomFactor
  const finalHeight = Math.max(baseHeight, Math.min(100, baseHeight + activeHeight))
  
  return {
    height: `${finalHeight}px`,
    transition: 'height 0.08s ease-out'
  }
}
</script>

<style scoped>
.voice-app-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: radial-gradient(circle at center, #1b2030 0%, #0c0e17 100%);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #e2e8f0;
  padding: 20px;
}

.voice-app-card {
  width: 100%;
  max-width: 520px;
  background: rgba(20, 24, 43, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  padding: 30px;
  box-sizing: border-box;
}

/* 头部样式 */
.voice-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-area h1 {
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #38bdf8 0%, #34d399 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #94a3b8;
}
.pulse-dot.listening {
  background-color: #10b981;
  box-shadow: 0 0 10px #10b981;
}
.pulse-dot.speaking {
  background-color: #8b5cf6;
  box-shadow: 0 0 10px #8b5cf6;
}
.pulse-dot.processing {
  background-color: #3b82f6;
  box-shadow: 0 0 10px #3b82f6;
}

.error-alert {
  margin-bottom: 20px;
}

/* 核心动画视觉区 */
.visualizer-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 240px;
  margin-bottom: 24px;
  position: relative;
}

.visualizer-circle {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  position: relative;
}

.icon-ring {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s ease;
  z-index: 2;
}

.mic-svg {
  width: 44px;
  height: 44px;
  color: #94a3b8;
  transition: color 0.3s ease;
}

.click-tip {
  margin-top: 15px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  text-align: center;
  z-index: 2;
}
.click-tip.green { color: #10b981; }
.click-tip.blue { color: #3b82f6; }
.click-tip.purple { color: #a78bfa; }

/* 1. Idle 态呼吸动画 */
.visualizer-circle.idle:hover .icon-ring {
  border-color: #0284c7;
  box-shadow: 0 0 25px rgba(2, 132, 199, 0.4);
}
.visualizer-circle.idle:hover .mic-svg {
  color: #38bdf8;
}

/* 2. Listening 态雷达动画 */
.visualizer-circle.listening .icon-ring {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.05);
}
.active-mic {
  color: #10b981 !important;
}

.radar-wave {
  position: absolute;
  top: 30px;
  left: 30px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 2px solid #10b981;
  opacity: 0;
  animation: radarWave 2s cubic-bezier(0.1, 0.8, 0.3, 1) infinite;
  z-index: 1;
}
.wave2 { animation-delay: 0.6s; }
.wave3 { animation-delay: 1.2s; }

@keyframes radarWave {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(1.7); opacity: 0; }
}

/* 3. Processing 态旋转加载动画 */
.visualizer-circle.processing .icon-ring {
  background: rgba(59, 130, 246, 0.02);
  border-color: transparent;
}
.loading-ring {
  position: absolute;
  top: 28px;
  left: 28px;
  width: 102px;
  height: 102px;
  border-radius: 50%;
  border: 2px solid rgba(59, 130, 246, 0.1);
  border-top-color: #3b82f6;
  animation: spin 1s linear infinite;
  z-index: 1;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.thinking-dots {
  display: flex;
  gap: 5px;
}
.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #3b82f6;
  animation: bounce 1.2s infinite ease-in-out both;
}
.thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
.thinking-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 4. Speaking 态音乐振幅动画 */
.visualizer-circle.speaking {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  cursor: default;
}
.music-wave {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  height: 100px;
  width: 100%;
}
.music-wave .bar {
  width: 5px;
  background: linear-gradient(to top, #8b5cf6 0%, #d946ef 100%);
  border-radius: 3px;
  box-shadow: 0 0 8px rgba(217, 70, 239, 0.4);
}

/* 对话字幕区域 */
.chat-feed-container {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 24px;
}

.chat-feed-header {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.chat-feed-scroll {
  height: 180px;
}

.empty-chat {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  font-size: 13px;
  color: #475569;
  padding: 20px;
  line-height: 1.6;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 8px;
}

.msg-bubble-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 11px;
  font-weight: bold;
}

.msg-bubble {
  max-width: 75%;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.5;
  border-radius: 14px;
}

/* 用户泡泡样式 */
.msg-bubble-wrapper.user {
  flex-direction: row-reverse;
}
.msg-bubble-wrapper.user .avatar {
  background: rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
}
.msg-bubble-wrapper.user .msg-bubble {
  background: rgba(255, 255, 255, 0.06);
  color: #f1f5f9;
  border-top-right-radius: 2px;
}

/* AI 泡泡样式 */
.msg-bubble-wrapper.ai .avatar {
  background: linear-gradient(135deg, #0284c7 0%, #7c3aed 100%);
  color: #ffffff;
}
.msg-bubble-wrapper.ai .msg-bubble {
  background: linear-gradient(135deg, rgba(2, 132, 199, 0.2) 0%, rgba(124, 58, 237, 0.2) 100%);
  border: 1px solid rgba(124, 58, 237, 0.15);
  color: #ffffff;
  border-top-left-radius: 2px;
}

/* 参数设置区 */
.control-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.03);
  padding: 16px;
  border-radius: 16px;
  margin-bottom: 24px;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-section label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
}

/* 底部操作 */
.action-bar {
  margin-top: 10px;
}

/* 磨砂文字输入条样式 */
.text-chat-input-bar {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.text-chat-input-bar :deep(.n-input) {
  background: rgba(0, 0, 0, 0.35) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
}

.text-chat-input-bar :deep(.n-input:hover),
.text-chat-input-bar :deep(.n-input--focus) {
  border-color: rgba(56, 189, 248, 0.5) !important;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.15), inset 0 2px 4px rgba(0, 0, 0, 0.2) !important;
}
</style>
