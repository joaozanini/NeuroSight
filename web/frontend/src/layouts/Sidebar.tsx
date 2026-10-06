import { Link, NavLink } from 'react-router-dom'
import { CirclePlay, Image, LogOut, ShieldCheck, UserRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Avatar from '../components/Avatar/Avatar'
import HomeIcon from '../components/icons/HomeIcon'
import Logo from '../components/Logo/Logo'
import { cx } from '../lib/cx'
import styles from './Sidebar.module.css'

export interface SidebarUser {
  name: string
  roleLabel: string
}

interface SidebarProps {
  // Sem usuário (antes do login existir) o rodapé com o perfil e o "Sair" não aparece.
  user?: SidebarUser | null
  // "Administração" só para quem tem a permissão.
  showAdmin?: boolean
  // "Pacientes" some para quem não pode ver pacientes.
  showPatients?: boolean
  // Sessões em andamento ou aguardando dados; 0 ou vazio esconde o selo.
  sessionsBadge?: number
  onLogout?: () => void
}

interface NavItemProps {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  badge?: number
}

function NavItem({ to, label, icon: Icon, end, badge }: NavItemProps) {
  return (
    <li>
      <NavLink to={to} end={end} className={({ isActive }) => cx(styles.item, isActive && styles.active)}>
        <Icon size={20} aria-hidden />
        <span className={styles.itemLabel}>{label}</span>
        {badge ? (
          <span className={styles.badge}>
            {badge}
            <span className="sr-only"> em andamento ou aguardando dados</span>
          </span>
        ) : null}
      </NavLink>
    </li>
  )
}

// Menu lateral (protótipo "Componente · Menu lateral").
export default function Sidebar({ user, showAdmin = false, showPatients = true, sessionsBadge, onLogout }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <Link to="/" className={styles.brand}>
        <Logo size={36} />
        <span>NeuroSight</span>
      </Link>

      <nav aria-label="Menu principal">
        <ul className={styles.nav}>
          <NavItem to="/" end label="Início" icon={HomeIcon} />
          <NavItem to="/sessoes" label="Sessões" icon={CirclePlay} badge={sessionsBadge} />
          {showPatients && <NavItem to="/pacientes" label="Pacientes" icon={UserRound} />}
          <NavItem to="/estimulos" label="Estímulos" icon={Image} />
          {showAdmin && <NavItem to="/admin" label="Administração" icon={ShieldCheck} />}
        </ul>
      </nav>

      {user && (
        <div className={styles.footer}>
          <NavLink to="/perfil" className={({ isActive }) => cx(styles.user, isActive && styles.userActive)}>
            <Avatar name={user.name} />
            <span className={styles.userText}>
              <span className={styles.userName}>{user.name}</span>
              <span className={styles.userRole}>{user.roleLabel}</span>
            </span>
          </NavLink>
          <button type="button" className={styles.logout} onClick={onLogout}>
            <LogOut size={20} aria-hidden />
            Sair
          </button>
        </div>
      )}
    </aside>
  )
}
