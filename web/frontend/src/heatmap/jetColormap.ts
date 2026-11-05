// LUT JET de 256 entradas (azul -> ciano -> verde -> amarelo -> vermelho), equivalente ao
// cv2.COLORMAP_JET usado no tools/heatmap_overlay.py. Aproximação analítica padrão do "jet".

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}

function jetValue(v: number): [number, number, number] {
  const r = clamp01(Math.min(4 * v - 1.5, -4 * v + 4.5))
  const g = clamp01(Math.min(4 * v - 0.5, -4 * v + 3.5))
  const b = clamp01(Math.min(4 * v + 0.5, -4 * v + 2.5))
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)]
}

export const JET_LUT: Array<[number, number, number]> = Array.from({ length: 256 }, (_, i) =>
  jetValue(i / 255),
)
