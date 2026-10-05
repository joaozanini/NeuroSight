import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { isUnauthorized, useMe } from '../api/auth'
import Button from '../components/Button/Button'
import Spinner from '../components/Spinner/Spinner'
import styles from './RequireAuth.module.css'

// Guarda da área logada: sem sessão, leva ao login guardando a página em ?next=. O servidor
// recarrega o usuário a cada request, então um usuário desativado cai no próximo acesso.
export default function RequireAuth() {
  const me = useMe()
  const location = useLocation()

  if (me.isPending) {
    return (
      <div className={styles.screen}>
        <Spinner size={28} label="Carregando" />
      </div>
    )
  }
  if (me.isError) {
    if (isUnauthorized(me.error)) {
      const next = location.pathname + location.search
      return <Navigate to={next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`} replace />
    }
    return (
      <div className={styles.screen} role="alert">
        <p className={styles.message}>{me.error.message}</p>
        <Button variant="secondary" onClick={() => me.refetch()}>
          Tentar de novo
        </Button>
      </div>
    )
  }
  return <Outlet />
}
