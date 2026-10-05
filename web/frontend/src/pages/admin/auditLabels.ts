import type { Permission } from '../../api/auth'
import type { Option } from '../../api/audit'

// Rótulo de um código (ação, tipo de item, perfil) a partir das opções que o servidor manda.
export function labelOf(options: Option[] | undefined, value: string | null | undefined): string {
  if (!value) return ''
  return options?.find((o) => o.value === value)?.label ?? value
}

// Para onde leva o "Abrir ..." do item afetado (W23). Sessões, pacientes e estímulos chegam nas
// fases 2 e 3; a rota já existe.
export const ENTITY_LINKS: Record<string, { to: (id: string) => string; label: string; permission?: Permission }> = {
  session: { to: (id) => `/sessoes/${id}`, label: 'Abrir sessão' },
  patient: { to: (id) => `/pacientes/${id}`, label: 'Abrir paciente' },
  stimulus: { to: (id) => `/estimulos/${id}`, label: 'Abrir estímulo' },
  user: { to: (id) => `/admin/usuarios/${id}`, label: 'Abrir usuário', permission: 'admin.users' },
  permissions: { to: () => '/admin/permissoes', label: 'Abrir permissões', permission: 'admin.permissions' },
}
