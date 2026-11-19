import { useEffect, useState } from 'react'
import { Chip, REASONS, nice } from './ui.jsx'

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
const table = (head, rows) => `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows
  .map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`

export function buildHtml(d) {
  const R = d.report, rc = R.root_cause, B = d.baseline
  const reason = R.escalation_reason ? REASONS[R.escalation_reason] || R.escalation_reason : ''
  const parts = [
    `<h1>Incident report ${esc(R.incident_id || d.case_id)}</h1>`,
    `<p class="note">SYNTHETIC case ${esc(d.case_id)} (${esc(nice(d.scenario))}). Fixes are simulated. Generated ${esc(new Date().toLocaleString())} by the AIOps agent (${esc(d.engine)}).</p>`,
    `<h2>Outcome</h2><p class="big">${esc(nice(R.final_status))}</p>${reason ? `<p>${esc(reason)}</p>` : ''}`,
    `<h2>Symptoms detected</h2>` + (R.symptoms.length ? table(['Service', 'Metric', 'Onset sample', 'Detected at sample', 'Peak z-score', 'Peak value'],
      R.symptoms.map((s) => [s.service, s.metric, s.onset_idx, s.detect_idx, s.peak_z, s.peak_value])) : '<p>No sustained anomaly.</p>'),
    `<h2>Alert correlation</h2><p>${d.alerts.length} raw alerts were grouped into ${d.n_groups} groups; ${R.correlated_alerts.length} alerts belong to this incident.</p>`,
  ]
  if (rc) {
    parts.push(`<h2>Root cause analysis</h2><p>Top cause: <b>${esc(nice(rc.top))}</b> at <b>${esc(rc.root_service)}</b> (confidence ${(rc.confidence * 100).toFixed(0)}%, ${rc.uncertain ? 'not confident' : 'confident'}).</p>`,
      table(['Candidate cause', 'Relative support'], rc.ranked.map(([c, p]) => [nice(c), (p * 100).toFixed(1) + '%'])),
      `<h3>Evidence</h3><ul>${rc.evidence.map((e) => `<li>${esc(e.replace(/^\+[\d.]+: /, ''))}</li>`).join('')}</ul>`,
      rc.missing.length ? `<p>Missing information: ${esc(rc.missing.join(', '))}</p>` : '',
      `<p>Recommended next step: ${esc(rc.next_step)}</p>`)
  }
  if (R.action) {
    parts.push(`<h2>Action and safety policy</h2><p>${esc(nice(R.action.action))} on ${esc(R.action.target)}. Policy: ${esc(R.policy?.reason)} (risk ${esc(R.policy?.risk)}${R.policy?.requires_approval ? ', needs human approval' : ''}).</p>`)
    if (R.execution) parts.push(`<p>${esc(R.execution.detail)}</p>`)
  }
  if (R.verification) {
    parts.push(`<h2>Verification after the fix</h2><p>Overall: <b>${esc(R.verification.overall)}</b></p>`,
      table(['Service', 'Metric', 'State', 'Share of problem remaining'], R.verification.series.map((s) => [s.service, s.metric, s.state, s.ratio === null ? 'n/a' : Math.round(Math.max(0, s.ratio) * 100) + '%'])))
  }
  parts.push(`<h2>Timeline</h2>` + table(['Step', 'Detail'], R.timeline.map((t) => [t.node, t.msg])),
    `<h2>Comparison with a rule-based baseline</h2><p>Baseline verdict: ${esc(nice(B.status))}${B.cause ? `, guessed cause ${esc(nice(B.cause))}` : ''}${B.status === 'resolved' ? (B.actually_effective ? ' (its fix really worked)' : ' (but the problem was still there)') : ''}.</p>`,
    `<h2>Evaluation labels (synthetic ground truth)</h2><p>True cause ${esc(nice(d.truth.root_cause))} at ${esc(d.truth.root_service)}; expected outcome ${esc(nice(d.truth.expected_final))}.</p>`)
  return `<!doctype html><html><head><meta charset="utf-8"><title>Incident report ${esc(d.case_id)}</title><style>
body{font-family:Arial,Helvetica,sans-serif;max-width:820px;margin:32px auto;padding:0 20px;color:#111;line-height:1.45}
h1{font-size:24px;border-bottom:3px solid #111;padding-bottom:8px}h2{font-size:16px;margin-top:24px;border-bottom:1px solid #999;padding-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}th,td{border:1px solid #888;padding:4px 8px;text-align:left}th{background:#eee}
.note{color:#555;font-size:12px}.big{font-size:22px;font-weight:bold;text-transform:capitalize}@media print{body{margin:0}}
</style></head><body>${parts.join('\n')}</body></html>`
}

