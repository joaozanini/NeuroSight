// Tema claro/escuro: dirigido pelo atributo data-theme no <html>, persistido no localStorage,
// com fallback para a preferência do sistema.

export type Theme = 'light' | 'dark'

const KEY = 'questpro-theme'

export function getInitialTheme(): Theme {
  const saved = localStorage.getItem(KEY)
  if (saved === 'light' || saved === 'dark') return saved
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches
  return prefersLight ? 'light' : 'dark'
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  localStorage.setItem(KEY, theme)
}

export function currentTheme(): Theme {
  return (document.documentElement.dataset.theme as Theme) || getInitialTheme()
}
