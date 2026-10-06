// Estado do assistente de nova sessão (W13), que passa de uma etapa para a outra até "Salvar".
import type { PatientRow } from '../../../api/patients'
import type { SessionDetail, SessionInput } from '../../../api/sessions'
import type { StimulusKind } from '../../../api/stimuli'
import { DEFAULT_IMAGE_SECONDS, parseSeconds, secondsText } from '../sequence'

export const STEPS = ['Paciente', 'Informações', 'Estímulos', 'Revisão']

export type WizardPatient = Pick<PatientRow, 'id' | 'code' | 'name' | 'birth_date' | 'sessions_count'>

export interface WizardItem {
  stimulus_id: string
  name: string
  kind: StimulusKind
  thumbnail_url: string
  media_duration_seconds: number | null
  // Texto do campo de tempo (só imagens); em branco, a troca é manual.
  seconds: string
}

export interface WizardState {
  patient: WizardPatient | null
  title: string
  objective: string
  notes: string
  record: boolean
  items: WizardItem[]
  // "Duplicar para outro paciente": a sessão de origem.
  duplicatedFrom: { id: string; title: string; patientCode: string } | null
}

export const EMPTY_WIZARD: WizardState = {
  patient: null,
  title: '',
  objective: '',
  notes: '',
  record: true,
  items: [],
  duplicatedFrom: null,
}

export function newItem(stimulus: {
  id: string
  name: string
  kind: StimulusKind
  thumbnail_url: string
  duration_seconds: number | null
}): WizardItem {
  return {
    stimulus_id: stimulus.id,
    name: stimulus.name,
    kind: stimulus.kind,
    thumbnail_url: stimulus.thumbnail_url,
    media_duration_seconds: stimulus.kind === 'video' ? stimulus.duration_seconds : null,
    seconds: stimulus.kind === 'image' ? String(DEFAULT_IMAGE_SECONDS) : '',
  }
}

// A sessão copiada, sem o paciente e sem os estímulos arquivados (que não entram em sessões novas).
export function fromSession(session: SessionDetail): { state: WizardState; skipped: number } {
  const items = session.items
    .filter((i) => !i.archived)
    .map((i) => ({
      stimulus_id: i.stimulus_id,
      name: i.name,
      kind: i.kind,
      thumbnail_url: i.thumbnail_url,
      media_duration_seconds: i.media_duration_seconds,
      seconds: i.kind === 'image' && i.duration_seconds !== null ? secondsText(i.duration_seconds) : '',
    }))
  return {
    state: {
      patient: null,
      title: session.title,
      objective: session.objective,
      notes: session.notes ?? '',
      record: session.record,
      items,
      duplicatedFrom: { id: session.id, title: session.title, patientCode: session.patient.code },
    },
    skipped: session.items.length - items.length,
  }
}

// O tempo digitado de cada item; undefined marca o que não vale.
export function itemSeconds(item: WizardItem): number | null | undefined {
  return item.kind === 'image' ? parseSeconds(item.seconds) : null
}

export function toInput(state: WizardState): SessionInput {
  return {
    patient_id: state.patient!.id,
    title: state.title.trim(),
    objective: state.objective.trim(),
    notes: state.notes.trim(),
    record: state.record,
    stimuli: state.items.map((i) => ({ stimulus_id: i.stimulus_id, duration_seconds: itemSeconds(i) ?? null })),
    duplicated_from_id: state.duplicatedFrom?.id ?? null,
  }
}

// Itens no formato dos textos da sequência (sequence.ts).
export function entries(items: WizardItem[]) {
  return items.map((i) => ({ kind: i.kind, duration_seconds: itemSeconds(i) ?? null, media_duration_seconds: i.media_duration_seconds }))
}
