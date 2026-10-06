// Paleta azul do mapa de calor (W17): do azul claro e quase transparente, onde o paciente olhou
// pouco, ao azul da marca e mais opaco, onde olhou mais. A legenda "Menos tempo / Mais tempo de
// olhar" usa as duas pontas (HEAT_LEGEND).

const LIGHT = [143, 163, 255]
const STRONG = [43, 70, 214]
const MAX_ALPHA = 0.82

export const BLUE_LUT: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 4)
  for (let i = 0; i < 256; i++) {
    const t = i / 255
    for (let c = 0; c < 3; c++) lut[i * 4 + c] = Math.round(LIGHT[c] + (STRONG[c] - LIGHT[c]) * t)
    lut[i * 4 + 3] = Math.round(255 * MAX_ALPHA * Math.pow(t, 0.7))
  }
  return lut
})()

export const HEAT_LEGEND = `linear-gradient(90deg, rgba(${LIGHT.join(', ')}, 0.25), rgba(${STRONG.join(', ')}, ${MAX_ALPHA}))`
