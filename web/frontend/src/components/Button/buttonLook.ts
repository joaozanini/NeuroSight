import type { LucideIcon } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Button.module.css'

// primary: ação principal (azul cheio); secondary: contorno azul; danger: contorno vermelho
// (zona de perigo); danger-subtle: contorno vermelho claro ("Interromper sessão"); text e
// text-danger: ações em linha sem sublinhado ("Reenviar convite", "Desativar", "Remover").
export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'danger-subtle' | 'text' | 'text-danger'

// lg: 52 px (login); md: 48 px (padrão); sm: 44 px (dentro de cartões e modais, paginação).
export type ButtonSize = 'lg' | 'md' | 'sm'

export interface ButtonLookProps {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
  iconRight?: LucideIcon
  block?: boolean
}

export const ICON_SIZE: Record<ButtonSize, number> = { lg: 22, md: 20, sm: 18 }

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: styles.primary,
  secondary: styles.secondary,
  danger: styles.danger,
  'danger-subtle': styles.dangerSubtle,
  text: styles.text,
  'text-danger': styles.textDanger,
}

export function buttonClassName(
  { variant = 'primary', size = 'md', block = false }: ButtonLookProps,
  hasIcon = false,
) {
  const isText = variant === 'text' || variant === 'text-danger'
  return cx(
    styles.button,
    VARIANT_CLASS[variant],
    !isText && styles[size],
    !isText && hasIcon && styles.withIcon,
    block && styles.block,
  )
}
