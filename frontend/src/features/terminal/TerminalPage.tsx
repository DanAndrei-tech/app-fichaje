import { useParams } from 'react-router'

// Pantalla provisional del terminal de fichaje.
export function TerminalPage() {
  const { companySlug } = useParams()

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 bg-slate-900 p-4 text-white">
      <h1 className="text-3xl font-bold">Terminal de fichaje</h1>
      <p className="text-lg text-slate-300">Empresa: {companySlug}</p>
    </main>
  )
}
