import { ShieldCheck, UsersRound } from 'lucide-react'
import AuditIcon from '../../components/icons/AuditIcon'
import Tabs from '../../components/Tabs/Tabs'

// Abas da Administração (W19, W21, W22); cada aba é uma rota.
export default function AdminTabs() {
  return (
    <Tabs
      ariaLabel="Administração"
      items={[
        { label: 'Usuários', icon: UsersRound, to: '/admin/usuarios' },
        { label: 'Perfis e permissões', icon: ShieldCheck, to: '/admin/permissoes' },
        { label: 'Auditoria', icon: AuditIcon, to: '/admin/auditoria' },
      ]}
    />
  )
}
