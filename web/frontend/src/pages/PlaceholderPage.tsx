import { generatePath, useParams } from 'react-router-dom'
import { Construction } from 'lucide-react'
import BackLink from '../components/PageHeader/BackLink'
import PageHeader from '../components/PageHeader/PageHeader'
import { cx } from '../lib/cx'
import { usePageTitle } from '../lib/usePageTitle'
import { PHASE_NAMES } from '../routes'
import type { ScreenRoute } from '../routes'
import AdminTabs from './admin/AdminTabs'
import styles from './PlaceholderPage.module.css'

interface PlaceholderPageProps {
  screen: ScreenRoute
  // app: dentro do menu lateral; auth: telas de acesso; fullscreen: controle ao vivo.
  variant?: 'app' | 'auth' | 'fullscreen'
}

// Tela ainda não implementada: mostra o título do protótipo e em que fase do plano ela entra.
export default function PlaceholderPage({ screen, variant = 'app' }: PlaceholderPageProps) {
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

  if (variant === 'auth') {
    return (
      <div className={styles.auth}>
        {back && <BackLink to={back.to} label={back.label} className={styles.authBack} />}
        <h1 className={styles.authTitle}>{screen.title}</h1>
        {screen.subtitle && <p className={styles.authSubtitle}>{screen.subtitle}</p>}
        {notice}
      </div>
    )
  }

  return (
    <div className={cx(variant === 'fullscreen' && styles.fullscreen)}>
      <PageHeader title={screen.title} subtitle={screen.subtitle} back={back} className={screen.adminTabs ? styles.withTabs : undefined} />
      {screen.adminTabs && <AdminTabs />}
      <div className={cx(styles.body, screen.adminTabs && styles.bodyAfterTabs)}>{notice}</div>
    </div>
  )
}
