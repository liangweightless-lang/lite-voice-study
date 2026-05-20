# Lite Voice Study 🎙️ (极简流式语音交互学习脚手架)

本项目是一个为学习和研究“流式大模型双向语音对话交互”而专门剥离的轻量级开发脚手架。
采用 **Vue 3 + Vite + TypeScript + Naive UI (前端)** 与 **Python Asyncio + DashScope SDK + Websockets (后端)** 架构。

它实现了流式大模型对接中最具挑战性的四大核心难点：
1. **流式语音识别 (Realtime ASR)**：实时采集麦克风裸音频并通过 WebSocket 送入后端识别，流式拼装字帧。
2. **大模型流式生成 (LLM Streaming)**：流式请求 Qwen 模型，文字分片第一时间返回网页展示。
3. **流式语音合成 (TTS Streaming)**：双阈值缓冲控制（满足标点符号或积累超 20 字），流式刷入 CosyVoice 合成器，PCM 二进制裸流毫秒级回传。
4. **端侧毫秒级强打断 (Barge-In)**：自适应端侧语音活动检测 (VAD)，在 AI 播音时一旦检测到用户开口，瞬时压低音量进行快速避让 (Ducking)；若发声明显，则下发打断信号，物理切断后端合成并清空前端声卡队列，体验丝滑自然。

---

## 📂 项目结构

```text
lite-voice-study/
├── backend/                  # 后端 Python 服务
│   ├── .env                  # API Key 密钥配置文件 (需填写)
│   ├── requirements.txt      # 依赖包列表
│   ├── main.py               # 核心服务引导启动入口 (纯净入口)
│   ├── config/               # 全局配置与 Logger 中心
│   │   └── settings.py
│   ├── core/                 # 核心底层音频引擎层 (ASR/TTS 适配解耦)
│   │   ├── asr.py
│   │   └── tts.py
│   ├── providers/            # 插件驱动化大模型层 (支持 Qwen/Gemini/OpenAI 动态插拔)
│   │   ├── base.py
│   │   ├── qwen.py
│   │   ├── gemini.py
│   │   ├── openai_compat.py
│   │   └── factory.py
│   └── routers/              # 核心连接网关与会话调度层
│       └── voice.py
└── frontend/                 # 前端 Vue3 项目
    ├── package.json          # 前端依赖配置
    ├── pnpm-lock.yaml        # pnpm 锁定文件
    ├── vite.config.ts        # Vite 配置
    └── src/
        ├── App.vue           # 高颜值科技感对话舱控制台 (三态动效)
        ├── main.ts           # 应用入口
        ├── style.css         # 样式重置
        ├── worklets/
        │   └── recorder-worklet.js  # 音频 PCM 转换与数据分块处理器
        ├── utils/
        │   ├── pcmRecorder.ts       # 麦克风 16000Hz 采集管理器
        │   └── pcmAudioPlayer.ts    # 流式 22050Hz 音频平滑队列播放器 (含避让打断)
        └── composables/
            └── useVoiceConversation.ts # 核心双向 WebSocket 连接与话轮 VAD 控制器
```

---

## 🚀 快速开始指引

### 第一步：准备 DashScope API Key
1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/) 并注册/登录。
2. 在右上角点击“个人中心” -> “API-KEY”，创建一个有效的 API Key。
3. 打开 `backend/.env`，将您的 API Key 填入：
   ```env
   DASHSCOPE_API_KEY=您的百炼API_KEY_填写到这里
   ```

---

### 第二步：启动 Python 语音对话后台
您电脑上已经全局配置了极其高效的 **`uv`**（位于 `~/.local/bin/uv`），**这是最强烈推荐的一键部署与运行方式**！

只需打开终端，执行以下几行命令：

```bash
cd /Users/weightless/Documents/Project/lite-voice-study/backend

# 1. 使用 uv 瞬间创建 Python 虚拟环境
~/.local/bin/uv venv

# 2. 使用 uv 极速安装 requirements.txt 依赖包
~/.local/bin/uv pip install -r requirements.txt

# 3. 启动后端 WebSocket 语音核心服务
~/.local/bin/uv run backend/main.py
```

当终端输出以下日志时，说明后端已经在 9090 端口就绪：
> `WebSocket 语音核心服务成功启动，监听地址: ws://localhost:9090`

---

### 第三步：启动前端科技感控制台
因为本项目使用最新版 Vite 构建，请使用高版本 Node.js 运行。您的电脑支持 `nvm`，可按如下步骤启动：

1. 打开另一个新的终端窗口，切入前端目录：
   ```bash
   cd /Users/weightless/Documents/Project/lite-voice-study/frontend
   ```
2. 使用 `nvm` 切换到 v22.22 版本：
   ```bash
   source ~/.nvm/nvm.sh
   nvm use 22
   ```
3. 使用全局 `pnpm` 启动前端开发服务器：
   ```bash
   pnpm run dev
   ```
4. 在浏览器中打开终端输出的 Vite 本地链接（如 `http://localhost:5173`），即可进入高颜值对话舱开始演练！

---

## 💡 核心机制学习建议

为了最大化您的学习效果，建议重点阅读以下三个核心文件中的代码：

1. **后端大模型与语音合成流式对接管道 (`backend/routers/voice.py` 及 `backend/providers/`)**：
   * 学习如何使用**插件策略工厂模式**解耦多大模型提供商的请求差异；
   * 观察 `get_text_chunks_generator` 异步生成器如何将各类同步/异步模型响应完美降维整合为单一字符迭代流；
   * 学习 `routers/voice.py` 中如何通过多协程并发安全地协调 ASR、LLM 与 TTS，以及如何实现毫秒级开口说话打断机制。

2. **前端流式音频平滑播放器 (`frontend/src/utils/pcmAudioPlayer.ts`)**：
   * 学习如何通过 `AudioContext` 以 22.05kHz 频率建立单声道缓冲队列；
   * 观察 `nextStart` 机制如何避免音频分片重叠或间断，以及边缘淡化如何完美清除杂音。

3. **双向话轮控制层 (`frontend/src/composables/useVoiceConversation.ts`)**：
   * 学习自适应话轮延时计算（通过说话时间 `dur` 和峰值音量 `peak` 综合调整下发大模型提问的时间戳）；
   * 重点阅读**打断判断**：如何使用端侧 VAD 的 `peak` 进行判断，执行 `player.stop()` 并发送 `stop_tts` 信令瞬间阻断 AI 播音。
