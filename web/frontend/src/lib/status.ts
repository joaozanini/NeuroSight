// Rótulos e cores dos selos de status (W04, W08, W12, W19). As chaves são os valores que a API
// usa em snake_case; o ciclo da sessão é Configurada → Em andamento → Aguardando dados →
// Concluída ou Interrompida.

export type BadgeTone = 'info' | 'warning' | 'outline' | 'danger' | 'success' | 'neutral'

export interface StatusStyle {
  label: string
  tone: BadgeTone
  dot?: boolean
}

export type SessionStatus = 'configured' | 'running' | 'awaiting_data' | 'completed' | 'interrupted'
export type UserStatus = 'active' | 'invited' | 'inactive'
export type PatientStatus = 'active' | 'inactive'

export const SESSION_STATUS: Record<SessionStatus, StatusStyle> = {
  configured: { label: 'Configurada', tone: 'outline' },
  running: { label: 'Em andamento', tone: 'info', dot: true },
  awaiting_data: { label: 'Aguardando dados', tone: 'warning' },
  completed: { label: 'Concluída', tone: 'success' },
  interrupted: { label: 'Interrompida', tone: 'danger' },
}

export const USER_STATUS: Record<UserStatus, StatusStyle> = {
  active: { label: 'Ativo', tone: 'success' },
  invited: { label: 'Convite pendente', tone: 'warning' },
  inactive: { label: 'Inativo', tone: 'neutral' },
}

export const PATIENT_STATUS: Record<PatientStatus, StatusStyle> = {
  active: { label: 'Ativo', tone: 'success' },
  inactive: { label: 'Inativo', tone: 'neutral' },
}
