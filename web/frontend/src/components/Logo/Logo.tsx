interface LogoProps {
  size?: number
  className?: string
  // Sem título o símbolo é decorativo (o nome "NeuroSight" costuma estar ao lado).
  title?: string
}

// Símbolo da marca: três pontos ligados (o olhar passando por pontos de fixação).
export default function Logo({ size = 36, className, title }: LogoProps) {
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
