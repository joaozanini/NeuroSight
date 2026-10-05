interface CheckCircleFilledProps {
  size?: number
  className?: string
}

// Círculo cheio com o check branco (regras de senha cumpridas, arquivo enviado, item pronto).
// A cor do círculo vem de `color` (currentColor).
export default function CheckCircleFilled({ size = 20, className }: CheckCircleFilledProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" focusable="false" className={className}>
      <circle cx="10" cy="10" r="10" fill="currentColor" />
      <path d="m6 10.3 2.7 2.7L14.2 7.4" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
