import { Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { authApi, useCurrentUser } from '../api/auth'
import { useToast } from '../components/Toast/toastContext'
import { allowedAdminTabs } from '../pages/admin/adminTabs'
import Sidebar from './Sidebar'
import styles from './AppLayout.module.css'

// Casca das telas internas: menu lateral à esquerda e a página à direita. Fica dentro da guarda
// de login (RequireAuth); "Administração" aparece para quem tem alguma permissão da área.
// O número de sessões ativas no menu chega com o dashboard (Fase 6).
export default function AppLayout() {
  const me = useCurrentUser()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      toast.error('Não foi possível sair agora. Tente de novo.')
      return
    }
    queryClient.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className={styles.shell}>
      <a href="#conteudo" className={styles.skip}>
        Pular para o conteúdo
      </a>
      <Sidebar user={{ name: me.name, roleLabel: me.role_label }} showAdmin={allowedAdminTabs(me).length > 0} onLogout={logout} />
      <main id="conteudo" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
