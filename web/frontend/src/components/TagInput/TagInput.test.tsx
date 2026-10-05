import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TagInput from './TagInput'

function Harness({ initial = [] as string[] }) {
  const [tags, setTags] = useState(initial)
  return (
    <>
      <TagInput label="Etiquetas" value={tags} onChange={setTags} />
      <output>{tags.join('|')}</output>
    </>
  )
}

describe('TagInput', () => {
  it('adiciona com Enter e vírgula, sem repetir', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByLabelText('Etiquetas')
    expect(input).toHaveAttribute('placeholder', 'Adicionar etiqueta')
    await user.type(input, 'paisagem{Enter}natureza,')
    await user.type(input, 'Paisagem{Enter}  {Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('paisagem|natureza')
  })

  it('Backspace no campo vazio tira a última; o x tira a escolhida', async () => {
    const user = userEvent.setup()
    render(<Harness initial={['rosto', 'neutro', 'alegria']} />)
    await user.type(screen.getByLabelText('Etiquetas'), '{Backspace}')
    expect(screen.getByRole('status')).toHaveTextContent('rosto|neutro')
    await user.click(screen.getByRole('button', { name: 'Remover a etiqueta rosto' }))
    expect(screen.getByRole('status')).toHaveTextContent(/^neutro$/)
  })

  it('separa etiquetas coladas com vírgulas e confirma o texto ao sair do campo', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByLabelText('Etiquetas')
    await user.click(input)
    await user.paste('mar, praia,sol')
    await user.type(input, 'verão')
    await user.tab()
    expect(screen.getByRole('status')).toHaveTextContent('mar|praia|sol|verão')
  })
})
