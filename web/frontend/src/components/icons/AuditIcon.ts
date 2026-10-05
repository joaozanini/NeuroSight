import { createLucideIcon } from 'lucide-react'

// Ícone da aba "Auditoria" (folha com linhas de texto), no traço dos ícones do lucide.
const AuditIcon = createLucideIcon('neurosight-audit', [
  ['rect', { x: '5', y: '3', width: '14', height: '18', rx: '2.5', key: 'sheet' }],
  ['path', { d: 'M9 8.5h6', key: 'line-1' }],
  ['path', { d: 'M9 12h6', key: 'line-2' }],
  ['path', { d: 'M9 15.5h3.5', key: 'line-3' }],
])

export default AuditIcon
