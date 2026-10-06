import { forwardRef } from 'react'
import { maskDate } from '../../lib/dates'
import TextField from '../TextField/TextField'
import type { TextFieldProps } from '../TextField/TextField'

interface DateFieldProps extends Omit<TextFieldProps, 'value' | 'onChange' | 'type'> {
  // Texto como aparece no campo ("12/03/1998"); converta com parseBrDate ao salvar.
  value: string
  onChange: (value: string) => void
}

// Data digitada como nos protótipos (W07): "dd/mm/aaaa", com as barras postas sozinhas.
const DateField = forwardRef<HTMLInputElement, DateFieldProps>(function DateField(
  { value, onChange, placeholder = 'dd/mm/aaaa', ...rest },
  ref,
) {
  return (
    <TextField
      ref={ref}
      {...rest}
      value={value}
      inputMode="numeric"
      autoComplete="off"
      maxLength={10}
      placeholder={placeholder}
      onChange={(event) => onChange(maskDate(event.target.value))}
    />
  )
})

export default DateField
