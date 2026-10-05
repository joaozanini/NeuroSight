import { forwardRef, useId } from 'react'
import type { ReactNode, TextareaHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'
import Field from '../Field/Field'
import { describedBy } from '../Field/describedBy'
import fieldStyles from '../Field/Field.module.css'
import styles from './Textarea.module.css'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  fieldClassName?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { id, label, hint, error, fieldClassName, className, rows = 4, ...rest },
  ref,
) {
  const autoId = useId()
  const textareaId = id ?? autoId
  return (
    <Field id={textareaId} label={label} hint={hint} error={error} className={fieldClassName}>
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(textareaId, { hint, error })}
        className={cx(fieldStyles.control, styles.textarea, className)}
        {...rest}
      />
    </Field>
  )
})

export default Textarea
