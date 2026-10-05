import LinkButton from '../components/Button/LinkButton'
import PageHeader from '../components/PageHeader/PageHeader'
import { usePageTitle } from '../lib/usePageTitle'

export default function NotFoundPage() {
  usePageTitle('Página não encontrada')
  return (
    <>
      <PageHeader title="Página não encontrada" subtitle="O endereço não existe ou mudou de lugar." />
      <LinkButton to="/" variant="secondary">
        Voltar para o início
      </LinkButton>
    </>
  )
}
