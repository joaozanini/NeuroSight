// Mapa de calor do olhar sobre o estímulo (W17), portado do tools/heatmap_overlay.py do fluxo antigo:
// cada célula com olhar espalha uma gaussiana (raio 3σ), com o peso do tempo de olhar, num acumulador
// em resolução reduzida; o acumulador é normalizado pelo pico e pintado pela paleta, com
// transparência, para o estímulo aparecer por baixo. Depois o canvas escala a imagem com suavização.

// [u, v, peso]: posição no estímulo (0 a 1, origem em cima à esquerda) e quanto tempo de olhar.
export type HeatPoint = readonly [number, number, number]

// Espalha os pontos num acumulador accW × accH; `sigma` é o desvio da gaussiana em pixels dele.
export function accumulate(points: readonly HeatPoint[], accW: number, accH: number, sigma: number): Float32Array {
  const acc = new Float32Array(accW * accH)
  const sig = Math.max(0.5, sigma)
  const s2 = 2 * sig * sig
  const r = Math.max(1, Math.floor(3 * sig))
  for (const [u, v, weight] of points) {
    if (weight <= 0) continue
    const cx = Math.round(u * accW)
    const cy = Math.round(v * accH)
    const x0 = Math.max(0, cx - r), x1 = Math.min(accW, cx + r + 1)
    const y0 = Math.max(0, cy - r), y1 = Math.min(accH, cy + r + 1)
    for (let y = y0; y < y1; y++) {
      const dy = y - cy
      const gy = Math.exp(-(dy * dy) / s2)
      const row = y * accW
      for (let x = x0; x < x1; x++) {
        const dx = x - cx
        acc[row + x] += weight * gy * Math.exp(-(dx * dx) / s2)
      }
    }
  }
  return acc
}

// Normaliza pelo pico e pinta com a paleta (256 cores RGBA); abaixo de 2% do pico fica transparente.
export function paint(acc: Float32Array, accW: number, accH: number, lut: Uint8ClampedArray): ImageData | null {
  let peak = 0
  for (let i = 0; i < acc.length; i++) if (acc[i] > peak) peak = acc[i]
  if (peak <= 1e-8) return null
  const img = new ImageData(accW, accH)
  const data = img.data
  for (let i = 0; i < acc.length; i++) {
    const norm = acc[i] / peak
    if (norm <= 0.02) continue
    const k = Math.min(255, Math.round(norm * 255)) * 4
    const o = i * 4
    data[o] = lut[k]
    data[o + 1] = lut[k + 1]
    data[o + 2] = lut[k + 2]
    data[o + 3] = lut[k + 3]
  }
  return img
}
