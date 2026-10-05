import { useQuery } from '@tanstack/react-query'
import { auditApi, auditKeys } from '../../api/audit'
import type { AuditFilterOptions } from '../../api/audit'
import { hasPermission, useCurrentUser } from '../../api/auth'
import Button from '../../components/Button/Button'
import FormAlert from '../../components/FormAlert/FormAlert'
import Modal from '../../components/Modal/Modal'
import Spinner from '../../components/Spinner/Spinner'
import TextLink from '../../components/TextLink/TextLink'
import { cx } from '../../lib/cx'
import { formatDateTime, sentence } from '../../lib/format'
import { describeUserAgent } from '../../lib/userAgent'
import { ENTITY_LINKS, labelOf } from './auditLabels'
import styles from './AuditDetailModal.module.css'

interface AuditDetailModalProps {
  entryId: number | null
  options?: AuditFilterOptions
  onClose: () => void
}

// W23: quem, de onde, o item afetado (com link) e a tabela "O que mudou".
export default function AuditDetailModal({ entryId, options, onClose }: AuditDetailModalProps) {
  const me = useCurrentUser()
  const entry = useQuery({
    queryKey: auditKeys.detail(entryId ?? 0),
    queryFn: ({ signal }) => auditApi.get(entryId!, signal),
    enabled: entryId !== null,
    staleTime: Infinity,
  })
  const data = entry.data

  let body
  if (entry.isPending) body = <Spinner size={24} label="Carregando o registro" />
  else if (entry.isError) body = <FormAlert>{sentence(entry.error.message)}</FormAlert>
  else {
    const link = ENTITY_LINKS[data!.entity_type]
    const canOpen = link && (data!.entity_id || data!.entity_type === 'permissions') && (!link.permission || hasPermission(me, link.permission))
    const role = labelOf(options?.roles, data!.user_role)
    body = (
      <>
        <div className={styles.who}>
          <div>
            <p className={styles.label}>Quem</p>
            <p className={styles.value}>{data!.user_name ? `${data!.user_name}${role ? `, perfil ${role}` : ''}` : 'Sistema'}</p>
          </div>
          <div>
            <p className={styles.label}>De onde</p>
            <p className={styles.value}>
              {data!.ip ? `IP ${data!.ip}, ${describeUserAgent(data!.user_agent)}` : 'Linha de comando do servidor'}
            </p>
          </div>
        </div>
        <p className={styles.label}>Item afetado</p>
        <div className={styles.item}>
          <p className={styles.value}>
            {labelOf(options?.entity_types, data!.entity_type)} {data!.entity_label}
          </p>
          {canOpen && (
            <TextLink to={link.to(data!.entity_id ?? '')} onClick={onClose}>
              {link.label}
            </TextLink>
          )}
        </div>
        <h3 className={styles.heading}>O que mudou</h3>
        {data!.changes.length ? (
          <div className={styles.changes}>
            <table>
              <thead>
                <tr>
                  <th scope="col">Campo</th>
                  <th scope="col">Antes</th>
                  <th scope="col">Depois</th>
                </tr>
              </thead>
              <tbody>
                {data!.changes.map((c) => (
                  <tr key={c.field}>
                    <th scope="row">{c.label}</th>
                    <td className={cx(c.before ? styles.before : styles.empty)}>{c.before ?? '—'}</td>
                    <td className={cx(c.after ? styles.after : styles.empty)}>{c.after ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.noChanges}>Nenhum dado foi alterado nesta ação.</p>
        )}
      </>
    )
  }

  return (
    <Modal
      open={entryId !== null}
      onClose={onClose}
      size="md"
      title={data ? labelOf(options?.actions, data.action) : 'Detalhes do registro'}
      subtitle={data ? formatDateTime(data.created_at, true) : undefined}
      footerNote="Registros de auditoria não podem ser editados nem apagados."
      footer={
        <Button size="sm" onClick={onClose}>
          Fechar
        </Button>
      }
    >
      {body}
    </Modal>
  )
}
