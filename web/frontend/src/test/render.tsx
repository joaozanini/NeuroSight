// Renderiza com os mesmos provedores do app (router em memória, React Query e avisos).
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import ToastProvider from '../components/Toast/ToastProvider'

// As mesmas opções do BrowserRouter do main.tsx (comportamento do React Router 7).
export const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true }

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]} future={ROUTER_FUTURE}>
        <ToastProvider>{ui}</ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
