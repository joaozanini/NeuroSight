import type { ReactNode } from 'react'
import { hasPermission, useCurrentUser } from '../api/auth'
import type { Permission } from '../api/auth'
import ForbiddenPage from '../pages/ForbiddenPage'

// Mostra a página só para quem tem a permissão; os outros veem o aviso de acesso negado. O
// servidor também confere (403), isto só evita mostrar uma tela que não funcionaria.
export default function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const me = useCurrentUser()
  return hasPermission(me, permission) ? <>{children}</> : <ForbiddenPage />
}
