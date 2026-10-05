import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import styles from './AppLayout.module.css'

// Casca das telas internas: menu lateral à esquerda e a página à direita.
// O usuário do rodapé, a permissão de Administração e o número de sessões ativas vêm do login
// e do dashboard; até lá o menu mostra todos os itens e esconde o rodapé.
export default function AppLayout() {
  return (
    <div className={styles.shell}>
      <a href="#conteudo" className={styles.skip}>
        Pular para o conteúdo
      </a>
      <Sidebar showAdmin />
      <main id="conteudo" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
