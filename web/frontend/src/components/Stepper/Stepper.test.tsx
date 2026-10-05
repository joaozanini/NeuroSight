import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from '../Badge/StatusBadge'
import Stepper from './Stepper'

describe('Stepper', () => {
  it('marca as etapas concluídas e a atual', () => {
    render(<Stepper steps={['Paciente', 'Informações', 'Estímulos', 'Revisão']} current={2} />)
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Paciente (concluída)')
    expect(items[1]).toHaveTextContent('Informações (concluída)')
    expect(items[2]).toHaveAttribute('aria-current', 'step')
    expect(items[2]).toHaveTextContent('3Estímulos')
    expect(items[3]).not.toHaveAttribute('aria-current')
  })
})

describe('StatusBadge', () => {
  it('usa os textos dos protótipos', () => {
    render(
      <>
        <StatusBadge kind="session" status="running" />
        <StatusBadge kind="session" status="awaiting_data" />
        <StatusBadge kind="session" status="configured" />
        <StatusBadge kind="session" status="completed" />
        <StatusBadge kind="session" status="interrupted" />
        <StatusBadge kind="user" status="invited" />
        <StatusBadge kind="patient" status="inactive" />
      </>,
    )
    for (const text of ['Em andamento', 'Aguardando dados', 'Configurada', 'Concluída', 'Interrompida', 'Convite pendente', 'Inativo']) {
      expect(screen.getByText(text)).toBeInTheDocument()
    }
  })
})
