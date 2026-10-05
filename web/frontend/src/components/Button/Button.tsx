import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import Spinner from '../Spinner/Spinner'
import { ICON_SIZE, buttonClassName } from './buttonLook'
import type { ButtonLookProps } from './buttonLook'

export function ButtonContent({
  icon: Icon,
  iconRight: IconRight,
  size = 'md',
  loading = false,
  children,
}: ButtonLookProps & { loading?: boolean; children?: ReactNode }) {
  const iconSize = ICON_SIZE[size]
  return (
    <>
      {loading ? <Spinner size={iconSize} /> : Icon && <Icon size={iconSize} aria-hidden />}
      {children}
      {IconRight && <IconRight size={iconSize} aria-hidden />}
    </>
  )
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, ButtonLookProps {
  loading?: boolean
}

export default function Button({
  variant,
  size,
  icon,
  iconRight,
  block,
  loading = false,
  disabled,
  type = 'button',
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(buttonClassName({ variant, size, block }, Boolean(icon) || loading), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      <ButtonContent icon={icon} iconRight={iconRight} size={size} loading={loading}>
        {children}
      </ButtonContent>
    </button>
  )
}
