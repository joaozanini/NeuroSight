import { Navigate, Outlet } from 'react-router-dom'
import { useCurrentUser } from '../../api/auth'
import PageHeader from '../../components/PageHeader/PageHeader'
import ForbiddenPage from '../ForbiddenPage'
import AdminTabs from './AdminTabs'
import { allowedAdminTabs } from './adminTabItems'
import styles from './AdminLayout.module.css'

// Cabeçalho e abas comuns a Usuários, Perfis e permissões e Auditoria (W19, W21, W22).
export default function AdminLayout() {
  return (
    <>
      <PageHeader title="Administração" subtitle="Usuários, permissões e registro de auditoria." className={styles.header} />
      <AdminTabs />
      <div className={styles.body}>
        <Outlet />
      </div>
    </>
  )
}

// /admin abre a primeira aba que a pessoa pode ver.
export function AdminIndex() {
  const tabs = allowedAdminTabs(useCurrentUser())
  return tabs.length ? <Navigate to={tabs[0].to} replace /> : <ForbiddenPage />
}
