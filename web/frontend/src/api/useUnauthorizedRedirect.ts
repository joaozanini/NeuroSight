import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { isAuthPath, setUnauthorizedHandler } from './client'

// Num 401, limpa o cache e leva ao login guardando a página atual em ?next=, sem recarregar.
export function useUnauthorizedRedirect() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  useEffect(() => {
    setUnauthorizedHandler(() => {
      const { pathname, search } = window.location
      if (isAuthPath(pathname)) return
      queryClient.clear()
      navigate(`/login?next=${encodeURIComponent(pathname + search)}`, { replace: true })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate, queryClient])
}
