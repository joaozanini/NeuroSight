import type { AnchorHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'
import { ButtonContent } from './Button'
import { buttonClassName } from './buttonLook'
import type { ButtonLookProps } from './buttonLook'

export type AnchorButtonProps = AnchorHTMLAttributes<HTMLAnchorElement> & ButtonLookProps

// Link comum com cara de botão, para o que sai do site: os downloads ("Baixar", "Baixar JSON").
export default function AnchorButton({
  variant,
  size,
  icon,
  iconRight,
  block,
  className,
  children,
  ...rest
}: AnchorButtonProps) {
  return (
    <a className={cx(buttonClassName({ variant, size, block }, Boolean(icon)), className)} {...rest}>
      <ButtonContent icon={icon} iconRight={iconRight} size={size}>
        {children}
      </ButtonContent>
    </a>
  )
}
