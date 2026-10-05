import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { useCurrentUser } from '../../api/auth'
import { ApiError } from '../../api/client'
import { ROLE_DESCRIPTIONS, ROLE_LABELS, usersApi, usersKeys } from '../../api/users'
import type { LinkResult, UserDetail, UserUpdate } from '../../api/users'
import Button from '../../components/Button/Button'
import Card from '../../components/Card/Card'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import RadioCard from '../../components/RadioCard/RadioCard'
import RadioCardGroup from '../../components/RadioCard/RadioCardGroup'
import Spinner from '../../components/Spinner/Spinner'
import TextField from '../../components/TextField/TextField'
import { useToast } from '../../components/Toast/toastContext'
import { formatDate, formatRelative, sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import { emailField } from '../../lib/validation'
import LinkModal from './LinkModal'
import styles from './UserFormPage.module.css'

const schema = z.object({
  name: z.string().trim().min(1, 'Informe o nome completo.').max(120, 'Use no máximo 120 caracteres.'),
  email: emailField,
  role: z.enum(['researcher', 'admin']),
  status: z.enum(['active', 'invited', 'inactive']),
})

type UserValues = z.infer<typeof schema>

const BACK = { to: '/admin/usuarios', label: 'Usuários' }

// W20: novo usuário (com convite) e edição (com status e o cartão de acesso).
export default function UserFormPage() {
  const { userId } = useParams()
  const user = useQuery({
    queryKey: usersKeys.detail(userId ?? ''),
    queryFn: ({ signal }) => usersApi.get(userId!, signal),
    enabled: Boolean(userId),
  })
  usePageTitle(userId ? 'Editar usuário' : 'Novo usuário')

  if (!userId) return <UserForm />
  if (user.isPending) {
    return (
      <>
        <PageHeader title="Editar usuário" back={BACK} />
        <Spinner size={28} label="Carregando o usuário" />
      </>
    )
  }
  if (user.isError) {
    return (
      <>
        <PageHeader title="Editar usuário" back={BACK} />
        <FormAlert>{sentence(user.error.message)}</FormAlert>
      </>
    )
  }
  return <UserForm user={user.data} />
}

function UserForm({ user }: { user?: UserDetail }) {
  const editing = Boolean(user)
  const me = useCurrentUser()
  const isSelf = user?.id === me.id
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)
  const [pendingLink, setPendingLink] = useState<{ kind: 'invite' | 'reset'; result: LinkResult; userName: string; leave: boolean } | null>(null)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<UserValues>({
    resolver: zodResolver(schema),
    defaultValues: user
      ? { name: user.name, email: user.email, role: user.role, status: user.status }
      : { name: '', email: '', role: 'researcher', status: 'invited' },
  })

  function refresh() {
    queryClient.invalidateQueries({ queryKey: usersKeys.all })
    queryClient.invalidateQueries({ queryKey: ['audit'] })
  }

  function backToList() {
    navigate('/admin/usuarios')
  }

  function handleError(error: unknown) {
    if (error instanceof ApiError && error.status === 409 && error.message.includes('e-mail')) {
      setError('email', { message: sentence(error.message) })
      return
    }
    setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar.')
  }

  async function onSubmit(values: UserValues) {
    setFormError(null)
    try {
      if (!user) {
        const { user: created, invite } = await usersApi.create({ name: values.name, email: values.email, role: values.role })
        refresh()
        if (invite.email_sent) {
          toast.success(`Convite enviado para ${values.email}.`)
          backToList()
        } else {
          setPendingLink({ kind: 'invite', result: invite, userName: created.name, leave: true })
        }
        return
      }
      const changes: UserUpdate = { name: values.name, email: values.email }
      if (!isSelf) {
        changes.role = values.role
        if (values.status !== 'invited') changes.status = values.status
      }
      await usersApi.update(user.id, changes)
      refresh()
      toast.success('Alterações salvas.')
      backToList()
    } catch (error) {
      handleError(error)
    }
  }

  const sendLink = useMutation({
    mutationFn: (kind: 'invite' | 'reset') => (kind === 'invite' ? usersApi.resendInvite(user!.id) : usersApi.sendReset(user!.id)),
    onSuccess: (result, kind) => {
      refresh()
      if (!result.email_sent) setPendingLink({ kind, result, userName: user!.name, leave: false })
      else if (kind === 'invite') toast.success(`Convite reenviado para ${user!.email}.`)
      else toast.success(`Link de redefinição enviado para ${user!.email}.`)
    },
    onError: (error) => toast.error(error instanceof ApiError ? sentence(error.message) : 'Não foi possível enviar o link.'),
  })

  const statusOptions = user?.status === 'invited' ? (['invited', 'inactive'] as const) : (['active', 'inactive'] as const)
  const statusLabels = { active: 'Ativo', invited: 'Convite pendente', inactive: 'Inativo' }

  return (
    <>
      <PageHeader
        title={editing ? 'Editar usuário' : 'Novo usuário'}
        subtitle={editing ? 'As alterações ficam registradas na auditoria.' : undefined}
        back={BACK}
      />
      <div className={styles.layout}>
        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className={editing ? styles.twoColumns : styles.fields}>
            <TextField label="Nome completo" autoComplete="off" error={errors.name?.message} {...register('name')} />
            <TextField
              label="E-mail"
              type="email"
              autoComplete="off"
              placeholder="nome@exemplo.com"
              hint={editing ? undefined : 'É para este e-mail que vai o convite de acesso.'}
              error={errors.email?.message}
              {...register('email')}
            />
          </div>

          <RadioCardGroup
            legend="Perfil"
            layout="stack"
            hint={isSelf ? 'Você não pode mudar o próprio perfil.' : undefined}
            error={errors.role?.message}
          >
            {(['researcher', 'admin'] as const).map((role) => (
              <RadioCard
                key={role}
                value={role}
                label={ROLE_LABELS[role]}
                description={ROLE_DESCRIPTIONS[role]}
                disabled={isSelf}
                {...register('role')}
              />
            ))}
          </RadioCardGroup>

          {editing && (
            <RadioCardGroup
              legend="Status"
              hint={
                isSelf
                  ? 'Você não pode desativar a própria conta.'
                  : 'Usuários inativos não conseguem entrar no sistema. As sessões e o histórico na auditoria continuam guardados.'
              }
            >
              {statusOptions.map((status) => (
                <RadioCard key={status} value={status} label={statusLabels[status]} disabled={isSelf} {...register('status')} />
              ))}
            </RadioCardGroup>
          )}

          {formError && <FormAlert>{formError}</FormAlert>}
          <div className={styles.buttons}>
            <Button variant="secondary" onClick={backToList}>
              Cancelar
            </Button>
            <Button type="submit" loading={isSubmitting}>
              {editing ? 'Salvar alterações' : 'Salvar e enviar convite'}
            </Button>
          </div>
        </form>

        {user ? (
          <AccessCard user={user} sending={sendLink.isPending} onSend={(kind) => sendLink.mutate(kind)} />
        ) : (
          <HowAccessWorks />
        )}
      </div>

      <LinkModal
        kind={pendingLink?.kind ?? 'invite'}
        userName={pendingLink?.userName ?? ''}
        result={pendingLink?.result ?? null}
        onClose={() => {
          const leave = pendingLink?.leave
          setPendingLink(null)
          if (leave) backToList()
        }}
      />
    </>
  )
}

