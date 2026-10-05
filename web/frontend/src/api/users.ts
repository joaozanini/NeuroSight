// Administração de usuários (W19, W20).
import { api } from './client'
import type { Role } from './auth'
import type { UserStatus } from '../lib/status'

export interface UserSummary {
  id: string
  name: string
  email: string
  role: Role
  status: UserStatus
  last_login_at: string | null
  created_at: string
}

export interface UserDetail extends UserSummary {
  created_by_name: string | null
  sessions_as_owner: number
}

export interface UserPage {
  items: UserSummary[]
  total: number
  page: number
  page_size: number
}

export interface UserFilters {
  q?: string
  role?: Role | ''
  status?: UserStatus | ''
  page?: number
}

// Resultado de um convite ou redefinição: `link` só vem quando o e-mail não saiu.
export interface LinkResult {
  email_sent: boolean
  link: string | null
  expires_at: string
}

export interface UserInput {
  name: string
  email: string
  role: Role
}

export interface UserUpdate extends Partial<UserInput> {
  status?: 'active' | 'inactive'
}

export const USERS_PAGE_SIZE = 8

export const ROLE_LABELS: Record<Role, string> = { admin: 'Admin', researcher: 'Pesquisador' }

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  researcher: 'Cadastra pacientes e estímulos, configura e executa sessões e analisa os dados.',
  admin: 'Tudo o que o pesquisador faz, mais usuários, permissões, visibilidade das sessões e auditoria.',
}

export const usersKeys = {
  all: ['users'] as const,
  list: (filters: UserFilters) => ['users', 'list', filters] as const,
  detail: (id: string) => ['users', 'detail', id] as const,
}

export const usersApi = {
  list: (filters: UserFilters, signal?: AbortSignal) =>
    api.get<UserPage>('/users', { signal, query: { ...filters, page_size: USERS_PAGE_SIZE } }),
  get: (id: string, signal?: AbortSignal) => api.get<UserDetail>(`/users/${encodeURIComponent(id)}`, { signal }),
  create: (input: UserInput) => api.post<{ user: UserDetail; invite: LinkResult }>('/users', input),
  update: (id: string, input: UserUpdate) => api.patch<UserDetail>(`/users/${encodeURIComponent(id)}`, input),
  resendInvite: (id: string) => api.post<LinkResult>(`/users/${encodeURIComponent(id)}/resend-invite`),
  sendReset: (id: string) => api.post<LinkResult>(`/users/${encodeURIComponent(id)}/send-reset`),
}
