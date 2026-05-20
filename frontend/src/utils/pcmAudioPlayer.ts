export default class PCMAudioPlayer {
  private sampleRate: number
  private audioContext: AudioContext | null = null
  private audioQueue: ArrayBuffer[] = []
  private isPlaying = false
  private currentSource: AudioBufferSourceNode | null = null
  private _volume = 0
  private nextStart = 0
  private sources: AudioBufferSourceNode[] = []
  private gains: GainNode[] = []
  private pendingChunks: ArrayBuffer[] = []
  private pendingBytes = 0
  private minBytes: number

  constructor(sampleRate: number) {
    this.sampleRate = sampleRate
    // 每次向声卡输出的最小缓冲块大小（50ms的音频），用于防止频繁排队引起的咔哒声
    this.minBytes = Math.floor(sampleRate * 0.05) * 2
  }

  connect() {
    if (!this.audioContext) {
      const AudioContextClass = (window.AudioContext ?? (window as any).webkitAudioContext) as typeof AudioContext
      this.audioContext = new AudioContextClass()
    }
  }

  getAudioContext(): AudioContext | null {
    return this.audioContext
  }

  pushPCM(arrayBuffer: ArrayBuffer) {
    const incomingBytes = arrayBuffer.byteLength
    const total = this.pendingBytes + incomingBytes
    
    // 如果累积的数据块太小，先放入 pending 数组，防止频繁触发小块播放导致杂音
    if (total < this.minBytes) {
      this.pendingChunks.push(arrayBuffer)
      this.pendingBytes = total
      return
    }
    
    if (this.pendingBytes > 0) {
      // 合并多段 pending 音频片段
      const merged = new ArrayBuffer(this.pendingBytes + incomingBytes)
      const out = new Int16Array(merged)
      let offset = 0
      for (const chunk of this.pendingChunks) {
        out.set(new Int16Array(chunk), offset)
        offset += chunk.byteLength / 2
      }
      out.set(new Int16Array(arrayBuffer), offset)
      this.pendingChunks = []
      this.pendingBytes = 0
      this.audioQueue.push(merged)
    } else {
      this.audioQueue.push(arrayBuffer)
    }
    this.playNext()
  }

  get volume() {
    return this._volume
  }

  private bufferPCM(pcmData: ArrayBuffer) {
    const length = pcmData.byteLength / 2
    // 创建单声道音频缓冲
    const audioBuffer = this.audioContext!.createBuffer(1, length, this.sampleRate)
    const channelData = audioBuffer.getChannelData(0)
    const int16Array = new Int16Array(pcmData)
    let peak = 0
    for (let i = 0; i < length; i++) {
      // 将 Int16 数字量化为 -1.0 到 1.0 的浮点数
      const v = (int16Array[i] ?? 0) / 32768
      channelData[i] = v
      const a = Math.abs(v)
      if (a > peak) peak = a
    }
    this._volume = peak // 记录当前播放的瞬时峰值，可用于音量波动动画展示
    return audioBuffer
  }

  private async play(arrayBuffer: ArrayBuffer) {
    if (this.audioContext!.state === 'suspended') await this.audioContext!.resume()
    const audioBuffer = this.bufferPCM(arrayBuffer)
    const source = this.audioContext!.createBufferSource()
    source.buffer = audioBuffer
    const gain = this.audioContext!.createGain()
    source.connect(gain)
    gain.connect(this.audioContext!.destination)
    
    // 计算完美的排队播放开始时间（nextStart 实现了多个 buffer 的无缝平滑拼接）
    const start = Math.max(this.audioContext!.currentTime, this.nextStart)
    
    // 进场/出场边缘淡化，彻底消除边缘咔哒声
    gain.gain.setValueAtTime(0.0001, start)
    gain.gain.linearRampToValueAtTime(1, start + 0.005)
    gain.gain.setValueAtTime(1, start + audioBuffer.duration - 0.005)
    gain.gain.linearRampToValueAtTime(0.0001, start + audioBuffer.duration)
    
    source.start(start)
    this.nextStart = start + audioBuffer.duration
    this.sources.push(source)
    this.gains.push(gain)
    this.currentSource = source
    this.isPlaying = true
  }

  private playNext() {
    if (!this.audioContext) return
    const next = this.audioQueue.shift()
    if (next) this.play(next)
  }

  stop() {
    /** 瞬时切断所有当前和未来的音频播放 */
    for (const s of this.sources) { 
      try { s.stop() } catch {} 
    }
    this.sources = []
    this.gains = []
    this.currentSource = null
    this.isPlaying = false
    this.nextStart = 0
    this.audioQueue = []
    this.pendingChunks = []
    this.pendingBytes = 0
    this._volume = 0
  }

  duck(ms = 80) {
    /** 80ms内急速压低至静音 */
    if (!this.audioContext) return
    const dur = ms / 1000
    const now = this.audioContext.currentTime
    for (const g of this.gains) {
      try {
        g.gain.cancelScheduledValues(now)
        g.gain.setValueAtTime(g.gain.value, now)
        g.gain.linearRampToValueAtTime(0.0001, now + dur)
      } catch {}
    }
  }

  duckTo(level: number, ms = 80) {
    /** 压低至指定音量比例 */
    if (!this.audioContext) return
    const dur = ms / 1000
    const now = this.audioContext.currentTime
    for (const g of this.gains) {
      try {
        g.gain.cancelScheduledValues(now)
        g.gain.setValueAtTime(g.gain.value, now)
        g.gain.linearRampToValueAtTime(level, now + dur)
      } catch {}
    }
  }

  unduck(ms = 120) {
    /** 120ms内缓和恢复音量 */
    if (!this.audioContext) return
    const dur = ms / 1000
    const now = this.audioContext.currentTime
    for (const g of this.gains) {
      try {
        g.gain.cancelScheduledValues(now)
        g.gain.setValueAtTime(g.gain.value, now)
        g.gain.linearRampToValueAtTime(1, now + dur)
      } catch {}
    }
  }
}
