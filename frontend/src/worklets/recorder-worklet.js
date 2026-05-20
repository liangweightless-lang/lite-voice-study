class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.port.onmessage = (event) => {
            if (event.data === 'stop') {
                this.port.postMessage('prepare to stop');
                this.isStopped = true;
                if (this.buffer.length > 0) {
                    this.port.postMessage(new Int16Array(this.buffer));
                    this.port.postMessage({'event':'stopped'});
                    this.buffer = [];
                }
            }
        };
        this.buffer = [];
        this.targetSampleCount = 1600; // 每次输出 1600 个采样分片 (即 100ms 的音频帧)
    }

    process(inputs) {
        const input = inputs[0];
        if (input && input.length > 0) {
            const inputData = input[0];
            for (let i = 0; i < inputData.length; i++) {
                // 将浮点数音频采样量化为 16-bit 有符号整数 PCM (Int16)
                const sample = Math.max(-32768, Math.min(32767, Math.round(inputData[i] * 32767)));
                this.buffer.push(sample);
            }
            while (this.buffer.length >= this.targetSampleCount) {
                const pcmData = this.buffer.splice(0, this.targetSampleCount);
                this.port.postMessage(new Int16Array(pcmData));
                this.port.postMessage({'event':'sending'});
            }
        }
        return true;
    }
}

registerProcessor('pcm-processor', PCMProcessor);
