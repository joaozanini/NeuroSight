import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

// Largura do elemento, acompanhando o redimensionamento (gráficos em SVG desenhados em pixels reais).
// Sem ResizeObserver (testes), fica a largura de reserva.
export function useElementWidth(ref: RefObject<HTMLElement | null>, fallback: number): number {
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const element = ref.current
    if (!element || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry.contentRect.width)
      if (next > 0) setWidth(next)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return width
}
