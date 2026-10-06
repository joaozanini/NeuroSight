import { Globe, Lock, Users } from 'lucide-react'
import { VISIBILITY_LABELS } from '../../api/sessions'
import type { Visibility } from '../../api/sessions'
import { cx } from '../../lib/cx'
import styles from './VisibilityLabel.module.css'

const ICONS = { private: Lock, shared: Users, all: Globe }

// "🔒 Privada", "👥 Compartilhada" ou "🌐 Aberta a todos" (W12, W16).
export default function VisibilityLabel({ visibility, className }: { visibility: Visibility; className?: string }) {
  const Icon = ICONS[visibility]
  return (
    <span className={cx(styles.label, className)}>
      <Icon size={20} strokeWidth={1.75} aria-hidden />
      {VISIBILITY_LABELS[visibility]}
    </span>
  )
}
