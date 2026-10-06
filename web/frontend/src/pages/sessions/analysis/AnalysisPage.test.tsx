import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../../App'
import type { AnalysisExposure, SessionAnalysis } from '../../../api/analysis'
import { mockApi, reply } from '../../../test/api'
import { RESEARCHER } from '../../../test/fixtures'
import { renderWithProviders } from '../../../test/render'
import { markerLabel, seriesPath, timeTicks } from './chartScale'
import { frameIndexAt, sessionTimeAt, videoTimeAt } from '../../../heatmap/gazeVideo'
import { accumulate } from '../../../heatmap/heatmapEngine'

afterEach(() => {
  vi.unstubAllGlobals()
})

function exposure(seq: number, position: number, name: string, on: number, extra: Partial<AnalysisExposure> = {}): AnalysisExposure {
  return {
    seq,
    position,
    stimulus_id: `st${position}`,
    name,
    kind: 'image',
    thumbnail_url: `/api/v1/stimuli/st${position}/thumbnail`,
    file_url: `/api/v1/stimuli/st${position}/file`,
    width: 1600,
    height: 1000,
    on_t: on,
    off_t: on + 5,
    samples: 360,
    valid_samples: 320,
    fixation_count: 3,
    mean_fixation_ms: 334.4,
    first_fixation_ms: 296.2,
    fixations: [
      [on + 0.3, 0.4, 0.4, 0.4],
      [on + 0.8, 0.3, 0.6, 0.4],
      [on + 1.2, 0.5, 0.5, 0.7],
    ],
    heat: [
      [0.4, 0.4, 20],
      [0.6, 0.4, 15],
    ],
    ...extra,
  }
}

const ANALYSIS: SessionAnalysis = {
  id: 's3',
  title: 'Rostos neutros e expressivos',
  patient_code: 'P-015',
  started_at: '2026-09-29T17:26:00Z',
  status: 'completed',
  duration: 110,
  exposures: [
    exposure(1, 1, 'Rosto neutro 01', 20),
    exposure(2, 2, 'Rosto alegre 02', 27),
    exposure(3, 3, 'Rosto surpreso 03', 34, { fixation_count: 8, mean_fixation_ms: 334, first_fixation_ms: 296, valid_samples: 320, samples: 360 }),
  ],
  markers: [
    { t: 28, text: 'Paciente movimentou a cabeça' },
    { t: 65, text: 'Enfermagem entrou no quarto' },
  ],
  recording_status: 'ready',
  recording: {
    url: '/api/v1/sessions/s3/recording',
    fps: 10,
    width: 640,
    height: 400,
    frame_t: Array.from({ length: 1100 }, (_, i) => i / 10),
    frame_gaze: Array.from({ length: 1100 }, () => [0.5, 0.5] as [number, number]),
  },
  face: {
    hz: 10,
    series: [
      { key: 'INNER_BROW_RAISER', label: 'Sobrancelha interna elevada', values: Array.from({ length: 1100 }, () => 0.1) },
      { key: 'LIP_CORNER_PULLER', label: 'Canto da boca puxado', values: Array.from({ length: 1100 }, (_, i) => (i < 5 ? null : 0.05)) },
      { key: 'EYES_CLOSED', label: 'Olhos fechados', values: Array.from({ length: 1100 }, () => 0.03) },
    ],
  },
  can_export: true,
}

function setup(analysis: SessionAnalysis | Response = ANALYSIS, route = '/sessoes/s3/analise') {
  const api = mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/:id/analysis': analysis })
  renderWithProviders(<App />, { route })
  return api
}