const save = (name, type, text) => {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = name
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}

export default function ReportActions({ data }) {
  const [rating, setRating] = useState(null)
  const [comment, setComment] = useState('')
  const [sum, setSum] = useState(null)
  const [state, setState] = useState('idle')

  useEffect(() => { setRating(null); setComment(''); setState('idle') }, [data.case_id])

  const send = () => {
    setState('sending')
    fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: data.case_id, status: data.report.final_status, rating, comment }) })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((s) => { setSum(s); setState('sent') })
      .catch(() => setState('error'))
  }
  const base = `incident-${data.case_id}`
  const btn = 'border-2 border-ink bg-sheet px-3 py-1.5 text-xs font-bold hover:bg-tyel'

  return (
    <div className="mt-5 border-t-2 border-ink pt-3">
      <div className="mb-2 text-sm font-bold">Report and feedback</div>
      <div className="flex flex-wrap gap-2">
        <button className={btn} onClick={() => save(`${base}.json`, 'application/json', JSON.stringify({ synthetic: true, ...data }, null, 2))}>Download report (JSON)</button>
        <button className={btn} onClick={() => save(`${base}.html`, 'text/html', buildHtml(data))}>Download report (HTML)</button>
        <button className={btn} onClick={() => { const w = window.open('', '_blank'); if (w) { w.document.write(buildHtml(data)); w.document.close(); w.focus(); w.print() } }}>Print or save as PDF</button>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 text-xs font-bold">Was the agent's decision right?</div>
        {state === 'sent' ? (
          <p className="text-xs">Thanks, your feedback is saved. {sum && <span className="text-mute">So far {sum.up} of {sum.total} ratings said the agent was right.</span>}</p>
        ) : (
          <>
            <div className="flex gap-2">
              <button aria-pressed={rating === 'up'} onClick={() => setRating('up')} className={`border-2 border-ink px-3 py-1.5 text-xs font-bold ${rating === 'up' ? 'bg-tgrn text-white' : 'bg-sheet hover:bg-tyel'}`}>Yes, correct</button>
              <button aria-pressed={rating === 'down'} onClick={() => setRating('down')} className={`border-2 border-ink px-3 py-1.5 text-xs font-bold ${rating === 'down' ? 'bg-tred text-white' : 'bg-sheet hover:bg-tyel'}`}>No, wrong</button>
            </div>
            {rating && (
              <div className="mt-2 flex gap-2">
                <input value={comment} onChange={(e) => setComment(e.target.value)} maxLength={300} placeholder="Add a comment (optional)" aria-label="Feedback comment"
                  className="min-w-0 flex-1 border-2 border-ink bg-sheet px-2 py-1.5 text-xs" />
                <button disabled={state === 'sending'} onClick={send} className={`${btn} disabled:opacity-50`}>{state === 'sending' ? 'Saving…' : 'Send'}</button>
              </div>
            )}
            {state === 'error' && <p className="mt-1 text-xs font-semibold text-tred">Could not save. Is the backend running?</p>}
          </>
        )}
      </div>
    </div>
  )
}