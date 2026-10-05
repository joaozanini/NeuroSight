// Login, usuário logado e permissões. O cookie de sessão é httpOnly: o front não vê o token, só
// pergunta ao servidor quem está logado (GET /me).
import { useQuery } from '@tanstack/react-query'
import { ApiError, api } from './client'

export type Role = 'admin' | 'researcher'

export type Permission =
  | 'patients.view'
  | 'patients.edit'
  | 'patients.deactivate'
  | 'stimuli.edit'
  | 'stimuli.archive'
  | 'sessions.run'
  | 'sessions.view_all'
  | 'sessions.visibility'
  | 'sessions.export'
  | 'admin.users'
  | 'admin.permissions'
  | 'admin.audit'

export interface Me {
  id: string
  name: string
  email: string
  role: Role
  role_label: string
  permissions: Permission[]
}

export type LinkKind = 'invite' | 'reset'

export interface LinkInfo {
  kind: LinkKind
  name: string
  email: string
}

export const ME_KEY = ['me'] as const

// Quem está logado. Sem sessão, o erro é um ApiError 401 (sem redirecionar: quem decide é a guarda).
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: ({ signal }) => api.get<Me>('/me', { signal, redirectOnUnauthorized: false }),
    staleTime: 60_000,
  })
}

// O usuário logado, para as telas que só abrem depois da guarda de login (RequireAuth).
export function useCurrentUser(): Me {
  const { data } = useMe()
  if (!data) throw new Error('useCurrentUser fora da área logada')
  return data
}

export function hasPermission(me: Pick<Me, 'permissions'> | undefined, permission: Permission): boolean {
  return Boolean(me?.permissions.includes(permission))
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export const authApi = {
  login: (email: string, password: string) => api.post<Me>('/auth/login', { email, password }, { redirectOnUnauthorized: false }),
  logout: () => api.post<void>('/auth/logout', undefined, { redirectOnUnauthorized: false }),
  forgot: (email: string) => api.post<void>('/auth/forgot', { email }),
  linkInfo: (token: string, kind: LinkKind) => api.get<LinkInfo>('/auth/link', { query: { token, kind } }),
  setPassword: (kind: LinkKind, token: string, password: string) =>
    api.post<Me>(kind === 'invite' ? '/auth/accept-invite' : '/auth/reset-password', { token, password }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.put<void>('/me/password', { current_password: currentPassword, new_password: newPassword }),
}

// Para onde voltar depois do login (?next=). Só caminhos deste site: nada de "//outro.site".
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/'
  return next
}
