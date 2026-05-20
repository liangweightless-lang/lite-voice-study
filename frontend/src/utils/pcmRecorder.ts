export class PCMAudioRecorder {
  private audioContext: AudioContext | null = null
  private stream: MediaStream | null = null
  private currentSource: MediaStreamAudioSourceNode | null = null
  private processorNode: AudioWorkletNode | null = null
  private audioCallback: ((data: Int16Array) => void) | null = null

  async connect(audioCallback: (data: Int16Array) => void) {
    /** 申请麦克风权限，启动 AudioWorklet 并流式回调输出 16k PCM 帧 */
    this.audioCallback = audioCallback
    if (!this.audioContext) {
      const AudioContextClass = (window.AudioContext ?? (window as any).webkitAudioContext) as typeof AudioContext
      // 指定采样率为 ASR 最佳实践：16000Hz 单声道
      this.audioContext = new AudioContextClass({ sampleRate: 16000 })
    }

    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    this.currentSource = this.audioContext.createMediaStreamSource(this.stream)

    // 使用 Vite 支持的 new URL(..., import.meta.url) 动态加载后台 Worklet 模块
    await this.audioContext.audioWorklet.addModule(new URL('../worklets/recorder-worklet.js', import.meta.url))

    this.processorNode = new AudioWorkletNode(this.audioContext, 'pcm-processor')
    this.processorNode.port.onmessage = (event) => {
      if (event.data instanceof Int16Array) {
        this.audioCallback?.(event.data)
      }
    }

    this.currentSource.connect(this.processorNode)
    this.processorNode.connect(this.audioContext.destination)
  }

  stop() {
    /** 停止录音，完全释放音频输入上下文，关闭麦克风占用 */
    if (this.processorNode) {
      this.processorNode.port.postMessage('stop')
    }
    if (this.stream) {
      for (const track of this.stream.getTracks()) track.stop()
    }
    if (this.currentSource) {
      this.currentSource.disconnect()
      this.currentSource = null
    }
    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }
    if (this.processorNode) {
      this.processorNode.disconnect()
      this.processorNode.port.close()
      this.processorNode = null
    }
    this.audioCallback = null
  }
}
