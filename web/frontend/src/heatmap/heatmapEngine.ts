// Porta fiel do algoritmo de tools/heatmap_overlay.py (modo heatmap), rodando no canvas.
//
// Para o tempo de gaze t: amostras válidas com uv em [0,1] na janela [t-W, t] fazem splat de
// uma gaussiana (raio 3σ) num acumulador float, com peso de decay linear max(0, 1-age/W).
// Normaliza pelo pico, aplica JET e gera RGBA com alpha onde norm > 0.02 (transparente no resto,
// porque o vídeo aparece por baixo). Tudo em "quarter-res" por performance e depois é escalado.

import type { GazeSample } from './types'
import { JET_LUT } from './jetColormap'

export function renderHeatmapImageData(
  validSamples: GazeSample[],
  gazeTime: number,
  accW: number,
  accH: number,
  frameWidth: number,
  sigma: number,
  window: number,
  alpha: number,
): ImageData | null {
  const scale = accW / Math.max(1, frameWidth)
  const sig = Math.max(0.5, sigma * scale)
  const s2 = 2 * sig * sig
  const r = Math.max(1, Math.floor(3 * sig))
  const t0 = gazeTime - window
  const w = Math.max(window, 1e-6)

  const acc = new Float32Array(accW * accH)
  let any = false

  for (const s of validSamples) {
    if (s.t < t0 || s.t > gazeTime) continue
    const weight = 1 - (gazeTime - s.t) / w // decay linear
    if (weight <= 0) continue

    const cx = Math.round(s.uv[0] * accW)
    const cy = Math.round(s.uv[1] * accH)
    const x0 = Math.max(0, cx - r), x1 = Math.min(accW, cx + r + 1)
    const y0 = Math.max(0, cy - r), y1 = Math.min(accH, cy + r + 1)

    for (let y = y0; y < y1; y++) {
      const dy = y - cy
      const gy = Math.exp(-(dy * dy) / s2)
      const row = y * accW
      for (let x = x0; x < x1; x++) {
        const dx = x - cx
        acc[row + x] += weight * gy * Math.exp(-(dx * dx) / s2)
        any = true
      }
    }
  }

  if (!any) return null

  let peak = 0
  for (let i = 0; i < acc.length; i++) if (acc[i] > peak) peak = acc[i]
  if (peak <= 1e-8) return null

  const img = new ImageData(accW, accH)
  const data = img.data
  const a = Math.round(clamp01(alpha) * 255)

  for (let i = 0; i < acc.length; i++) {
    const norm = acc[i] / peak
    const o = i * 4
    if (norm > 0.02) {
      const [rr, gg, bb] = JET_LUT[Math.min(255, Math.round(norm * 255))]
      data[o] = rr
      data[o + 1] = gg
      data[o + 2] = bb
      data[o + 3] = a
    } else {
      data[o + 3] = 0
    }
  }
  return img
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}
