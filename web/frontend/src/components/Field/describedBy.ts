import type { ReactNode } from 'react'

export interface FieldMessages {
  hint?: ReactNode
  error?: ReactNode
}

// id da mensagem (erro ou dica) que o campo anuncia via aria-describedby.
export function describedBy(id: string, { hint, error }: FieldMessages): string | undefined {
  if (error) return `${id}-error`
  if (hint) return `${id}-hint`
  return undefined
}
