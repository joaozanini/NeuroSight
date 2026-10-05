import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { authApi, useCurrentUser } from '../api/auth'
import { ApiError } from '../api/client'
import Button from '../components/Button/Button'
import FormAlert from '../components/FormAlert/FormAlert'
import PageHeader from '../components/PageHeader/PageHeader'
import PasswordField from '../components/PasswordField/PasswordField'
import Tag from '../components/Tag/Tag'
import TextField from '../components/TextField/TextField'
import { useToast } from '../components/Toast/toastContext'
import { sentence } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { PASSWORDS_DIFFER, confirmPasswordField, newPasswordField } from '../lib/validation'
import styles from './ProfilePage.module.css'

const schema = z
  .object({
    current: z.string().min(1, 'Informe a senha atual.'),
    password: newPasswordField,
    confirm: confirmPasswordField,
  })
  .refine((v) => v.password === v.confirm, { message: PASSWORDS_DIFFER, path: ['confirm'] })

type ChangeValues = z.infer<typeof schema>

const EMPTY: ChangeValues = { current: '', password: '', confirm: '' }

// W05: dados da conta (só leitura, definidos pelo admin) e a troca da própria senha.
export default function ProfilePage() {
  usePageTitle('Meu perfil')
  const me = useCurrentUser()
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)
  // Remonta o campo da senha nova ao limpar o formulário, para as regras voltarem a zero.
  const [formKey, setFormKey] = useState(0)

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangeValues>({ resolver: zodResolver(schema), defaultValues: EMPTY })

  async function onSubmit(values: ChangeValues) {
    setFormError(null)
    try {
      await authApi.changePassword(values.current, values.password)
      reset(EMPTY)
      setFormKey((k) => k + 1)
      toast.success('Senha alterada.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        setError('current', { message: sentence(error.message) })
        return
      }
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível alterar a senha.')
    }
  }

  return (
    <>
      <PageHeader title="Meu perfil" />
      <div className={styles.columns}>
        <section aria-labelledby="dados-da-conta">
          <h2 id="dados-da-conta" className={styles.heading}>
            Dados da conta
          </h2>
          <dl className={styles.data}>
            <div>
              <dt>Nome</dt>
              <dd>{me.name}</dd>
            </div>
            <div>
              <dt>E-mail</dt>
              <dd>{me.email}</dd>
            </div>
            <div>
              <dt>Perfil</dt>
              <dd>
                <Tag size="md">{me.role_label}</Tag>
              </dd>
            </div>
          </dl>
          <p className={styles.note}>
            Nome, e-mail e perfil são definidos pelo administrador. Para corrigir algum dado, fale com ele.
          </p>
        </section>

        <section aria-labelledby="alterar-senha">
          <h2 id="alterar-senha" className={styles.heading}>
            Alterar senha
          </h2>
          <form key={formKey} className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
            <input type="email" name="username" autoComplete="username" value={me.email} readOnly hidden />
            <TextField label="Senha atual" type="password" autoComplete="current-password" error={errors.current?.message} {...register('current')} />
            <PasswordField label="Nova senha" autoComplete="new-password" showRules error={errors.password?.message} {...register('password')} />
            <TextField label="Confirmar nova senha" type="password" autoComplete="new-password" error={errors.confirm?.message} {...register('confirm')} />
            {formError && <FormAlert>{formError}</FormAlert>}
            <div>
              <Button type="submit" size="lg" loading={isSubmitting} className={styles.submit}>
                Salvar nova senha
              </Button>
            </div>
          </form>
        </section>
      </div>
    </>
  )
}
