import { Link } from 'react-router-dom'
import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from 'react'
import type { LinkProps } from 'react-router-dom'
import { cx } from '../../lib/cx'
import styles from './TextLink.module.css'

interface TextLinkLook {
  tone?: 'primary' | 'danger'
  // Links sublinhados são o padrão dos protótipos ("Esqueci minha senha", "Editar", "Ver sessão");
  // nomes clicáveis em tabelas ficam sem sublinhado.
  underline?: boolean
}

type RouterLinkProps = TextLinkLook & LinkProps & { href?: never }
type AnchorProps = TextLinkLook & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; to?: never }
type ButtonLinkProps = TextLinkLook & ButtonHTMLAttributes<HTMLButtonElement> & { to?: never; href?: never }

export type TextLinkProps = RouterLinkProps | AnchorProps | ButtonLinkProps

// Link de texto: navega (to), abre um endereço (href) ou executa uma ação com cara de link.
export default function TextLink(props: TextLinkProps) {
  const { tone = 'primary', underline = true, className, ...rest } = props
  const classes = cx(styles.link, tone === 'danger' && styles.danger, !underline && styles.plain, className)
  if ('to' in rest && rest.to !== undefined) {
    return <Link className={classes} {...(rest as LinkProps)} />
  }
  if ('href' in rest && rest.href !== undefined) {
    return <a className={classes} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)} />
  }
  return <button type="button" className={classes} {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)} />
}
