// Mapa das telas dos protótipos (web/docs/pages) para as rotas do site. Enquanto uma tela não é
// implementada, a rota mostra um placeholder com o título, o link de voltar e a fase do plano.
// Ao implementar uma tela, troque o placeholder pela página no App.tsx e tire-a daqui.

export interface ScreenRoute {
  path: string
  title: string
  // Códigos dos protótipos que a rota cobre (modais entram junto da tela de baixo).
  prototypes: string[]
  phase: number
  subtitle?: string
  back?: { to: string; label: string }
  // Abas da Administração (W19, W21, W22).
  adminTabs?: boolean
}

// Telas de acesso, no AuthLayout (painel da marca à direita).
export const AUTH_SCREENS: ScreenRoute[] = [
  { path: '/login', title: 'Entrar', prototypes: ['W01'], phase: 1, subtitle: 'Acesse com o e-mail e a senha cadastrados pelo administrador.' },
  {
    path: '/esqueci-senha',
    title: 'Esqueceu a senha?',
    prototypes: ['W02'],
    phase: 1,
    subtitle: 'Informe o e-mail da sua conta. Se ele estiver cadastrado, você recebe um link para criar uma nova senha.',
    back: { to: '/login', label: 'Voltar para o login' },
  },
  { path: '/redefinir-senha', title: 'Defina uma nova senha', prototypes: ['W03'], phase: 1, subtitle: 'Escolha uma senha nova para voltar a acessar o sistema.' },
  { path: '/aceitar-convite', title: 'Defina uma nova senha', prototypes: ['W03'], phase: 1, subtitle: 'Crie a senha para começar a usar o sistema.' },
]

// Telas internas, no AppLayout (menu lateral).
export const APP_SCREENS: ScreenRoute[] = [
  { path: '/', title: 'Início', prototypes: ['W04'], phase: 6 },
  { path: '/perfil', title: 'Meu perfil', prototypes: ['W05'], phase: 1 },

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

  { path: '/admin/usuarios', title: 'Administração', prototypes: ['W19'], phase: 1, subtitle: 'Usuários, permissões e registro de auditoria.', adminTabs: true },
  { path: '/admin/usuarios/novo', title: 'Novo usuário', prototypes: ['W20'], phase: 1, back: { to: '/admin/usuarios', label: 'Usuários' } },
  {
    path: '/admin/usuarios/:userId',
    title: 'Editar usuário',
    prototypes: ['W20'],
    phase: 1,
    subtitle: 'As alterações ficam registradas na auditoria.',
    back: { to: '/admin/usuarios', label: 'Usuários' },
  },
  { path: '/admin/permissoes', title: 'Administração', prototypes: ['W21'], phase: 1, subtitle: 'Usuários, permissões e registro de auditoria.', adminTabs: true },
  { path: '/admin/auditoria', title: 'Administração', prototypes: ['W22', 'W23'], phase: 1, subtitle: 'Usuários, permissões e registro de auditoria.', adminTabs: true },
]

// Tela cheia, sem menu.
export const FULLSCREEN_SCREENS: ScreenRoute[] = [
  { path: '/sessoes/:sessionId/controle', title: 'Controle da sessão ao vivo', prototypes: ['W15'], phase: 4, back: { to: '/sessoes/:sessionId', label: 'Detalhes da sessão' } },
]

export const PHASE_NAMES: Record<number, string> = {
  1: 'Contas, permissões e auditoria',
  2: 'Pacientes e estímulos',
  3: 'Configuração de sessões',
  4: 'Execução ao vivo',
  5: 'Ingestão e análise',
  6: 'Início',
}
