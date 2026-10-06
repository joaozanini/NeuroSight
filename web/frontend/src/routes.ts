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
]

export const PHASE_NAMES: Record<number, string> = {
  6: 'Início',
}
