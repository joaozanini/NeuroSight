// Usuários e respostas de exemplo para os testes, com os nomes dos protótipos.
import type { Me, Permission } from '../api/auth'

export const ALL_PERMISSIONS: Permission[] = [
  'patients.view',
  'patients.edit',
  'patients.deactivate',
  'stimuli.edit',
  'stimuli.archive',
  'sessions.run',
  'sessions.view_all',
  'sessions.visibility',
  'sessions.export',
  'admin.users',
  'admin.permissions',
  'admin.audit',
]

export const ADMIN: Me = {
  id: 'u1',
  name: 'Carlos Lima',
  email: 'carlos.lima@exemplo.com',
  role: 'admin',
  role_label: 'Admin',
  permissions: ALL_PERMISSIONS,
}

export const RESEARCHER: Me = {
  id: 'u2',
  name: 'Ana Souza',
  email: 'ana.souza@exemplo.com',
  role: 'researcher',
  role_label: 'Pesquisador',
  permissions: ['patients.view', 'patients.edit', 'stimuli.edit', 'sessions.run', 'sessions.export'],
}