describe('W17 Análise da sessão', () => {
  it('mostra o cabeçalho, a tira de estímulos e as métricas do primeiro', async () => {
    setup()
    expect(await screen.findByText('Rostos neutros e expressivos, paciente P-015, 29/09/2026')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Análise da sessão' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Detalhes da sessão' })).toHaveAttribute('href', '/sessoes/s3')
    expect(screen.getByRole('link', { name: 'Baixar JSON' }).getAttribute('href')).toMatch(/^\/api\/v1\/sessions\/s3\/downloads\/tracking\?tz=/)
    expect(screen.getByRole('link', { name: 'Baixar CSV por estímulo' }).getAttribute('href')).toMatch(/\/downloads\/csv\?tz=/)

    const strip = screen.getByRole('radiogroup', { name: 'Estímulo analisado' })
    const thumbs = within(strip).getAllByRole('radio')
    expect(thumbs).toHaveLength(3)
    expect(thumbs[0]).toHaveAccessibleName('Estímulo 1: Rosto neutro 01, exibido de 00:20 a 00:25')
    expect(thumbs[0]).toBeChecked()

    expect(screen.getByRole('heading', { name: 'Estímulo 1: Rosto neutro 01' })).toBeInTheDocument()
    expect(screen.getByText('Exibido de 00:20 a 00:25')).toBeInTheDocument()
    expect(screen.getByText('Menos tempo')).toBeInTheDocument()
    expect(screen.getByText('Mais tempo de olhar')).toBeInTheDocument()
    const metrics = Object.fromEntries(
      screen.getAllByRole('term').map((dt) => [dt.textContent, dt.nextElementSibling?.textContent]),
    )
    expect(metrics).toEqual({
      Fixações: '3',
      'Duração média da fixação': '334 ms',
      'Tempo até a 1ª fixação': '296 ms',
      'Amostras válidas': '89%',
    })
    expect(screen.getByText('O círculo mostra para onde o paciente olhava. A gravação acompanha o estímulo escolhido e o gráfico abaixo.')).toBeInTheDocument()
    // A gravação começa no estímulo escolhido.
    expect(screen.getByText('00:20 / 01:50')).toBeInTheDocument()
  })

  it('escolher outro estímulo pela tira ou pela faixa do gráfico troca a análise e leva a gravação até ele', async () => {
    const user = userEvent.setup()
    setup()
    const strip = await screen.findByRole('radiogroup', { name: 'Estímulo analisado' })
    await user.click(within(strip).getAllByRole('radio')[2])
    expect(screen.getByRole('heading', { name: 'Estímulo 3: Rosto surpreso 03' })).toBeInTheDocument()
    expect(screen.getByText('Exibido de 00:34 a 00:39')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('00:34 / 01:50')).toBeInTheDocument()
    expect((document.querySelector('video[src="/api/v1/sessions/s3/recording"]') as HTMLVideoElement).currentTime).toBeCloseTo(34.001, 2)

    await user.click(screen.getByRole('button', { name: 'Analisar o estímulo 2: Rosto alegre 02, de 00:27 a 00:32' }))
    expect(screen.getByRole('heading', { name: 'Estímulo 2: Rosto alegre 02' })).toBeInTheDocument()
    expect(within(strip).getAllByRole('radio')[1]).toBeChecked()
    expect(screen.getByRole('button', { name: /Analisar o estímulo 2/ })).toHaveAttribute('aria-pressed', 'true')

    // As setas andam pela tira.
    within(strip).getAllByRole('radio')[1].focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('heading', { name: 'Estímulo 3: Rosto surpreso 03' })).toBeInTheDocument()
  })

  it('a exibição escolhida fica na URL', async () => {
    setup(ANALYSIS, '/sessoes/s3/analise?exibicao=2')
    expect(await screen.findByRole('heading', { name: 'Estímulo 2: Rosto alegre 02' })).toBeInTheDocument()
  })

  it('mostra a trajetória com as fixações numeradas', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole('radio', { name: 'Trajetória do olhar' }))
    const path = screen.getByRole('img', { name: 'Trajetória do olhar sobre Rosto neutro 01: 3 fixações' })
    expect(Array.from(path.querySelectorAll('text')).map((t) => t.textContent)).toEqual(['1', '2', '3'])
    expect(path.querySelectorAll('circle')).toHaveLength(3)
    expect(screen.queryByText('Mais tempo de olhar')).not.toBeInTheDocument()
  })

  it('o gráfico tem as faixas dos estímulos, as marcações e a legenda padrão', async () => {
    setup()
    const chart = await screen.findByRole('group', { name: 'Expressões faciais ao longo da sessão' })
    expect(within(chart).getAllByRole('button')).toHaveLength(3)
    expect(within(chart).getByText('00:28 Paciente movimentou a cabeça')).toBeInTheDocument()
    expect(within(chart).getByText('01:05 Enfermagem entrou no quarto')).toBeInTheDocument()
    expect(within(chart).getAllByText(/^0[01]:[0-9]0$/).map((t) => t.textContent)).toEqual(['00:00', '00:20', '00:40', '01:00', '01:20', '01:40'])
    expect(chart.querySelectorAll('path')).toHaveLength(3)
    expect(screen.getByText('Sobrancelha interna elevada')).toBeInTheDocument()
    expect(screen.getByText('Canto da boca puxado')).toBeInTheDocument()
    expect(screen.getByText('Olhos fechados')).toBeInTheDocument()
  })

  it('a gravação toca, pausa e anda pela barra', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(await screen.findByRole('button', { name: 'Tocar a gravação' }))
    expect(screen.getByRole('button', { name: 'Pausar a gravação' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Pausar a gravação' }))
    const slider = screen.getByRole('slider', { name: 'Posição na gravação' })
    fireEvent.change(slider, { target: { value: '65' } })
    expect(screen.getByText('01:05 / 01:50')).toBeInTheDocument()
    expect(slider).toHaveAttribute('aria-valuetext', '01:05 de 01:50')
  })

  it('sem gravação, sem facial e sem permissão de exportar', async () => {
    setup({ ...ANALYSIS, recording: null, recording_status: 'none', face: null, can_export: false })
    expect(await screen.findByText('Esta sessão não foi gravada.')).toBeInTheDocument()
    expect(screen.getByText('O rastreamento facial não estava ativo nesta sessão.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Baixar JSON' })).not.toBeInTheDocument()
  })

  it('sessão sem estímulo exibido', async () => {
    setup({ ...ANALYSIS, exposures: [] })
    expect(await screen.findByText('Nenhum estímulo foi exibido nesta sessão.')).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: 'Estímulo analisado' })).not.toBeInTheDocument()
  })

  it('dados ainda não processados mostram a mensagem do servidor', async () => {
    setup(reply(409, { detail: 'os dados desta sessão ainda não foram processados' }))
    expect(await screen.findByText('Os dados desta sessão ainda não foram processados.')).toBeInTheDocument()
  })
})

