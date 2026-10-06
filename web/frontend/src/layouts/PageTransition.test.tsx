import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { ROUTER_FUTURE } from '../test/render'
import PageTransition from './PageTransition'
import styles from './PageTransition.module.css'

// Menu fora da transição, como o menu lateral, e o "voltar" do navegador.
function Menu() {
  const navigate = useNavigate()
  return (
    <nav>
      <Link to="/a">A</Link>
      <Link to="/b">B</Link>
      <Link to="/a?pagina=2">A, página 2</Link>
      <Link to="/abas/1">Aba 1</Link>
      <Link to="/abas/2">Aba 2</Link>
      <button type="button" onClick={() => navigate(-1)}>
        Voltar
      </button>
    </nav>
  )
}

// Como a Administração: as abas são uma tela só por fora, e o conteúdo delas anima por dentro.
function TabsLayout() {
  return (
    <section aria-label="Abas">
      <PageTransition nested />
    </section>
  )
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
      <Menu />
      <Routes>
        <Route element={<PageTransition screenKey={(pathname) => (pathname.startsWith('/abas/') ? '/abas' : pathname)} />}>
          <Route path="/a" element={<h1>Tela A</h1>} />
          <Route path="/b" element={<h1>Tela B</h1>} />
          <Route element={<TabsLayout />}>
            <Route path="/abas/1" element={<h1>Conteúdo 1</h1>} />
            <Route path="/abas/2" element={<h1>Conteúdo 2</h1>} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  return userEvent.setup()
}

// O contêiner que a transição recria a cada tela.
async function screenOf(title: string) {
  return (await screen.findByRole('heading', { name: title })).parentElement!
}

describe('PageTransition', () => {
  it('cada tela nova entra animada e começa do topo', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo')
    const user = renderAt('/a')
    const first = await screenOf('Tela A')
    expect(first).toHaveClass(styles.enter)
    expect(scrollTo).not.toHaveBeenCalled()

    await user.click(screen.getByRole('link', { name: 'B' }))
    expect(await screenOf('Tela B')).toHaveClass(styles.enter)
    expect(first).not.toBeInTheDocument()
    expect(scrollTo).toHaveBeenCalledWith({ top: 0 })
  })

  it('mudar só os parâmetros da URL não troca a tela', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo')
    const user = renderAt('/a')
    const first = await screenOf('Tela A')
    await user.click(screen.getByRole('link', { name: 'A, página 2' }))
    expect(await screenOf('Tela A')).toBe(first)
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('voltar no navegador anima, mas deixa a rolagem com ele', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo')
    const user = renderAt('/a')
    await user.click(screen.getByRole('link', { name: 'B' }))
    await screenOf('Tela B')
    scrollTo.mockClear()
    await user.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(await screenOf('Tela A')).toHaveClass(styles.enter)
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('aninhada, a primeira tela entra com a de fora e só as trocas de aba animam', async () => {
    const user = renderAt('/abas/1')
    expect(await screenOf('Conteúdo 1')).not.toHaveClass(styles.enter)
    const outer = screen.getByRole('region', { name: 'Abas' }).parentElement!
    expect(outer).toHaveClass(styles.enter)

    await user.click(screen.getByRole('link', { name: 'Aba 2' }))
    expect(await screenOf('Conteúdo 2')).toHaveClass(styles.enter)
    expect(screen.getByRole('region', { name: 'Abas' }).parentElement).toBe(outer)

    await user.click(screen.getByRole('link', { name: 'Aba 1' }))
    expect(await screenOf('Conteúdo 1')).toHaveClass(styles.enter)
  })
})
