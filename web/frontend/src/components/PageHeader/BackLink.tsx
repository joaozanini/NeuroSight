import { Link } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './PageHeader.module.css'

interface BackLinkProps {
  to: string
  label: string
  className?: string
}

// "‹ Pacientes": volta para a tela de cima (W07, W08, W11, W13...) ou para o login (W02).
export default function BackLink({ to, label, className }: BackLinkProps) {
  return (
    <Link to={to} className={cx(styles.back, className)}>
      <ChevronLeft size={18} strokeWidth={2.25} aria-hidden />
      {label}
    </Link>
  )
}
