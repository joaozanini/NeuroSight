import { useRef, useState } from 'react'
import type { DragEvent } from 'react'

// Estado de "arrastando por cima" e handlers de soltar arquivos. O contador evita piscar
// quando o ponteiro passa pelos elementos filhos da área.
export function useFileDrop(onFiles: (files: File[]) => void, disabled = false) {
  const [dragging, setDragging] = useState(false)
  const depth = useRef(0)

  const hasFiles = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes('Files')

  return {
    dragging,
    dropProps: {
      onDragEnter(event: DragEvent) {
        if (disabled || !hasFiles(event)) return
        event.preventDefault()
        depth.current += 1
        setDragging(true)
      },
      onDragOver(event: DragEvent) {
        if (disabled || !hasFiles(event)) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
      },
      onDragLeave(event: DragEvent) {
        if (disabled || !hasFiles(event)) return
        depth.current = Math.max(0, depth.current - 1)
        if (depth.current === 0) setDragging(false)
      },
      onDrop(event: DragEvent) {
        if (disabled) return
        event.preventDefault()
        depth.current = 0
        setDragging(false)
        const files = Array.from(event.dataTransfer?.files ?? [])
        if (files.length) onFiles(files)
      },
    },
  }
}
