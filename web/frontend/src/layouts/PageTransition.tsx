import { useLayoutEffect, useRef, useState } from 'react'
import { Outlet, useLocation, useNavigationType } from 'react-router-dom'
import styles from './PageTransition.module.css'

interface PageTransitionProps {
  // Caminhos com a mesma chave são uma tela só e trocam sem transição (as abas da Administração,
  // cujo conteúdo o AdminLayout anima por conta própria). Sem ela, cada caminho é uma tela.
  screenKey?: (pathname: string) => string
  // Dentro de outra transição: a primeira tela já entra com a de fora; só as trocas seguintes animam.
  nested?: boolean
}

// Troca de tela, no lugar do <Outlet />: a página nova entra com um fade e sobe 8 px, como os modais
// e os avisos, e começa do topo. Voltar e avançar no navegador também animam, mas deixam a rolagem
// com ele. Mudar só os parâmetros da URL (filtros, página da lista) não troca a tela.
export default function PageTransition({ screenKey, nested = false }: PageTransitionProps) {
  const { pathname } = useLocation()
  const navigationType = useNavigationType()
  const key = screenKey ? screenKey(pathname) : pathname

  const [firstKey] = useState(key)
  const [changed, setChanged] = useState(false)
  if (!changed && key !== firstKey) setChanged(true)

  const shownKey = useRef(key)
  useLayoutEffect(() => {
    if (shownKey.current === key) return
    shownKey.current = key
    if (navigationType !== 'POP') window.scrollTo({ top: 0 })
  }, [key, navigationType])

  return (
    <div key={key} className={!nested || changed ? styles.enter : undefined}>
      <Outlet />
    </div>
  )
}
