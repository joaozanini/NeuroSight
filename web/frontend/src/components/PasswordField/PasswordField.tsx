import { forwardRef, useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import TextField from '../TextField/TextField'
import type { TextFieldProps } from '../TextField/TextField'
import PasswordRules from './PasswordRules'
import styles from './PasswordField.module.css'

export interface PasswordFieldProps extends Omit<TextFieldProps, 'type' | 'trailing'> {
  // Mostra a lista "A senha precisa ter:" com as regras marcadas ao vivo (W03, W05).
  showRules?: boolean
}

// Senha com o botão de olho. Funciona controlado (value) ou com o register do react-hook-form:
// nesse caso acompanha o valor pelo onChange para marcar as regras.
const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(function PasswordField(
  { id, showRules = false, value, defaultValue, onChange, ...rest },
  ref,
) {
  const autoId = useId()
  const inputId = id ?? autoId
  const [visible, setVisible] = useState(false)
  const [typed, setTyped] = useState(String(defaultValue ?? ''))
  const current = value !== undefined ? String(value) : typed

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    setTyped(event.target.value)
    onChange?.(event)
  }

  return (
    <div className={styles.wrapper}>
      <TextField
        ref={ref}
        id={inputId}
        type={visible ? 'text' : 'password'}
        value={value}
        defaultValue={defaultValue}
        onChange={handleChange}
        aria-describedby={showRules ? `${inputId}-rules` : undefined}
        trailing={
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Esconder a senha' : 'Mostrar a senha'}
            aria-pressed={visible}
            aria-controls={inputId}
          >
            {visible ? <EyeOff size={22} aria-hidden /> : <Eye size={22} aria-hidden />}
          </button>
        }
        {...rest}
      />
      {showRules && <PasswordRules id={`${inputId}-rules`} value={current} />}
    </div>
  )
})

export default PasswordField
