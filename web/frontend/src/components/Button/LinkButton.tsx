import { Link } from 'react-router-dom'
import type { LinkProps } from 'react-router-dom'
import { cx } from '../../lib/cx'
import { ButtonContent } from './Button'
import { buttonClassName } from './buttonLook'
import type { ButtonLookProps } from './buttonLook'

export type LinkButtonProps = LinkProps & ButtonLookProps

// Navegação com cara de botão ("Novo paciente", "Nova sessão", "Abrir controle").
export default function LinkButton({
  variant,
  size,
  icon,
  iconRight,
  block,
  className,
  children,
  ...rest
}: LinkButtonProps) {
  return (
    <Link className={cx(buttonClassName({ variant, size, block }, Boolean(icon)), className)} {...rest}>
      <ButtonContent icon={icon} iconRight={iconRight} size={size}>
        {children}
      </ButtonContent>
    </Link>
  )
}
