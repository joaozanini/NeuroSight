// A gravação da sessão com o olhar por cima (W17), herdeira do modo de validação do viewer antigo.
// O MP4 tem fps constante, mas os frames foram capturados em instantes próprios (`frame_t`): o
// instante da sessão sai do índice do frame, e não do tempo do vídeo, para o círculo não derrapar.

// Índice do frame que o vídeo mostra em `currentTime`.
export function frameIndexAt(currentTime: number, fps: number, count: number): number {
  if (count === 0) return -1
  return Math.min(count - 1, Math.max(0, Math.floor(currentTime * fps + 1e-6)))
}

// Instante da sessão (segundos) que o vídeo mostra.
export function sessionTimeAt(currentTime: number, fps: number, frameT: readonly number[]): number {
  const i = frameIndexAt(currentTime, fps, frameT.length)
  return i < 0 ? currentTime : frameT[i]
}

// Tempo do vídeo que mostra o instante `t` da sessão: o primeiro frame a partir dele.
export function videoTimeAt(t: number, fps: number, frameT: readonly number[]): number {
  let lo = 0
  let hi = frameT.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (frameT[mid] < t) lo = mid + 1
    else hi = mid
  }
  const i = Math.min(lo, frameT.length - 1)
  // Um pouco depois do começo do frame, para o navegador não parar no anterior.
  return i < 0 ? 0 : (i + 0.01) / fps
}

// O círculo do olhar: anel azul com um ponto no centro, como no protótipo.
export function drawGazeCircle(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number) {
  ctx.lineWidth = Math.max(2, radius / 5)
  ctx.strokeStyle = 'rgba(59, 91, 240, 0.95)'
  ctx.fillStyle = 'rgba(59, 91, 240, 0.18)'
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = 'rgba(45, 73, 214, 0.95)'
  ctx.beginPath()
  ctx.arc(x, y, radius * 0.38, 0, Math.PI * 2)
  ctx.fill()
}
