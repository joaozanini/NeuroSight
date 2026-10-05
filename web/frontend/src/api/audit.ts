// Auditoria (W22, W23): lista, detalhe e o endereço do CSV. Os rótulos das ações e dos tipos de
// item vêm do servidor (GET /audit/filters), o mesmo que escreve o CSV.
import { api, buildUrl } from './client'

export interface AuditItem {
  id: number
  created_at: string
  user_id: string | null
  user_name: string | null
  user_role: string | null
  action: string
  entity_type: string
  entity_id: string | null
  entity_label: string
  ip: string | null
}

export interface AuditChange {
  field: string
  label: string
  before: string | null
  after: string | null
}

export interface AuditDetail extends AuditItem {
  user_agent: string | null
  changes: AuditChange[]
}

export interface AuditPage {
  items: AuditItem[]
  total: number
  page: number
  page_size: number
}

export interface Option {
  value: string
  label: string
}

export interface AuditFilterOptions {
  actions: Option[]
  entity_types: Option[]
  roles: Option[]
  users: Option[]
}

export interface AuditQuery {
  since?: string
  user_id?: string
  action?: string
  entity_type?: string
}

export const AUDIT_PAGE_SIZE = 10

export const auditKeys = {
  all: ['audit'] as const,
  filters: ['audit', 'filters'] as const,
  list: (query: AuditQuery, page: number) => ['audit', 'list', query, page] as const,
  detail: (id: number) => ['audit', 'detail', id] as const,
}

export const auditApi = {
  filters: (signal?: AbortSignal) => api.get<AuditFilterOptions>('/audit/filters', { signal }),
  list: (query: AuditQuery, page: number, signal?: AbortSignal) =>
    api.get<AuditPage>('/audit', { signal, query: { ...query, page, page_size: AUDIT_PAGE_SIZE } }),
  get: (id: number, signal?: AbortSignal) => api.get<AuditDetail>(`/audit/${id}`, { signal }),
  // O navegador baixa direto (o cookie vai junto); as datas saem no fuso de quem exporta.
  exportUrl: (query: AuditQuery) =>
    buildUrl('/audit/export.csv', { ...query, tz: Intl.DateTimeFormat().resolvedOptions().timeZone }),
}
