// Formato do olhar e dos frames de vídeo do gaze.json do fluxo antigo (contrato v1).
// O heatmap só precisa destes campos; a análise do contrato v2 vai adaptá-los.

export interface GazeSample {
  t: number
  valid: boolean
  uv: [number, number]
  world?: number[]
  confidence?: number
}

export interface GazeFrame {
  idx: number
  t: number
  file: string
}
