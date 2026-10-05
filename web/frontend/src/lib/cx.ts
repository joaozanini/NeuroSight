// Junta classes CSS ignorando valores vazios: cx(styles.a, cond && styles.b).
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