describe('peças da W17', () => {
  it('eixo do tempo, caminhos das séries e rótulos das marcações', () => {
    expect(timeTicks(110)).toEqual([0, 20, 40, 60, 80, 100])
    expect(timeTicks(25)).toEqual([0, 5, 10, 15, 20, 25])
    expect(timeTicks(1800)).toEqual([0, 300, 600, 900, 1200, 1500, 1800])
    const x = (t: number) => t * 10
    const y = (v: number) => 100 - v * 100
    expect(seriesPath([0.5, null, 0.2, 0.4], 10, x, y)).toBe('M0.5 50.0M2.5 80.0L3.5 60.0')
    expect(markerLabel(28, 'Paciente movimentou a cabeça', 400)).toBe('00:28 Paciente movimentou a cabeça')
    expect(markerLabel(28, 'Paciente movimentou a cabeça', 120)).toBe('00:28 Paciente…')
    expect(markerLabel(28, 'Paciente movimentou a cabeça', 50)).toBe('00:28')
  })

  it('tempo do vídeo e tempo da sessão pelos frames', () => {
    const frameT = [0.2, 0.31, 0.45, 0.6]
    expect(frameIndexAt(0.15, 10, 4)).toBe(1)
    expect(sessionTimeAt(0.25, 10, frameT)).toBe(0.45)
    expect(videoTimeAt(0.4, 10, frameT)).toBeCloseTo(0.201)
    expect(videoTimeAt(99, 10, frameT)).toBeCloseTo(0.301)
  })

  it('o mapa de calor acumula o tempo de olhar em volta de cada ponto', () => {
    const acc = accumulate([[0.5, 0.5, 2], [0.1, 0.1, 1]], 20, 10, 1)
    const at = (x: number, y: number) => acc[y * 20 + x]
    expect(at(10, 5)).toBeCloseTo(2)
    expect(at(2, 1)).toBeCloseTo(1)
    expect(at(11, 5)).toBeLessThan(at(10, 5))
    expect(at(19, 9)).toBe(0)
  })
})
