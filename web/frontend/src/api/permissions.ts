// Matriz de perfis e permissões (W21). O catálogo vem do servidor, que é quem aplica as regras.
import { api } from './client'
import type { Permission, Role } from './auth'

export interface PermissionMatrix {
  roles: { id: Role; label: string; description: string }[]
  groups: { label: string; permissions: { id: Permission; label: string; description: string | null }[] }[]
  grants: Record<Role, Permission[]>
  locked: Partial<Record<Role, Permission[]>>
}

export type Grants = Record<Role, Permission[]>

export const PERMISSIONS_KEY = ['permissions'] as const

export const permissionsApi = {
  get: (signal?: AbortSignal) => api.get<PermissionMatrix>('/permissions', { signal }),
  save: (grants: Grants) => api.put<PermissionMatrix>('/permissions', { grants }),
}
