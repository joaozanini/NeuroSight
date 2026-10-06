import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

export type FilterChanges = Record<string, string | number | null | undefined>

// Filtros das listas na query string (?q=&pagina=...), para a lista voltar igual depois de abrir um
// item. O setSearchParams do React Router monta a próxima URL a partir da do último render: duas
// mudanças seguidas antes de a tela renderizar de novo (trocar o tipo e logo a etiqueta) se
// sobrescreviam. Aqui cada mudança parte da anterior. Valor vazio e a página 1 saem da URL.
export function useUrlFilters() {
  const [params, setParams] = useSearchParams()
  const pending = useRef<URLSearchParams | null>(null)

  useEffect(() => {
    pending.current = null
  }, [params])

  function update(changes: FilterChanges) {
    const next = new URLSearchParams(pending.current ?? params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '' || (key === 'pagina' && Number(value) <= 1)) next.delete(key)
      else next.set(key, String(value))
    }
    pending.current = next
    setParams(next, { replace: true })
  }

  return [params, update] as const
}
