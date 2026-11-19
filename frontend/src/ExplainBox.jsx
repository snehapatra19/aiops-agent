import { useEffect, useState } from 'react'
import { Chip } from './ui.jsx'

export default function ExplainBox({ caseId }) {
  const [out, setOut] = useState(null)
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    setOut(null)
    setQ('')
  }, [caseId])

  const ask = (question) => {
    setBusy(true)
    fetch('/api/explain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ case_id: caseId, question: question || null }) })
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(setOut)
      .catch(() => setOut({ text: 'Could not get an explanation. Check that the backend is running.', source: 'error' }))
      .finally(() => setBusy(false))
  }

  return (
    <div className="mt-5 border-t-2 border-ink pt-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-bold">Explain this incident</span>
        {out && out.source !== 'error' && <Chip tone={out.source === 'gemini' ? 'grn' : 'ink'}>{out.source === 'gemini' ? `Gemini ${out.model || ''}` : 'Built-in'}</Chip>}
      </div>
      {!out && <button onClick={() => ask(null)} disabled={busy} className="border-2 border-ink bg-ink px-3 py-1.5 text-xs font-bold text-sheet disabled:opacity-50">{busy ? 'Thinking…' : 'Explain in plain English'}</button>}
      {out && (
        <>
          <p className="whitespace-pre-line text-xs leading-relaxed">{out.text}</p>
          {out.note && <p className="mt-1 text-[11px] text-mute">{out.note}</p>}
          <div className="mt-3 flex gap-2">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && q.trim() && !busy) ask(q.trim()) }}
              placeholder="Ask about this incident" aria-label="Ask about this incident" className="min-w-0 flex-1 border-2 border-ink bg-sheet px-2 py-1.5 text-xs" />
            <button onClick={() => q.trim() && ask(q.trim())} disabled={busy || !q.trim()} className="border-2 border-ink bg-sheet px-3 py-1.5 text-xs font-bold hover:bg-tyel disabled:opacity-50">{busy ? '…' : 'Ask'}</button>
          </div>
        </>
      )}
    </div>
  )
}