import Logo from '../components/Logo/Logo'
import { cx } from '../lib/cx'
import styles from './BrandPanel.module.css'

// Painel da marca das telas de acesso (protótipo "Componente · Painel da marca"): o texto de
// apresentação e uma miniatura da tela de análise, desenhada em HTML e SVG (decorativa).
export default function BrandPanel({ className }: { className?: string }) {
  return (
    <aside className={cx(styles.panel, className)} aria-label="Sobre o NeuroSight">
      <div className={styles.copy}>
        <p className={styles.tagline}>Rastreamento ocular e emocional com Meta Quest Pro</p>
        <p className={styles.title}>NeuroSight</p>
        <p className={styles.description}>
          Estímulos, coleta do olhar e das expressões faciais e análise das sessões num só lugar.
        </p>
      </div>
      <PreviewWindow />
    </aside>
  )
}

const PREVIEW_NAV = ['Início', 'Sessões', 'Pacientes', 'Estímulos']

function PreviewWindow() {
  return (
    <div className={styles.preview} aria-hidden="true">
      <div className={styles.previewSidebar}>
        <div className={styles.previewBrand}>
          <Logo size={22} />
          NeuroSight
        </div>
        <ul className={styles.previewNav}>
          {PREVIEW_NAV.map((item) => (
            <li key={item} className={item === 'Sessões' ? styles.previewActive : undefined}>
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div className={styles.previewMain}>
        <p className={styles.previewTitle}>Análise da sessão</p>
        <div className={cx(styles.previewCard, styles.previewFace)}>
          <FaceHeatmap />
        </div>
        <div className={cx(styles.previewCard, styles.previewStat)} style={{ top: 50 }}>
          <span>Fixações</span>
          <strong>9</strong>
        </div>
        <div className={cx(styles.previewCard, styles.previewStat)} style={{ top: 122 }}>
          <span>Amostras válidas</span>
          <strong>94%</strong>
        </div>
        <div className={cx(styles.previewCard, styles.previewChart)}>
          <span className={styles.previewChartTitle}>Expressões faciais</span>
          <ExpressionsChart />
        </div>
      </div>
    </div>
  )
}

// Rosto ilustrado com o mapa de calor do olhar: azul nos olhos, laranja na boca.
function FaceHeatmap() {
  return (
    <svg viewBox="0 0 256 160" className={styles.faceSvg}>
      <defs>
        <radialGradient id="ns-heat-eyes">
          <stop offset="0" stopColor="#3b5bf0" stopOpacity="0.85" />
          <stop offset="0.55" stopColor="#3b5bf0" stopOpacity="0.45" />
          <stop offset="1" stopColor="#3b5bf0" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="ns-heat-mouth">
          <stop offset="0" stopColor="#f97316" stopOpacity="0.9" />
          <stop offset="1" stopColor="#f97316" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="256" height="160" fill="#c9d0d4" />
      <path d="M70 160c0-28 22-44 58-44s58 16 58 44Z" fill="#65737c" />
      <rect x="116" y="96" width="23" height="24" fill="#b9a594" />
      <ellipse cx="128" cy="67" rx="29" ry="36" fill="#cdb8a6" />
      <path d="M99 64c0-22 13-33 29-33s29 11 29 33c-6-9-15-14-29-14s-23 5-29 14Z" fill="#4e4843" />
      <path d="M111 62h13M132 62h13" stroke="#4b4f57" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="117.5" cy="70" rx="3" ry="2.2" fill="#3d3f47" />
      <ellipse cx="138.5" cy="70" rx="3" ry="2.2" fill="#3d3f47" />
      <path d="M119 91h18" stroke="#9f6b55" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="128" cy="70" rx="34" ry="26" fill="url(#ns-heat-eyes)" />
      <ellipse cx="128" cy="91" rx="16" ry="11" fill="url(#ns-heat-mouth)" />
    </svg>
  )
}

// Gráfico de expressões com as faixas dos estímulos (uma selecionada) e duas séries.
const BLUE_LINE = '12,92 32,90 52,84 67,64 82,85.5 107,88 116,56 130.5,84 152,89 172,82 182,68 197,86.5 222,90 236,74 249.5,87.5 282,88.5 294,60 307,86 342,90 372,88'
const ORANGE_LINE = '12,98 37,97 72,96 92,87 111,79 127,88 142,95.5 172,96.5 212,96.5 227,90 244.5,83 262,92 274.5,96.5 372,96'
const BANDS = [42.5, 102.5, 162.5, 222.5, 282.5]

function ExpressionsChart() {
  return (
    <svg viewBox="0 0 470 116" className={styles.chartSvg}>
      <defs>
        <pattern id="ns-stripes" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="8" height="8" fill="#f8f9fc" />
          <rect width="4" height="8" fill="#edf0f8" />
        </pattern>
      </defs>
      {BANDS.map((x, i) => (
        <rect key={x} x={x} y="34" width="20" height="70" fill={i === 1 ? '#dfe5fd' : 'url(#ns-stripes)'} />
      ))}
      <polyline points={BLUE_LINE} fill="none" stroke="#3b5bf0" strokeWidth="2" strokeLinejoin="round" />
      <polyline points={ORANGE_LINE} fill="none" stroke="#f97316" strokeWidth="2" strokeDasharray="0.1 4.4" strokeLinecap="round" />
    </svg>
  )
}
