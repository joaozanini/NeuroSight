import { useEffect } from 'react'

// Título da aba: "Pacientes · NeuroSight".
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} · NeuroSight` : 'NeuroSight'
  }, [title])
}
