// Mapa das telas dos protótipos (web/docs/pages) ainda não implementadas para as rotas do site:
// cada rota mostra um placeholder com o título, o link de voltar e a fase do plano. Ao implementar
// uma tela, troque o placeholder pela página no App.tsx e tire-a daqui.

export interface ScreenRoute {
  path: string
  title: string
  // Códigos dos protótipos que a rota cobre (modais entram junto da tela de baixo).
  prototypes: string[]
  phase: number
  subtitle?: string
  back?: { to: string; label: string }
}

// Telas internas, no AppLayout (menu lateral).
export const APP_SCREENS: ScreenRoute[] = [
  { path: '/', title: 'Início', prototypes: ['W04'], phase: 6 },

  { path: '/sessoes', title: 'Sessões', prototypes: ['W12'], phase: 3, subtitle: 'Suas sessões e as que outros pesquisadores liberaram para você.' },
  { path: '/sessoes/nova', title: 'Nova sessão', prototypes: ['W13'], phase: 3, back: { to: '/sessoes', label: 'Sessões' } },
  { path: '/sessoes/:sessionId', title: 'Detalhes da sessão', prototypes: ['W16', 'W18'], phase: 3, back: { to: '/sessoes', label: 'Sessões' } },
  { path: '/sessoes/:sessionId/preparar', title: 'Preparar sessão', prototypes: ['W14'], phase: 4, back: { to: '/sessoes', label: 'Sessões' } },
  {
    path: '/sessoes/:sessionId/analise',
    title: 'Análise da sessão',
    prototypes: ['W17'],
    phase: 5,
    back: { to: '/sessoes/:sessionId', label: 'Detalhes da sessão' },
  },

  { path: '/pacientes', title: 'Pacientes', prototypes: ['W06'], phase: 2 },
  { path: '/pacientes/novo', title: 'Novo paciente', prototypes: ['W07'], phase: 2, back: { to: '/pacientes', label: 'Pacientes' } },
  { path: '/pacientes/:patientId', title: 'Detalhes do paciente', prototypes: ['W08'], phase: 2, back: { to: '/pacientes', label: 'Pacientes' } },
  {
    path: '/pacientes/:patientId/editar',
    title: 'Editar paciente',
    prototypes: ['W07'],
    phase: 2,
    subtitle: 'As alterações ficam registradas na auditoria.',
    back: { to: '/pacientes/:patientId', label: 'Paciente' },
  },

  { path: '/estimulos', title: 'Estímulos', prototypes: ['W09', 'W10'], phase: 2 },
  { path: '/estimulos/:stimulusId', title: 'Detalhes do estímulo', prototypes: ['W11'], phase: 2, back: { to: '/estimulos', label: 'Estímulos' } },
]

// Tela cheia, sem menu.
export const FULLSCREEN_SCREENS: ScreenRoute[] = [
  { path: '/sessoes/:sessionId/controle', title: 'Controle da sessão ao vivo', prototypes: ['W15'], phase: 4, back: { to: '/sessoes/:sessionId', label: 'Detalhes da sessão' } },
]

export const PHASE_NAMES: Record<number, string> = {
  2: 'Pacientes e estímulos',
  3: 'Configuração de sessões',
  4: 'Execução ao vivo',
  5: 'Ingestão e análise',
  6: 'Início',
}
