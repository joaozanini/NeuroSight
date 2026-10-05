import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Button from '../Button/Button'
import Modal from './Modal'

function Harness({ dismissible = true, onClose = () => undefined }: { dismissible?: boolean; onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Alterar visibilidade</Button>
      <Modal
        open={open}
        onClose={() => {
          onClose()
          setOpen(false)
        }}
        title="Visibilidade da sessão"
        subtitle="Rostos neutros e expressivos, paciente P-015"
        dismissible={dismissible}
        footerNote="A mudança fica registrada na auditoria."
        footer={<Button onClick={() => setOpen(false)}>Salvar</Button>}
      >
        <input aria-label="Buscar pesquisador" />
      </Modal>
    </>
  )
}

describe('Modal', () => {
  it('abre como diálogo, com título e descrição, e leva o foco para dentro', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Alterar visibilidade' }))
    const dialog = screen.getByRole('dialog', { name: 'Visibilidade da sessão' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleDescription('Rostos neutros e expressivos, paciente P-015')
    expect(screen.getByText('A mudança fica registrada na auditoria.')).toBeInTheDocument()
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
  })

  it('fecha com Esc e devolve o foco a quem abriu', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const opener = screen.getByRole('button', { name: 'Alterar visibilidade' })
    await user.click(opener)
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('fecha pelo X e mantém o Tab dentro do diálogo', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Alterar visibilidade' }))
    const close = screen.getByRole('button', { name: 'Fechar' })
    const save = screen.getByRole('button', { name: 'Salvar' })
    save.focus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(save).toHaveFocus()
    await user.click(close)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('não fecha com Esc quando não pode ser interrompido', async () => {
    const user = userEvent.setup()
    render(<Harness dismissible={false} />)
    await user.click(screen.getByRole('button', { name: 'Alterar visibilidade' }))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fechar' })).not.toBeInTheDocument()
  })
})
