import { createLucideIcon } from 'lucide-react'

// Ícone de "Início" dos protótipos (quatro círculos), no mesmo traço dos ícones do lucide.
const HomeIcon = createLucideIcon('neurosight-home', [
  ['circle', { cx: '6.5', cy: '6.5', r: '3.5', key: 'top-left' }],
  ['circle', { cx: '17.5', cy: '6.5', r: '3.5', key: 'top-right' }],
  ['circle', { cx: '6.5', cy: '17.5', r: '3.5', key: 'bottom-left' }],
  ['circle', { cx: '17.5', cy: '17.5', r: '3.5', key: 'bottom-right' }],
])

export default HomeIcon
