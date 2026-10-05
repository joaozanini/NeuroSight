import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Mail } from 'lucide-react'
import { z } from 'zod'
import { authApi } from '../../api/auth'
import { ApiError } from '../../api/client'
import Button from '../../components/Button/Button'
import LinkButton from '../../components/Button/LinkButton'
import FormAlert from '../../components/FormAlert/FormAlert'
import BackLink from '../../components/PageHeader/BackLink'
import TextField from '../../components/TextField/TextField'
import TextLink from '../../components/TextLink/TextLink'
import { useToast } from '../../components/Toast/toastContext'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import { emailField } from '../../lib/validation'
import styles from './AuthPage.module.css'

const schema = z.object({ email: emailField })

type ForgotValues = z.infer<typeof schema>

// W02: pede o link para criar uma senha nova. A resposta é a mesma exista ou não o e-mail.
export default function ForgotPasswordPage() {
  const location = useLocation()
  const toast = useToast()
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  usePageTitle(sentTo ? 'Confira seu e-mail' : 'Esqueceu a senha?')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: (location.state as { email?: string } | null)?.email ?? '' },
  })

  async function onSubmit({ email }: ForgotValues) {
    setFormError(null)
    try {
      await authApi.forgot(email)
      setSentTo(email)
    } catch (error) {
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível enviar o link.')
    }
  }

  async function resend() {
    if (!sentTo) return
    setResending(true)
    try {
      await authApi.forgot(sentTo)
      toast.info('Se o e-mail estiver cadastrado, um novo link chega em instantes.')
    } catch (error) {
      toast.error(error instanceof ApiError ? sentence(error.message) : 'Não foi possível enviar o link.')
    } finally {
      setResending(false)
    }
  }

  if (sentTo) {
    return (
      <div className={styles.page}>
        <Mail size={44} strokeWidth={1.75} className={styles.icon} aria-hidden />
        <h1 className={styles.title}>Confira seu e-mail</h1>
        <p className={styles.subtitle}>
          Se o e-mail informado estiver cadastrado, enviamos um link para você criar uma nova senha. Se não encontrar,
          veja a caixa de spam.
        </p>
        <LinkButton to="/login" size="lg" block>
          Voltar para o login
        </LinkButton>
        <p className={styles.footer}>
          Não recebeu?{' '}
          <TextLink onClick={resend} disabled={resending}>
            Enviar de novo
          </TextLink>
        </p>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <BackLink to="/login" label="Voltar para o login" className={styles.back} />
      <h1 className={styles.title}>Esqueceu a senha?</h1>
      <p className={styles.subtitle}>
        Informe o e-mail da sua conta. Se ele estiver cadastrado, você recebe um link para criar uma nova senha.
      </p>
      <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
        <TextField
          label="E-mail"
          type="email"
          autoComplete="username"
          placeholder="nome@exemplo.com"
          error={errors.email?.message}
          {...register('email')}
        />
        {formError && <FormAlert>{formError}</FormAlert>}
        <Button type="submit" size="lg" block loading={isSubmitting} className={styles.submit}>
          Enviar link
        </Button>
      </form>
    </div>
  )
}
