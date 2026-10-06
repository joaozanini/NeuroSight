import { generatePath, useParams } from 'react-router-dom'
import { Construction } from 'lucide-react'
import PageHeader from '../components/PageHeader/PageHeader'
import { usePageTitle } from '../lib/usePageTitle'
import { PHASE_NAMES } from '../routes'
import type { ScreenRoute } from '../routes'
import styles from './PlaceholderPage.module.css'

interface PlaceholderPageProps {
  screen: ScreenRoute
}

// Tela ainda não implementada: mostra o título do protótipo e em que fase do plano ela entra.
export default function PlaceholderPage({ screen }: PlaceholderPageProps) {
  const params = useParams()
  usePageTitle(screen.title)
  const back = screen.back ? { to: generatePath(screen.back.to, params), label: screen.back.label } : undefined

  const notice = (
    <div className={styles.notice} role="note">
      <Construction size={22} className={styles.icon} aria-hidden />
      <div>
        <p className={styles.noticeTitle}>Tela em construção</p>
        <p className={styles.noticeText}>
          Segue o protótipo {screen.prototypes.join(' e ')} e entra na Fase {screen.phase}
          {PHASE_NAMES[screen.phase] ? ` (${PHASE_NAMES[screen.phase]})` : ''} do plano de implementação.
        </p>
      </div>
    </div>
  )

  return (
    <>
      <PageHeader title={screen.title} subtitle={screen.subtitle} back={back} />
      {notice}
    </>
  )
}
