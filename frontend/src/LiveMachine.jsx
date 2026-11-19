import { useEffect, useState } from 'react'
import { Sheet, Chip, REASONS, nice } from './ui.jsx'

const STATE = {
  stopped: 'Not monitoring', warming_up: 'Learning what normal looks like', monitoring: 'Watching this machine',
  investigating: 'Investigating an incident', acting_done: 'Fix applied, re-measuring', cooldown: 'Waiting for things to calm down',
}
const EXTRA = { no_allowed_action_for_unattributed_load: 'CPU is busy, but not because of the monitored app, so no safe automatic fix exists.' }
const W = 640, H = 210, P = 28

function Chart({ samples, baseline, events }) {
  if (!samples.length) return <p className="pt-20 text-center text-sm text-mute">No data yet. Press Start monitoring.</p>
  const n = samples.length
  const X = (i) => P + (i / Math.max(n - 1, 1)) * (W - P - 8)
  const Y = (v) => H - P - (v / 100) * (H - 2 * P)
  const line = (k) => samples.map((s, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(s[k]).toFixed(1)}`).join(' ')
  const mark = (node) => {
    const e = events.find(x => x.node === node)
    if (!e) return null
    const i = samples.findIndex(s => s.t >= e.t - 0.6)
    return i < 0 ? null : i
  }
  const di = mark('detect'), ei = mark('execute')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Live CPU and memory of this machine">
      {[0, 25, 50, 75, 100].map(v => <g key={v}><line x1={P} x2={W - 8} y1={Y(v)} y2={Y(v)} stroke="rgb(var(--ink))" opacity="0.12" />
        <text x={P - 4} y={Y(v) + 4} textAnchor="end" className="fill-mute text-[10px]">{v}</text></g>)}
      {baseline && <rect x={P} y={Y(Math.min(100, baseline.median + 6 * baseline.sigma))} width={W - P - 8}
        height={Math.max(2, Y(Math.max(0, baseline.median - 6 * baseline.sigma)) - Y(Math.min(100, baseline.median + 6 * baseline.sigma)))} fill="rgb(var(--tgrn))" opacity="0.14" />}
      <path d={line('mem')} fill="none" stroke="rgb(var(--mute))" strokeWidth="1.5" strokeDasharray="4 4" />
      <path d={line('cpu')} fill="none" stroke="rgb(var(--ink))" strokeWidth="2.5" strokeLinejoin="round" />
      {di !== null && <><line x1={X(di)} x2={X(di)} y1={8} y2={H - P} stroke="rgb(var(--tred))" strokeWidth="2" /><text x={X(di) + 5} y={18} className="fill-tred text-[11px] font-bold">detected</text></>}
      {ei !== null && <><line x1={X(ei)} x2={X(ei)} y1={8} y2={H - P} stroke="rgb(var(--tgrn))" strokeWidth="2" strokeDasharray="3 3" /><text x={X(ei) + 5} y={34} className="fill-tgrn text-[11px] font-bold">fix applied</text></>}
      <circle cx={X(n - 1)} cy={Y(samples[n - 1].cpu)} r="5" fill="rgb(var(--tred))" stroke="rgb(var(--ink))" strokeWidth="2" />
    </svg>
  )
}

export default function LiveMachine() {
  const [s, setS] = useState(null)
  const [hist, setHist] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const poll = () => fetch('/api/live/state').then(r => r.json()).then(d => { if (alive) { setS(d); setErr(null) } })
      .catch(() => alive && setErr('Cannot reach the backend. Start it with: uvicorn api:app --port 8000'))
    const ph = () => fetch('/api/incidents?limit=8').then(r => r.json()).then(d => alive && setHist(d)).catch(() => {})
    poll(); ph()
    const a = setInterval(poll, 1000), b = setInterval(ph, 3000)
    return () => { alive = false; clearInterval(a); clearInterval(b) }
  }, [])

  const post = (u) => fetch(u, { method: 'POST' })
  if (err) return <Sheet><p className="font-semibold text-tred">{err}</p></Sheet>
  if (!s) return <Sheet><p className="text-mute">Loading…</p></Sheet>
  const inc = s.incident || s.last_incident
  const last = s.samples[s.samples.length - 1]
  const running = s.running

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="space-y-4">
        <Sheet title="This machine, live" tone="mint" aside={<Chip tone={s.state === 'investigating' || s.state === 'acting_done' ? 'yel' : 'ink'}>{STATE[s.state] || s.state}</Chip>}>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <button onClick={() => post(running ? '/api/live/stop' : '/api/live/start')}
              className={`border-2 border-ink px-4 py-2 text-sm font-bold ${running ? 'bg-sheet hover:bg-tyel' : 'bg-tgrn text-white'}`}>{running ? 'Stop monitoring' : 'Start monitoring'}</button>
            {last && <div className="flex gap-6 text-sm"><span>CPU <b className="font-display text-xl">{last.cpu}%</b></span><span className="text-mute">Memory <b>{last.mem}%</b></span></div>}
          </div>
          <div className="h-[220px]"><Chart samples={s.samples} baseline={s.baseline} events={inc?.timeline || []} /></div>
          <p className="mt-1 text-xs text-mute">Solid line is real CPU, dashed line is memory. The green band is the learned normal range. Real measurements from this computer, one sample per second.</p>
        </Sheet>

        <Sheet title="How to run the live demo" tone="yel">
          <ol className="list-decimal space-y-1.5 pl-5 text-sm">
            <li>Press <b>Start monitoring</b> and wait about 20 seconds while it learns what normal looks like. Keep the laptop idle.</li>
            <li>Open a <b>second terminal</b> in the project folder and run <code className="bg-rule px-1">python stress.py</code>. It burns CPU on all cores.</li>
            <li>Watch the agent detect the spike, find the cause, pause the stress workers through its one allowed action, and check that CPU really recovered.</li>
            <li>Press <b>Ctrl + C</b> in that terminal when you are done. To demo again, run <code className="bg-rule px-1">python stress.py</code> after the status shows "Watching this machine".</li>
          </ol>
          <p className="mt-2 text-xs text-mute">Safety: the only action it can take is pausing our own stress-app on 127.0.0.1. It never touches any other process.</p>
        </Sheet>

        <Sheet title="Incident history (saved in SQLite)" tone="pink">
          {hist.length === 0 ? <p className="text-sm text-mute">No incidents saved yet.</p> :
            <table className="w-full text-xs"><thead><tr className="border-b-2 border-ink text-left"><th className="py-1">Incident</th><th>Source</th><th>Outcome</th><th>Cause</th><th>Action</th></tr></thead>
              <tbody>{hist.map(h => (
                <tr key={h.id} className="border-b border-rule"><td className="py-1.5 font-semibold">{h.id}</td><td>{h.source}</td>
                  <td><Chip tone={h.status === 'resolved' ? 'grn' : 'yel'}>{h.status}</Chip></td><td>{nice(h.root_cause)}</td><td>{nice(h.action) || 'none'}</td></tr>))}</tbody></table>}
        </Sheet>
      </div>

      <Sheet title="Incident case file" tone="ora" className="lg:self-start" aside={inc && <span className="text-xs font-semibold">{inc.incident_id}</span>}>
        {!inc && <p className="text-sm text-mute">No incident yet. When the agent detects one, its steps appear here.</p>}
        {inc && <>
          {inc.final_status && <div className={`mb-4 inline-block border-4 border-ink px-4 py-2 font-display text-lg font-extrabold shadow-[4px_4px_0_0_rgb(var(--ink))] ${inc.final_status === 'resolved' ? 'bg-tgrn text-white' : 'bg-tyel'}`}>
            {inc.final_status === 'resolved' ? 'Fixed by agent' : 'Sent to a human'}</div>}
          <ol className="relative ml-2 space-y-3 border-l-2 border-ink pl-5">
            {inc.timeline.map((t, k) => (
              <li key={k} className="relative"><span className="absolute -left-[29px] top-1 h-3.5 w-3.5 border-2 border-ink bg-ink" />
                <div className="text-sm font-bold capitalize">{t.node}</div><div className="break-words text-xs text-mute">{t.msg}</div></li>))}
          </ol>
          {inc.escalation_reason && <div className="mt-4 border-2 border-ink bg-tyel p-3 text-xs"><b>Why a human:</b> {REASONS[inc.escalation_reason] || EXTRA[inc.escalation_reason] || inc.escalation_reason}</div>}
          {inc.root_cause && <div className="mt-4 border-t-2 border-ink pt-3 text-xs"><div className="mb-1 text-sm font-bold">Cause ranking</div>
            {inc.root_cause.ranked.map(([c, p]) => <div key={c} className="flex justify-between"><span>{nice(c)}</span><span>{(p * 100).toFixed(0)}%</span></div>)}</div>}
        </>}
      </Sheet>
    </div>
  )
}