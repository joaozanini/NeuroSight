import { useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ME_KEY, authApi, safeNext, useMe } from '../../api/auth'
import { ApiError } from '../../api/client'
import Button from '../../components/Button/Button'
import FormAlert from '../../components/FormAlert/FormAlert'
import PasswordField from '../../components/PasswordField/PasswordField'
import TextField from '../../components/TextField/TextField'
import TextLink from '../../components/TextLink/TextLink'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import { emailField } from '../../lib/validation'
import styles from './AuthPage.module.css'

const schema = z.object({
  email: emailField,
  password: z.string().min(1, 'Informe a senha.'),
})

type LoginValues = z.infer<typeof schema>

// W01: entrar com e-mail e senha. Volta para a página pedida antes do login (?next=).
export default function LoginPage() {
  usePageTitle('Entrar')
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useMe()
  const [formError, setFormError] = useState<string | null>(null)
  const initialEmail = (location.state as { email?: string } | null)?.email ?? ''

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(schema), defaultValues: { email: initialEmail, password: '' } })

  // Quem já está logado não precisa da tela de login.
  if (me.data) return <Navigate to={next} replace />

  async function onSubmit(values: LoginValues) {
    setFormError(null)
    try {
      const user = await authApi.login(values.email, values.password)
      queryClient.setQueryData(ME_KEY, user)
      navigate(next, { replace: true })
    } catch (error) {
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível entrar.')
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Entrar</h1>
      <p className={styles.subtitle}>Acesse com o e-mail e a senha cadastrados pelo administrador.</p>
      <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
        <TextField
          label="E-mail"
          type="email"
          autoComplete="username"
          placeholder="nome@exemplo.com"
          error={errors.email?.message}
          {...register('email')}
        />
        <PasswordField label="Senha" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
        <TextLink to="/esqueci-senha" state={{ email: watch('email') }} className={styles.forgot}>
          Esqueci minha senha
        </TextLink>
        {formError && <FormAlert>{formError}</FormAlert>}
        <Button type="submit" size="lg" block loading={isSubmitting} className={styles.submitAfterLink}>
          Entrar
        </Button>
      </form>
      <p className={styles.footer}>Ainda não tem acesso? Peça ao administrador do sistema.</p>
    </div>
  )
}
