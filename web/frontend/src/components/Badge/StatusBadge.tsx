import { PATIENT_STATUS, SESSION_STATUS, USER_STATUS } from '../../lib/status'
import type { PatientStatus, SessionStatus, StatusStyle, UserStatus } from '../../lib/status'
import Badge from './Badge'

type StatusBadgeProps =
  | { kind: 'session'; status: SessionStatus }
  | { kind: 'user'; status: UserStatus }
  | { kind: 'patient'; status: PatientStatus }

// Selo de status com o texto e a cor dos protótipos: <StatusBadge kind="session" status="running" />.
export default function StatusBadge(props: StatusBadgeProps) {
  let style: StatusStyle
  if (props.kind === 'session') style = SESSION_STATUS[props.status]
  else if (props.kind === 'user') style = USER_STATUS[props.status]
  else style = PATIENT_STATUS[props.status]
  return (
    <Badge tone={style.tone} dot={style.dot}>
      {style.label}
    </Badge>
  )
}