function HowAccessWorks() {
  return (
    <Card as="aside" title="Como o acesso é liberado" aria-label="Como o acesso é liberado" className={styles.side}>
      <ol className={styles.steps}>
        <li>Ao salvar, o sistema envia um convite para o e-mail informado.</li>
        <li>A pessoa abre o link e cria a própria senha.</li>
        <li>No primeiro acesso, o status muda de Convite pendente para Ativo.</li>
      </ol>
      <p className={styles.sideNote}>A criação do usuário fica registrada na auditoria.</p>
    </Card>
  )
}

function AccessCard({ user, sending, onSend }: { user: UserDetail; sending: boolean; onSend: (kind: 'invite' | 'reset') => void }) {
  return (
    <Card as="aside" title="Acesso" aria-label="Acesso" className={styles.side}>
      <dl className={styles.facts}>
        <div>
          <dt>Último acesso</dt>
          <dd>{user.last_login_at ? formatRelative(user.last_login_at) : 'Nunca acessou'}</dd>
        </div>
        <div>
          <dt>Criado em</dt>
          <dd>{formatDate(user.created_at)}</dd>
        </div>
        <div>
          <dt>Criado por</dt>
          <dd>{user.created_by_name ?? 'Sistema'}</dd>
        </div>
        <div>
          <dt>Sessões como responsável</dt>
          <dd>{user.sessions_as_owner}</dd>
        </div>
      </dl>
      <div className={styles.sideSection}>
        {user.status === 'invited' ? (
          <>
            <h3 className={styles.sideTitle}>Convite</h3>
            <p className={styles.sideText}>
              A pessoa ainda não criou a senha. Se o convite expirou ou se perdeu, envie outro; o anterior deixa de valer.
            </p>
            <Button variant="secondary" size="sm" loading={sending} onClick={() => onSend('invite')}>
              Reenviar convite
            </Button>
          </>
        ) : (
          <>
            <h3 className={styles.sideTitle}>Senha</h3>
            {user.status === 'active' ? (
              <>
                <p className={styles.sideText}>
                  O usuário recebe por e-mail um link para criar uma nova senha. A senha atual continua valendo até ele usar o link.
                </p>
                <Button variant="secondary" size="sm" loading={sending} onClick={() => onSend('reset')}>
                  Enviar redefinição de senha
                </Button>
              </>
            ) : (
              <p className={styles.sideText}>Ative o usuário para enviar a redefinição de senha.</p>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
