import { cx } from '../../lib/cx'
import { PASSWORD_RULES } from '../../lib/password'
import CheckCircleFilled from '../icons/CheckCircleFilled'
import styles from './PasswordField.module.css'

interface PasswordRulesProps {
  id?: string
  value: string
}

function RuleIcon({ met }: { met: boolean }) {
  if (met) return <CheckCircleFilled className={styles.ruleIcon} />
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" focusable="false" className={styles.ruleIcon}>
      <circle cx="10" cy="10" r="9.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

// "A senha precisa ter:" com cada regra marcada conforme a pessoa digita.
export default function PasswordRules({ id, value }: PasswordRulesProps) {
  return (
    <div id={id} className={styles.rules}>
      <p className={styles.rulesTitle}>A senha precisa ter:</p>
      <ul className={styles.ruleList}>
        {PASSWORD_RULES.map((rule) => {
          const met = rule.test(value)
          return (
            <li key={rule.id} className={cx(styles.rule, met && styles.met)}>
              <RuleIcon met={met} />
              <span>{rule.label}</span>
              <span className="sr-only">{met ? ' (atendida)' : ' (pendente)'}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
