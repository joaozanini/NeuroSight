import { Fragment, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { ME_KEY } from '../../api/auth'
import type { Permission, Role } from '../../api/auth'
import { ApiError } from '../../api/client'
import { PERMISSIONS_KEY, permissionsApi } from '../../api/permissions'
import type { Grants, PermissionMatrix } from '../../api/permissions'
import Button from '../../components/Button/Button'
import FormAlert from '../../components/FormAlert/FormAlert'
import Spinner from '../../components/Spinner/Spinner'
import { useToast } from '../../components/Toast/toastContext'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import styles from './PermissionsPage.module.css'

type Draft = Record<Role, Set<Permission>>

function toDraft(grants: Grants): Draft {
  return { admin: new Set(grants.admin), researcher: new Set(grants.researcher) }
}

function sameDraft(a: Draft, b: Draft): boolean {
  return (Object.keys(a) as Role[]).every((role) => a[role].size === b[role].size && [...a[role]].every((p) => b[role].has(p)))
}

// W21: matriz perfil × permissão. As mudanças valem a partir do próximo acesso de cada usuário;
// "Gerenciar usuários" e "Alterar permissões" ficam travadas para o Admin.
export default function PermissionsPage() {
  usePageTitle('Perfis e permissões')
  const toast = useToast()
  const queryClient = useQueryClient()
  const matrix = useQuery({ queryKey: PERMISSIONS_KEY, queryFn: ({ signal }) => permissionsApi.get(signal) })
  const [draft, setDraft] = useState<Draft | null>(null)

  const saved = useMemo(() => (matrix.data ? toDraft(matrix.data.grants) : null), [matrix.data])
  useEffect(() => {
    if (saved) setDraft(saved)
  }, [saved])

  const dirty = Boolean(draft && saved && !sameDraft(draft, saved))

  // Aviso do navegador ao sair da página com mudanças não salvas.
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const save = useMutation({
    mutationFn: (value: Draft) => permissionsApi.save({ admin: [...value.admin], researcher: [...value.researcher] }),
    onSuccess: (data) => {
      queryClient.setQueryData(PERMISSIONS_KEY, data)
      queryClient.invalidateQueries({ queryKey: ME_KEY })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast.success('Permissões salvas.')
    },
    onError: (error) => toast.error(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar as permissões.'),
  })

  if (matrix.isPending || !draft) {
    if (matrix.isError) return <FormAlert>{sentence(matrix.error.message)}</FormAlert>
    return <Spinner size={28} label="Carregando as permissões" />
  }

  const data: PermissionMatrix = matrix.data!
  const isLocked = (role: Role, permission: Permission) => Boolean(data.locked[role]?.includes(permission))

  function toggle(role: Role, permission: Permission, checked: boolean) {
    setDraft((current) => {
      if (!current) return current
      const next = { ...current, [role]: new Set(current[role]) }
      if (checked) next[role].add(permission)
      else next[role].delete(permission)
      return next
    })
  }

  return (
    <>
      <p className={styles.intro}>
        Marque o que cada perfil pode fazer. A mudança vale para todos os usuários do perfil a partir do próximo acesso.
      </p>
      <div className={styles.card}>
        <table className={styles.table}>
          <caption className="sr-only">Permissões de cada perfil</caption>
          <thead>
            <tr>
              <th scope="col">Permissão</th>
              {data.roles.map((role) => (
                <th key={role.id} scope="col" className={styles.roleColumn}>
                  {role.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.groups.map((group) => (
              <Fragment key={group.label}>
                <tr className={styles.groupRow}>
                  <th scope="rowgroup" colSpan={1 + data.roles.length}>
                    {group.label}
                  </th>
                </tr>
                {group.permissions.map((permission) => (
                  <tr key={permission.id}>
                    <th scope="row" className={styles.permission}>
                      {permission.label}
                      {permission.description && <span className={styles.description}>{permission.description}</span>}
                    </th>
                    {data.roles.map((role) => {
                      const locked = isLocked(role.id, permission.id)
                      return (
                        <td key={role.id} className={styles.check}>
                          <input
                            type="checkbox"
                            aria-label={`${role.label}: ${permission.label}${locked ? ' (sempre marcada)' : ''}`}
                            checked={locked || draft[role.id].has(permission.id)}
                            disabled={locked || save.isPending}
                            onChange={(e) => toggle(role.id, permission.id, e.target.checked)}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.lockNote}>
        <Lock size={18} aria-hidden />
        Gerenciar usuários e alterar permissões ficam sempre marcadas para o Admin, para ninguém perder o acesso à administração.
      </p>
      <div className={styles.footer}>
        <p className={styles.state} aria-live="polite">
          {dirty ? 'Há alterações não salvas.' : 'Todas as alterações estão salvas.'}
        </p>
        <div className={styles.buttons}>
          <Button variant="secondary" disabled={!dirty || save.isPending} onClick={() => saved && setDraft(saved)}>
            Descartar
          </Button>
          <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(draft)}>
            Salvar permissões
          </Button>
        </div>
      </div>
    </>
  )
}
