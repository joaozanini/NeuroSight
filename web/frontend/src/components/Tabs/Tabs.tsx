import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Tabs.module.css'

export interface TabItem {
  label: string
  icon?: LucideIcon
  // Com `to`, cada aba é uma rota (ex.: Administração: Usuários, Perfis e permissões, Auditoria).
  to?: string
  end?: boolean
  // Sem `to`, as abas trocam um painel na mesma página: `value` identifica a aba e `panelId`
  // aponta o painel que ela controla.
  value?: string
  panelId?: string
}

interface TabsProps {
  items: TabItem[]
  ariaLabel: string
  value?: string
  onChange?: (value: string) => void
  className?: string
}

export default function Tabs({ items, ariaLabel, value, onChange, className }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null)

  if (items.every((item) => item.to)) {
    return (
      <nav aria-label={ariaLabel} className={cx(styles.tabs, className)}>
        {items.map(({ label, icon: Icon, to, end }) => (
          <NavLink key={to} to={to!} end={end} className={({ isActive }) => cx(styles.tab, isActive && styles.active)}>
            {Icon && <Icon size={18} aria-hidden />}
            {label}
          </NavLink>
        ))}
      </nav>
    )
  }

  // Setas e Home/End movem entre as abas, como no padrão de tablist.
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End']
    if (!keys.includes(event.key)) return
    event.preventDefault()
    const values = items.map((i) => i.value!)
    const current = Math.max(0, values.indexOf(value ?? ''))
    let next = current
    if (event.key === 'ArrowRight') next = (current + 1) % values.length
    if (event.key === 'ArrowLeft') next = (current - 1 + values.length) % values.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = values.length - 1
    onChange?.(values[next])
    listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
  }

  return (
    <div ref={listRef} role="tablist" aria-label={ariaLabel} className={cx(styles.tabs, className)} onKeyDown={onKeyDown}>
      {items.map(({ label, icon: Icon, value: itemValue, panelId }) => {
        const selected = itemValue === value
        return (
          <button
            key={itemValue}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            className={cx(styles.tab, selected && styles.active)}
            onClick={() => onChange?.(itemValue!)}
          >
            {Icon && <Icon size={18} aria-hidden />}
            {label}
          </button>
        )
      })}
    </div>
  )
}
