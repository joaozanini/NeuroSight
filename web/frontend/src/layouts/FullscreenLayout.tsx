import { Outlet } from 'react-router-dom'
import styles from './FullscreenLayout.module.css'

// Tela cheia, sem o menu lateral: o controle da sessão ao vivo (W15).
export default function FullscreenLayout() {
  return (
    <main className={styles.main}>
      <Outlet />
    </main>
  )
}
