import { useCallback, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { analysisApi } from '../../../api/analysis'
import type { AnalysisExposure, SessionAnalysis } from '../../../api/analysis'
import { downloadUrl, sessionsKeys } from '../../../api/sessions'
import AnchorButton from '../../../components/Button/AnchorButton'
import Card from '../../../components/Card/Card'
import FormAlert from '../../../components/FormAlert/FormAlert'
import PageHeader from '../../../components/PageHeader/PageHeader'
import Segmented from '../../../components/Segmented/Segmented'
import Spinner from '../../../components/Spinner/Spinner'
import StimulusThumbnail from '../../../components/StimulusThumbnail/StimulusThumbnail'
import { HEAT_LEGEND } from '../../../heatmap/palette'
import { cx } from '../../../lib/cx'
import { formatClock, formatDate, formatNumber, formatPercent, sentence } from '../../../lib/format'
import { usePageTitle } from '../../../lib/usePageTitle'
import ExpressionsChart, { SERIES_STYLES } from './ExpressionsChart'
import RecordingPlayer from './RecordingPlayer'
import type { SeekRequest } from './RecordingPlayer'
import StimulusGaze from './StimulusGaze'
import type { GazeView } from './StimulusGaze'
import styles from './SessionAnalysisPage.module.css'

const VIEWS: { value: GazeView; label: string }[] = [
  { value: 'heatmap', label: 'Mapa de calor' },
  { value: 'path', label: 'Trajetória do olhar' },
]

// W17: a análise de uma sessão com os dados processados. A exibição escolhida fica na URL
// (?exibicao=N, a ordem em que apareceu), para voltar à mesma ao recarregar.
export default function SessionAnalysisPage() {
  const { sessionId = '' } = useParams()
  usePageTitle('Análise da sessão')
  const analysis = useQuery({
    queryKey: sessionsKeys.analysis(sessionId),
    queryFn: ({ signal }) => analysisApi.get(sessionId, signal),
  })
  const back = { to: `/sessoes/${sessionId}`, label: 'Detalhes da sessão' }

  if (analysis.isPending) {
    return (
      <>
        <PageHeader title="Análise da sessão" back={back} />
        <Spinner size={28} label="Carregando a análise" />
      </>
    )
  }
  if (analysis.isError) {
    return (
      <>
        <PageHeader title="Análise da sessão" back={back} />
        <FormAlert>{sentence(analysis.error.message)}</FormAlert>
      </>
    )
  }
  return <AnalysisView analysis={analysis.data} back={back} />
}

function AnalysisView({ analysis, back }: { analysis: SessionAnalysis; back: { to: string; label: string } }) {
  const [params, setParams] = useSearchParams()
  const exposures = analysis.exposures
  const requested = Number(params.get('exibicao'))
  const selected = exposures.find((e) => e.seq === requested) ?? exposures[0] ?? null
  const [view, setView] = useState<GazeView>('heatmap')
  const [seek, setSeek] = useState<SeekRequest | null>(selected ? { t: selected.on_t, nonce: 0 } : null)
  const [playhead, setPlayhead] = useState<number | null>(null)
  const nonce = useRef(0)

  const select = useCallback(
    (seq: number) => {
      const exposure = exposures.find((e) => e.seq === seq)
      if (!exposure) return
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.set('exibicao', String(seq))
          return next
        },
        { replace: true },
      )
      nonce.current += 1
      setSeek({ t: exposure.on_t, nonce: nonce.current })
    },
    [exposures, setParams],
  )

  const subtitle = [analysis.title, `paciente ${analysis.patient_code}`, analysis.started_at && formatDate(analysis.started_at)]
    .filter(Boolean)
    .join(', ')
  const cursor = analysis.recording ? playhead : (selected?.on_t ?? null)

  return (
    <>
      <PageHeader
        title="Análise da sessão"
        subtitle={subtitle}
        back={back}
        actions={
          analysis.can_export && (
            <>
              <AnchorButton variant="secondary" size="sm" icon={Download} href={downloadUrl(analysis.id, 'tracking')} download>
                Baixar JSON
              </AnchorButton>
              <AnchorButton variant="secondary" size="sm" icon={Download} href={downloadUrl(analysis.id, 'csv')} download>
                Baixar CSV por estímulo
              </AnchorButton>
            </>
          )
        }
      />

      {selected && <ExposureStrip exposures={exposures} selectedSeq={selected.seq} onSelect={select} />}

      <div className={styles.grid}>
        {selected ? (
          <ExposureCard exposure={selected} view={view} onView={setView} />
        ) : (
          <Card className={styles.card}>
            <p className={styles.muted}>Nenhum estímulo foi exibido nesta sessão.</p>
          </Card>
        )}
        <Card padding="none" className={cx(styles.card, styles.recordingCard)} aria-labelledby="gravacao">
          <h2 id="gravacao" className={styles.cardTitle}>
            Gravação da sessão
          </h2>
          {analysis.recording ? (
            <>
              <RecordingPlayer recording={analysis.recording} duration={analysis.duration} seek={seek} onTime={setPlayhead} />
              <p className={styles.caption}>
                O círculo mostra para onde o paciente olhava. A gravação acompanha o estímulo escolhido e o gráfico abaixo.
              </p>
            </>
          ) : (
            <p className={styles.noRecording}>
              {analysis.recording_status === 'failed'
                ? 'Não foi possível montar o vídeo desta sessão.'
                : 'Esta sessão não foi gravada.'}
            </p>
          )}
        </Card>
      </div>

      <Expressions analysis={analysis} selectedSeq={selected?.seq ?? null} cursor={cursor} onSelect={select} />
    </>
  )
}

