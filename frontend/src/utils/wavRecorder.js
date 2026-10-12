// Records the microphone as a 16 kHz mono WAV file.
//
// Browsers record WebM by default, which Chorus doesn't accept, so we capture the
// raw sound ourselves and pack it as WAV, the format Chorus recommends. 16 kHz mono
// is what Chorus converts everything to anyway, so the upload is as small as it can be.

const TARGET_RATE = 16000

// Runs on the browser's audio thread and passes each block of sound back to us.
const CAPTURE_WORKLET = `
class Capture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (channel) this.port.postMessage(channel.slice(0))
    return true
  }
}
registerProcessor('capture', Capture)
`

export function canRecord() {
  return Boolean(navigator.mediaDevices?.getUserMedia && window.AudioContext && window.AudioWorkletNode)
}

export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  })
  const context = new AudioContext()
  const moduleUrl = URL.createObjectURL(new Blob([CAPTURE_WORKLET], { type: 'application/javascript' }))
  await context.audioWorklet.addModule(moduleUrl)
  URL.revokeObjectURL(moduleUrl)

  const source = context.createMediaStreamSource(stream)
  const capture = new AudioWorkletNode(context, 'capture')
  const silent = context.createGain()
  silent.gain.value = 0 // keeps the graph running without playing the voice back
  const blocks = []
  capture.port.onmessage = (event) => blocks.push(event.data)
  source.connect(capture).connect(silent).connect(context.destination)

  return {
    async stop() {
      source.disconnect()
      capture.disconnect()
      stream.getTracks().forEach((track) => track.stop())
      const inputRate = context.sampleRate
      await context.close()
      const samples = downsample(join(blocks), inputRate, TARGET_RATE)
      return encodeWav(samples, TARGET_RATE)
    },
    cancel() {
      stream.getTracks().forEach((track) => track.stop())
      context.close()
    },
  }
}

function join(blocks) {
  const length = blocks.reduce((sum, block) => sum + block.length, 0)
  const joined = new Float32Array(length)
  let offset = 0
  for (const block of blocks) {
    joined.set(block, offset)
    offset += block.length
  }
  return joined
}

function downsample(samples, inputRate, outputRate) {
  if (outputRate >= inputRate) return samples
  const ratio = inputRate / outputRate
  const output = new Float32Array(Math.floor(samples.length / ratio))
  for (let i = 0; i < output.length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), samples.length)
    let sum = 0
    for (let j = start; j < end; j++) sum += samples[j]
    output[i] = sum / Math.max(1, end - start)
  }
  return output
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeText = (offset, text) => [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)))

  writeText(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true) // format chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // bytes per second
  view.setUint16(32, 2, true) // bytes per sample
  view.setUint16(34, 16, true) // bits per sample
  writeText(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  })
  return new Blob([view], { type: 'audio/wav' })
}
