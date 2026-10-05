interface SparklineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
  // Descrição para leitores de tela; sem ela o gráfico é decorativo.
  label?: string
}

// Linha de tendência dos cartões de KPI (W04), em SVG puro.
export default function Sparkline({ values, width = 96, height = 24, color = 'var(--color-primary)', label }: SparklineProps) {
  if (values.length < 2) return null
  const pad = 2
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = (width - pad * 2) / (values.length - 1)
  const points = values
    .map((v, i) => {
      const x = pad + i * step
      const y = height - pad - ((v - min) / span) * (height - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
