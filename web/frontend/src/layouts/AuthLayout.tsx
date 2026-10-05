import { Link, Outlet } from 'react-router-dom'
import Logo from '../components/Logo/Logo'
import BrandPanel from './BrandPanel'
import styles from './AuthLayout.module.css'

// Telas de acesso (W01–W03): marca no canto, formulário centralizado à esquerda e o painel da
// marca à direita.
export default function AuthLayout() {
  return (
    <div className={styles.shell}>
      <div className={styles.formSide}>
        <Link to="/login" className={styles.brand}>
          <Logo size={36} />
          <span>NeuroSight</span>
        </Link>
        <main className={styles.content}>
          <div className={styles.inner}>
            <Outlet />
          </div>
        </main>
      </div>
      <BrandPanel className={styles.panel} />
    </div>
  )
}
