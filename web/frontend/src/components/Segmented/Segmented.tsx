import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { cx } from '../../lib/cx'
import styles from './Segmented.module.css'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  ariaLabel: string
  className?: string
}

// Escolha única entre poucas opções ("Todos / Imagens / Vídeos", "Mapa de calor / Trajetória").
export default function Segmented<T extends string>({ options, value, onChange, ariaLabel, className }: SegmentedProps<T>) {
  const groupRef = useRef<HTMLDivElement>(null)

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const delta = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
    if (!delta) return
    event.preventDefault()
    const current = Math.max(0, options.findIndex((o) => o.value === value))
    const next = (current + delta + options.length) % options.length
    onChange(options[next].value)
    groupRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus()
  }

  return (
    <div ref={groupRef} role="radiogroup" aria-label={ariaLabel} className={cx(styles.segmented, className)} onKeyDown={onKeyDown}>
      {options.map((option) => {
        const checked = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            className={cx(styles.option, checked && styles.checked)}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
