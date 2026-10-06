// "Nova sessão" a partir de um paciente (W06, W08): o assistente da W13 abre com ele escolhido.
export function newSessionPath(patientId: string): string {
  return `/sessoes/nova?paciente=${encodeURIComponent(patientId)}`
}
