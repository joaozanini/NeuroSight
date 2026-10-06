interface LogoProps {
  size?: number
  className?: string
  // Sem título o símbolo é decorativo (o nome "NeuroSight" costuma estar ao lado).
  title?: string
  // badge: o símbolo branco no quadrado azul; mark: só o traço azul (topo da W15, painéis do óculos).
  variant?: 'badge' | 'mark'
}

// Símbolo da marca: três pontos ligados (o olhar passando por pontos de fixação).
export default function Logo({ size = 36, className, title, variant = 'badge' }: LogoProps) {
  if (variant === 'mark') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="4 5 22 22"
        className={className}
        role={title ? 'img' : undefined}
        aria-hidden={title ? undefined : true}
        focusable="false"
        fill="none"
        stroke="#3b5bf0"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {title && <title>{title}</title>}
        <path d="M12.7 11.3 18.1 12.1M18.9 14.2 15.9 17.9M10.4 13.9 12.4 17" />
        <circle cx="9.75" cy="11" r="2.9" />
        <circle cx="20.2" cy="12.4" r="2.1" />
        <circle cx="13.75" cy="20.4" r="3.7" />
      </svg>
    )
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      className={className}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title && <title>{title}</title>}
      <rect width="36" height="36" rx="10" fill="#3b5bf0" />
      <circle cx="13.75" cy="20.4" r="3.7" fill="#d8defc" />
      <path
        d="M9.75 11 20.2 12.4 13.75 20.4"
        fill="none"
        stroke="#fff"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="9.75" cy="11" r="3" fill="#fff" />
      <circle cx="20.2" cy="12.4" r="2.1" fill="#fff" />
    </svg>
  )
}
