// Preparação dos testes (vitest + Testing Library em jsdom).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})

// O jsdom não rola a página; o assistente da W13 volta ao topo a cada etapa.
window.scrollTo = () => {}
