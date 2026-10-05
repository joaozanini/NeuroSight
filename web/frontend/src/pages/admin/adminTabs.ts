import { ShieldCheck, UsersRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { hasPermission } from '../../api/auth'
import type { Me, Permission } from '../../api/auth'
import AuditIcon from '../../components/icons/AuditIcon'

export interface AdminTab {
  label: string
  icon: LucideIcon
  to: string
  permission: Permission
}

// Abas da Administração (W19, W21, W22), cada uma com a permissão que a libera.
export const ADMIN_TABS: AdminTab[] = [
  { label: 'Usuários', icon: UsersRound, to: '/admin/usuarios', permission: 'admin.users' },
  { label: 'Perfis e permissões', icon: ShieldCheck, to: '/admin/permissoes', permission: 'admin.permissions' },
  { label: 'Auditoria', icon: AuditIcon, to: '/admin/auditoria', permission: 'admin.audit' },
]

export function allowedAdminTabs(me: Pick<Me, 'permissions'>): AdminTab[] {
  return ADMIN_TABS.filter((tab) => hasPermission(me, tab.permission))
}
