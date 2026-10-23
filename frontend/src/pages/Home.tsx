import { useTranslation } from 'react-i18next'

export function Home() {
  const { t } = useTranslation()
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-900">{t('app.name')}</h1>
      <p className="mt-1 text-slate-700">{t('app.tagline')}</p>
      <p className="mt-6 text-slate-800">{t('home.shellReady')}</p>
    </main>
  )
}
