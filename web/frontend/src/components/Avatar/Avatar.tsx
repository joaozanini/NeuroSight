import { cx } from '../../lib/cx'
import { initials } from '../../lib/format'
import styles from './Avatar.module.css'

interface AvatarProps {
  name: string
  size?: number
  className?: string
}

// Iniciais num círculo azul-claro ("AS" para Ana Souza), como no menu lateral.
export default function Avatar({ name, size = 38, className }: AvatarProps) {
  return (
    <span
      className={cx(styles.avatar, className)}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4) }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}
