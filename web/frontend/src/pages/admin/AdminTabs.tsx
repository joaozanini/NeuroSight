import { useCurrentUser } from '../../api/auth'
import Tabs from '../../components/Tabs/Tabs'
import { allowedAdminTabs } from './adminTabItems'

// Abas da Administração; cada aba é uma rota e só aparece para quem tem a permissão dela.
export default function AdminTabs() {
  const me = useCurrentUser()
  return <Tabs ariaLabel="Administração" items={allowedAdminTabs(me).map(({ label, icon, to }) => ({ label, icon, to }))} />
}
