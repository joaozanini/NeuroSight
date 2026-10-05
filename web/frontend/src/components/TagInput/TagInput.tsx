import { useId, useRef, useState } from 'react'
import type { ClipboardEvent, KeyboardEvent, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import Field from '../Field/Field'
import { describedBy } from '../Field/describedBy'
import Tag from '../Tag/Tag'
import styles from './TagInput.module.css'

interface TagInputProps {
  id?: string
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  value: string[]
  onChange: (tags: string[]) => void
  onBlur?: () => void
  placeholder?: string
  disabled?: boolean
  // Ajuste do texto antes de virar etiqueta; o padrão tira espaços sobrando.
  normalize?: (text: string) => string
  className?: string
}

const defaultNormalize = (text: string) => text.trim().replace(/\s+/g, ' ')

// Campo de etiquetas (W10, W11): Enter ou vírgula adiciona, Backspace no campo vazio tira a última.
export default function TagInput({
  id,
  label,
  hint,
  error,
  value,
  onChange,
  onBlur,
  placeholder = 'Adicionar etiqueta',
  disabled = false,
  normalize = defaultNormalize,
  className,
}: TagInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const inputRef = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState('')

  function add(texts: string[]) {
    const next = [...value]
    for (const raw of texts) {
      const tag = normalize(raw)
      if (tag && !next.some((t) => t.toLocaleLowerCase('pt-BR') === tag.toLocaleLowerCase('pt-BR'))) next.push(tag)
    }
    if (next.length !== value.length) onChange(next)
    setDraft('')
  }

  function remove(index: number) {
    onChange(value.filter((_, i) => i !== index))
    inputRef.current?.focus()
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add([draft])
    } else if (event.key === 'Backspace' && draft === '' && value.length > 0) {
      event.preventDefault()
      onChange(value.slice(0, -1))
    }
  }

  function onPaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData('text')
    if (!/[,\n]/.test(text)) return
    event.preventDefault()
    add((draft + text).split(/[,\n]/))
  }

  return (
    <Field id={inputId} label={label} hint={hint} error={error} className={className}>
      <div
        className={cx(styles.box, error ? styles.invalid : undefined, disabled && styles.disabled)}
        onClick={() => inputRef.current?.focus()}
      >
        <ul className={styles.tags} aria-label="Etiquetas adicionadas">
          {value.map((tag, index) => (
            <li key={tag}>
              <Tag size="md" onRemove={disabled ? undefined : () => remove(index)} removeLabel={`Remover a etiqueta ${tag}`}>
                {tag}
              </Tag>
            </li>
          ))}
        </ul>
        <input
          ref={inputRef}
          id={inputId}
          className={styles.input}
          value={draft}
          placeholder={placeholder}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(inputId, { hint, error })}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={() => {
            if (draft.trim()) add([draft])
            onBlur?.()
          }}
        />
      </div>
    </Field>
  )
}
