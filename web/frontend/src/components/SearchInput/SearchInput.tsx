import { forwardRef } from 'react'
import { Search } from 'lucide-react'
import TextField from '../TextField/TextField'
import type { TextFieldProps } from '../TextField/TextField'
import styles from './SearchInput.module.css'

export type SearchInputProps = Omit<TextFieldProps, 'type' | 'leadingIcon' | 'label'> & {
  // Rótulo para leitores de tela; os protótipos só mostram o placeholder.
  label?: string
}

// Busca das listas ("Buscar por nome ou código"): lupa à esquerda, 48 px como os filtros.
const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(function SearchInput(
  { label, placeholder, size = 'md', className, ...rest },
  ref,
) {
  return (
    <TextField
      ref={ref}
      type="search"
      label={label ?? placeholder}
      hideLabel
      placeholder={placeholder}
      leadingIcon={Search}
      size={size}
      className={[styles.search, className].filter(Boolean).join(' ')}
      autoComplete="off"
      {...rest}
    />
  )
})

export default SearchInput
