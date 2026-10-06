import { matchPath, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi, hasPermission, useCurrentUser } from '../api/auth'
import { dashboardApi, dashboardKeys } from '../api/dashboard'
import { useToast } from '../components/Toast/toastContext'
import { ADMIN_TABS, allowedAdminTabs } from '../pages/admin/adminTabItems'
import PageTransition from './PageTransition'
import Sidebar from './Sidebar'
import styles from './AppLayout.module.css'

// Casca das telas internas: menu lateral à esquerda e a página à direita. Fica dentro da guarda
// de login (RequireAuth); "Administração" aparece para quem tem alguma permissão da área. O selo
// de Sessões conta as em andamento ou aguardando dados (as de "Precisam de atenção" do Início) e se
// atualiza sozinho, porque o óculos muda o status sem passar pelo navegador.
const BADGE_REFRESH_MS = 30_000

// As abas da Administração são uma tela só para a transição: o cabeçalho e as abas ficam, e o
// AdminLayout anima só o conteúdo da aba.
function screenKey(pathname: string) {
  return ADMIN_TABS.some((tab) => matchPath(tab.to, pathname)) ? '/admin' : pathname
}

export default function AppLayout() {
  const me = useCurrentUser()
  const badge = useQuery({
    queryKey: dashboardKeys.badge,
    queryFn: ({ signal }) => dashboardApi.badge(signal),
    refetchInterval: BADGE_REFRESH_MS,
  })
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
      <Sidebar
        user={{ name: me.name, roleLabel: me.role_label }}
        showAdmin={allowedAdminTabs(me).length > 0}
        showPatients={hasPermission(me, 'patients.view')}
        sessionsBadge={badge.data?.sessions}
        onLogout={logout}
      />
      <main id="conteudo" className={styles.main} tabIndex={-1}>
        <PageTransition screenKey={screenKey} />
      </main>
    </div>
  )
}
