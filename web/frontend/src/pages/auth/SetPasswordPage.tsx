import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ME_KEY, authApi } from '../../api/auth'
import type { LinkKind } from '../../api/auth'
import { ApiError } from '../../api/client'
import Button from '../../components/Button/Button'
import LinkButton from '../../components/Button/LinkButton'
import FormAlert from '../../components/FormAlert/FormAlert'
import PasswordField from '../../components/PasswordField/PasswordField'
import Spinner from '../../components/Spinner/Spinner'
import TextField from '../../components/TextField/TextField'
import { useToast } from '../../components/Toast/toastContext'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import { PASSWORDS_DIFFER, confirmPasswordField, newPasswordField } from '../../lib/validation'
import styles from './AuthPage.module.css'

const schema = z
  .object({ password: newPasswordField, confirm: confirmPasswordField })
  .refine((v) => v.password === v.confirm, { message: PASSWORDS_DIFFER, path: ['confirm'] })

type PasswordValues = z.infer<typeof schema>

// W03: senha nova pelo link do e-mail. A mesma tela aceita o convite (primeira senha) e a
// redefinição; nos dois casos a pessoa já entra no sistema ao salvar.
export default function SetPasswordPage({ kind }: { kind: LinkKind }) {
  usePageTitle('Defina uma nova senha')
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)

  const link = useQuery({
    queryKey: ['auth-link', kind, token],
    queryFn: () => authApi.linkInfo(token, kind),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  })

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(schema), defaultValues: { password: '', confirm: '' } })

  async function onSubmit({ password }: PasswordValues) {
    setFormError(null)
    try {
      const me = await authApi.setPassword(kind, token, password)
      queryClient.setQueryData(ME_KEY, me)
      toast.success(kind === 'invite' ? 'Senha criada. Boas-vindas ao NeuroSight!' : 'Senha nova salva.')
      navigate('/', { replace: true })
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        link.refetch()
        return
      }
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar a senha.')
    }
  }

  if (token && link.isPending) {
    return (
      <div className={styles.loading}>
        <Spinner size={28} label="Conferindo o link" />
      </div>
    )
  }

  if (!token || link.isError) {
    const expired = !token || (link.error instanceof ApiError && link.error.status === 404)
    return (
      <div className={styles.page}>
        <h1 className={styles.title}>{expired ? 'Link inválido ou expirado' : 'Não foi possível abrir o link'}</h1>
        <p className={styles.subtitle}>
          {!expired
            ? sentence(link.error!.message)
            : kind === 'invite'
              ? 'O convite já foi usado, foi substituído por um mais novo ou passou do prazo. Peça ao administrador do sistema para enviar outro.'
              : 'O link já foi usado, foi substituído por um mais novo ou passou do prazo. Peça um novo para criar a senha.'}
        </p>
        {kind === 'reset' && expired ? (
          <LinkButton to="/esqueci-senha" size="lg" block>
            Pedir um novo link
          </LinkButton>
        ) : (
          <LinkButton to="/login" size="lg" block variant={expired ? 'primary' : 'secondary'}>
            Ir para o login
          </LinkButton>
        )}
      </div>
    )
  }

  const info = link.data
  if (!info) return null
  const firstName = info.name.split(' ')[0]
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Defina uma nova senha</h1>
      <p className={styles.subtitle}>
        {kind === 'invite'
          ? `Olá, ${firstName}. Crie uma senha para começar a usar o sistema.`
          : 'Escolha uma senha nova para voltar a acessar o sistema.'}
      </p>
      <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
        {/* Para o gerenciador de senhas salvar a senha com a conta certa. */}
        <input type="email" name="username" autoComplete="username" value={info.email} readOnly hidden />
        <PasswordField label="Senha" autoComplete="new-password" showRules error={errors.password?.message} {...register('password')} />
        <TextField label="Confirmar senha" type="password" autoComplete="new-password" error={errors.confirm?.message} {...register('confirm')} />
        {formError && <FormAlert>{formError}</FormAlert>}
        <Button type="submit" size="lg" block loading={isSubmitting} className={styles.submit}>
          Salvar nova senha
        </Button>
      </form>
    </div>
  )
}