function ExposureStrip({
  exposures,
  selectedSeq,
  onSelect,
}: {
  exposures: AnalysisExposure[]
  selectedSeq: number
  onSelect: (seq: number) => void
}) {
  const groupRef = useRef<HTMLDivElement>(null)

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    event.preventDefault()
    const current = exposures.findIndex((e) => e.seq === selectedSeq)
    const next = Math.min(exposures.length - 1, Math.max(0, current + delta))
    onSelect(exposures[next].seq)
    groupRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus()
  }

  return (
    <section className={styles.strip} aria-labelledby="estimulo-analisado">
      <h2 id="estimulo-analisado" className={styles.stripLabel}>
        Estímulo analisado
      </h2>
      <div ref={groupRef} role="radiogroup" aria-labelledby="estimulo-analisado" className={styles.thumbs} onKeyDown={onKeyDown}>
        {exposures.map((e) => {
          const checked = e.seq === selectedSeq
          return (
            <button
              key={e.seq}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked ? 0 : -1}
              aria-label={`Estímulo ${e.position}: ${e.name}, exibido de ${formatClock(e.on_t)} a ${formatClock(e.off_t)}`}
              className={cx(styles.thumbButton, checked && styles.thumbSelected)}
              onClick={() => onSelect(e.seq)}
            >
              <StimulusThumbnail src={e.thumbnail_url} kind={e.kind} className={styles.thumb} />
              <span className={styles.thumbNumber} aria-hidden>
                {e.position}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function ExposureCard({ exposure, view, onView }: { exposure: AnalysisExposure; view: GazeView; onView: (v: GazeView) => void }) {
  const ms = (value: number | null) => (value === null ? '—' : `${formatNumber(Math.round(value))} ms`)
  return (
    <Card padding="none" className={styles.card} aria-labelledby="estimulo-titulo">
      <header className={styles.exposureHeader}>
        <div>
          <h2 id="estimulo-titulo" className={styles.cardTitle}>
            Estímulo {exposure.position}: {exposure.name}
          </h2>
          <p className={styles.exposureTime}>
            Exibido de {formatClock(exposure.on_t)} a {formatClock(exposure.off_t)}
          </p>
        </div>
        <Segmented options={VIEWS} value={view} onChange={onView} ariaLabel="Como ver o olhar" />
      </header>
      <StimulusGaze exposure={exposure} view={view} />
      {view === 'heatmap' ? (
        <p className={styles.legend}>
          <span>Menos tempo</span>
          <span className={styles.legendBar} style={{ background: HEAT_LEGEND }} aria-hidden />
          <span>Mais tempo de olhar</span>
        </p>
      ) : (
        <p className={styles.legend}>Fixações na ordem em que aconteceram; quanto maior o círculo, mais longa a fixação.</p>
      )}
      <dl className={styles.metrics}>
        <div>
          <dt>Fixações</dt>
          <dd>{formatNumber(exposure.fixation_count)}</dd>
        </div>
        <div>
          <dt>Duração média da fixação</dt>
          <dd>{ms(exposure.mean_fixation_ms)}</dd>
        </div>
        <div>
          <dt>Tempo até a 1ª fixação</dt>
          <dd>{ms(exposure.first_fixation_ms)}</dd>
        </div>
        <div>
          <dt>Amostras válidas</dt>
          <dd>{exposure.samples ? formatPercent(exposure.valid_samples / exposure.samples) : '—'}</dd>
        </div>
      </dl>
    </Card>
  )
}

function Expressions({
  analysis,
  selectedSeq,
  cursor,
  onSelect,
}: {
  analysis: SessionAnalysis
  selectedSeq: number | null
  cursor: number | null
  onSelect: (seq: number) => void
}) {
  const face = analysis.face
  const series = useMemo(() => face?.series ?? [], [face])
  return (
    <Card padding="none" className={cx(styles.card, styles.expressions)} aria-labelledby="expressoes">
      <header className={styles.expressionsHeader}>
        <div className={styles.expressionsText}>
          <h2 id="expressoes" className={styles.cardTitle}>
            Expressões faciais ao longo da sessão
          </h2>
          <p className={styles.muted}>
            Intensidade de 0 a 1 de cada expressão, fornecida pelo rastreamento facial do Quest Pro. As faixas marcam os
            estímulos: clique numa faixa para analisar o estímulo.
          </p>
        </div>
        {series.length > 0 && (
          <ul className={styles.seriesLegend}>
            {series.map((s) => (
              <li key={s.key}>
                <svg width="28" height="6" aria-hidden>
                  <line x1="1" x2="27" y1="3" y2="3" className={SERIES_STYLES[s.key]} />
                </svg>
                {s.label}
              </li>
            ))}
          </ul>
        )}
      </header>
      {face && series.length > 0 ? (
        <ExpressionsChart
          duration={analysis.duration}
          hz={face.hz}
          series={series}
          exposures={analysis.exposures}
          markers={analysis.markers}
          selectedSeq={selectedSeq}
          cursor={cursor}
          onSelect={onSelect}
        />
      ) : (
        <p className={styles.noFace}>O rastreamento facial não estava ativo nesta sessão.</p>
      )}
    </Card>
  )
}
