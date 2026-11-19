import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import Topology from './Topology.jsx'
import Trace from './Trace.jsx'
import ExplainBox from './ExplainBox.jsx'
import ReportActions from './ReportActions.jsx'
import { Sheet, Chip, SCENARIOS, REASONS, nice, short } from './ui.jsx'

const METRIC = { cpu: 'CPU', mem: 'memory', latency_ms: 'latency', error_rate: 'errors', pool_util: 'pool' }
const UNIT = { cpu: '%', mem: '%', latency_ms: ' ms', error_rate: '%', pool_util: '%' }
const SERVICES = ['frontend', 'api-gateway', 'payment-service', 'order-service', 'auth-service', 'cache-redis', 'db-primary']
const TICK_MS = 85

function makeSchedule(d) {
  const R = d.report, pre = d.series[0]?.pre.length || 40
  const dets = R.symptoms.map(s => s.detect_idx)
  let t = dets.length ? Math.min(...dets) : pre, postStart = null
  const appear = []
  R.timeline.forEach(step => {
    appear.push(t)
    if (step.node === 'execute' && d.series[0]?.post) { postStart = t + 2; t += 2 + 12 + 3 } else t += 8
  })
  return { appear, postStart, done: appear[appear.length - 1] + 3 }
}

function stepText(node, d) {
  const R = d.report
  switch (node) {
    case 'detect': return R.symptoms.length ? `Spotted ${R.symptoms.length} abnormal signal${R.symptoms.length > 1 ? 's' : ''} that stay high` : 'Nothing stays abnormal, so there is no incident'
    case 'correlate': return `Grouped ${d.alerts.length} alerts into ${d.n_groups} groups; ${R.correlated_alerts.length} belong to this incident`
    case 'evidence': return 'Pulled the related logs, traces and deploy events'
    case 'rca': { const c = R.root_cause; return `Most likely cause: ${nice(c.top)} at ${c.root_service}`  }
    case 'plan': return R.action ? `Proposed ${nice(R.action.action)} on ${R.action.target}` : 'Not confident enough to act on its own'
    case 'execute': return R.execution ? 'Ran the fix in the simulator' : 'The fix could not run'
    case 'verify': return `Re-measured after the fix: ${R.verification?.overall}`
    case 'escalate': return 'Handed over to the on-call engineer'
    default: return 'Incident report written'
  }
}

function Stamp({ status }) {
  const m = { resolved: ['Fixed by agent', 'bg-tgrn text-white'], escalated: ['Sent to a human', 'bg-tyel text-ink'], no_incident: ['All clear', 'bg-sheet text-ink'] }[status]
  return (
    <motion.div initial={{ scale: 2.2, rotate: -14, opacity: 0 }} animate={{ scale: 1, rotate: -3, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 420, damping: 16 }}
      className={`border-4 border-ink px-5 py-2.5 font-display text-xl font-extrabold leading-none shadow-[5px_5px_0_0_rgb(var(--ink))] ${m[1]}`}>
      {m[0]}
    </motion.div>
  )
}

const STRIPE = ['rgb(var(--tyel))', 'rgb(var(--mint))', 'rgb(var(--pink))', 'rgb(var(--tora))']
const TALLY_BG = ['bg-tyel', 'bg-mint', 'bg-tora', 'bg-pink', 'bg-sheet']

export default function Live({ onPulse }) {
  const [cases, setCases] = useState([])
  const [req, setReq] = useState(null)
  const [scn, setScn] = useState('db_pool_exhaustion')
  const [data, setData] = useState(null)
  const [tick, setTick] = useState(0)
  const [truth, setTruth] = useState(false)
  const [sel, setSel] = useState(0)
  const [auto, setAuto] = useState(false)
  const [tally, setTally] = useState({ n: 0, fixed: 0, human: 0, clear: 0, wrong: 0, match: 0 })
  const [err, setErr] = useState(null)
  const ptr = useRef({}), counted = useRef(-1), autoIdx = useRef(0)

  const inject = (name, list = cases) => {
    const ids = list.filter(c => c.scenario === name).map(c => c.case_id)
    if (!ids.length) return
    const k = ptr.current[name] || 0
    ptr.current[name] = k + 1
    setScn(name)
    setReq(r => ({ id: ids[k % ids.length], n: (r?.n || 0) + 1 }))
  }

  useEffect(() => {
    fetch('/api/cases').then(r => r.json()).then(cs => { setCases(cs); inject('db_pool_exhaustion', cs) })
      .catch(() => setErr('Cannot reach the backend. Start it with: uvicorn api:app --port 8000'))
  }, [])

  useEffect(() => {
    if (!req) return
    let alive = true
    setData(null); setTick(0); setTruth(false); setSel(0)
    fetch(`/api/run/${req.id}`).then(r => r.json()).then(d => { if (alive) setData(d) })
    return () => { alive = false }
  }, [req])

  const sch = useMemo(() => (data ? makeSchedule(data) : null), [data])

  useEffect(() => {
    if (!sch) return
    const h = setInterval(() => setTick(t => (t < sch.done + 80 ? t + 1 : t)), TICK_MS)
    return () => clearInterval(h)
  }, [sch])

  const done = !!sch && tick >= sch.done
  useEffect(() => {
    if (!done || !data || counted.current === req.n) return
    counted.current = req.n
    const R = data.report, bad = data.baseline.status === 'resolved' && !data.baseline.actually_effective
    setTally(t => ({ n: t.n + 1, fixed: t.fixed + (R.final_status === 'resolved'), human: t.human + (R.final_status === 'escalated'),
      clear: t.clear + (R.final_status === 'no_incident'), wrong: t.wrong + bad, match: t.match + (R.final_status === data.truth.expected_final) }))
  }, [done])

  useEffect(() => {
    if (!auto || !done) return
    const h = setTimeout(() => { autoIdx.current = (autoIdx.current + 1) % SCENARIOS.length; inject(SCENARIOS[autoIdx.current][0]) }, 4500)
    return () => clearTimeout(h)
  }, [auto, done])

  const R = data?.report, tl = R?.timeline || []
  const visible = sch ? sch.appear.filter(a => tick >= a).length : 0

  useEffect(() => {
    if (onPulse) onPulse({ seen: tl.slice(0, visible).map(t => t.node), all: tl.map(t => t.node), done, status: R?.final_status || null })
  }, [visible, done, data])

  if (err) return <Sheet><p className="font-semibold text-tred">{err}</p></Sheet>

  const idx = (n) => tl.findIndex(t => t.node === n)
  const seen = (n) => !!data && idx(n) >= 0 && visible > idx(n)
  const S = data?.series?.[sel]
  const shown = S ? Math.min(S.pre.length, tick + 1) : 0
  const postShown = S?.post && sch?.postStart != null ? Math.max(0, Math.min(S.post.length, tick - sch.postStart + 1)) : 0
  const cur = shown - 1
  const simSec = Math.max(0, cur) * 15 + postShown * 15
  const clock = `${String(Math.floor(simSec / 60)).padStart(2, '0')}:${String(simSec % 60).padStart(2, '0')}`

  const state = {}, vitals = {}
  SERVICES.forEach(s => {
    const an = R ? R.symptoms.filter(x => x.service === s) : []
    const recovered = seen('verify') && R.verification?.overall === 'resolved'
    state[s] = !an.length || recovered ? 'green' : cur >= Math.min(...an.map(a => a.detect_idx)) ? 'red' : cur >= Math.min(...an.map(a => a.onset_idx)) ? 'yellow' : 'green'
    const ss = data?.series.find(x => x.service === s)
    if (ss && cur >= 0) {
      const v = ss.post && sch?.postStart != null && tick >= sch.postStart ? ss.post[Math.min(ss.post.length - 1, Math.max(0, tick - sch.postStart))] : ss.pre[Math.min(cur, ss.pre.length - 1)]
      vitals[s] = `${METRIC[ss.metric]} ${Number(v).toFixed(ss.metric === 'error_rate' ? 1 : 0)}${UNIT[ss.metric]}`
    }
  })
  const root = seen('rca') ? R.root_cause?.root_service : null
  const rc = R?.root_cause
  const B = data?.baseline

  return (
    <div className="space-y-4">
      <div className="sheet grid grid-cols-2 divide-x-2 divide-ink md:grid-cols-5">
        {[['Incidents handled', tally.n], ['Fixed by the agent', tally.fixed], ['Sent to a human', tally.human],
          ['Baseline would have wrongly closed', tally.wrong], ['Agent matched expected outcome', `${tally.match} of ${tally.n}`]].map(([l, v], i) => (
          <div key={l} className={`px-4 py-3 ${TALLY_BG[i]}`}>
            <div className="font-display text-3xl font-extrabold leading-none">{v}</div>
            <div className="mt-1.5 text-xs font-semibold">{l}</div>
          </div>))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)_400px]">
        <Sheet title="Inject a fault" tone="yel" className="lg:self-start">
          <div className="space-y-2">
            {SCENARIOS.map(([k, t, sub], n) => (
              <button key={k} onClick={() => inject(k)} aria-pressed={scn === k} style={{ borderLeftColor: STRIPE[n % 4], borderLeftWidth: 10 }}
                className={`w-full border-2 border-ink px-3 py-2 text-left transition-colors ${scn === k ? 'bg-ink text-sheet' : 'bg-sheet hover:bg-tyel'}`}>
                <div className="text-sm font-bold leading-tight">{t}</div>
                <div className={`text-xs ${scn === k ? 'text-rule' : 'text-mute'}`}>{sub}</div>
              </button>))}
          </div>
          <button onClick={() => setAuto(!auto)} aria-pressed={auto}
            className={`mt-3 w-full border-2 border-ink px-3 py-2.5 text-sm font-bold ${auto ? 'bg-tgrn text-white' : 'bg-sheet hover:bg-tyel'}`}>
            {auto ? 'Autopilot is on. Click to stop' : 'Start autopilot (cycles all faults)'}
          </button>
        </Sheet>

        <div className="min-w-0 space-y-4">
          <Sheet title="Service map" tone="mint" aside={<span className="text-xs font-semibold">Simulated clock {clock}</span>}>
            <div className="h-[290px]"><Topology state={state} vitals={vitals} root={root} truth={truth && data ? data.truth.root_service : null} /></div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs font-medium">
              {[['bg-tgrn', 'healthy'], ['bg-tyel', 'degrading'], ['bg-tred', 'failing']].map(([c, l]) => <span key={l} className="flex items-center gap-1.5"><span className={`inline-block h-3 w-3 border-2 border-ink ${c}`} />{l}</span>)}
              {truth && <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-4 border-2 border-dashed border-ink" />true root cause</span>}
            </div>
          </Sheet>
          <Sheet tone="pink" title={S ? `Live telemetry: ${short(S.service)} ${METRIC[S.metric]}` : 'Live telemetry'}
            aside={data?.series?.length > 1 && <div className="flex flex-wrap justify-end gap-1">{data.series.map((x, k) => (
              <button key={k} onClick={() => setSel(k)} className={`border-2 border-ink px-2 py-0.5 text-[11px] font-semibold ${sel === k ? 'bg-ink text-sheet' : 'bg-sheet hover:bg-tyel'}`}>{short(x.service)} {METRIC[x.metric]}</button>))}</div>}>
            <div className="h-[200px]">
              {!data && <p className="pt-16 text-center text-sm text-mute">Running the agent…</p>}
              {data && !S && <p className="pt-16 text-center text-sm text-mute">No metric stays abnormal in this scenario. Short blips raise alerts, but the agent ignores them.</p>}
              {S && <Trace s={S} shown={shown} postShown={postShown} />}
            </div>
            <p className="mt-1 text-xs text-mute">One sample every 15 simulated seconds, streamed in real time. Green line is the measurement after the fix.</p>
          </Sheet>
        </div>

        <Sheet title="Case file" tone="ora" className="lg:self-start" aside={data && <span className="text-xs font-semibold">{data.case_id}</span>}>
          <div className="mb-4 flex h-[72px] items-center justify-center border-2 border-dashed border-rule">
            {done && R ? <Stamp key={req.n} status={R.final_status} /> : <span className="text-xs font-semibold text-mute">Verdict appears here</span>}
          </div>
          {!data && <p className="text-sm text-mute">Running the agent…</p>}
          <ol className="relative ml-2 space-y-3 border-l-2 border-ink pl-5">
            {tl.slice(0, visible).map((t, k) => (
              <li key={k} className="relative">
                <span className={`absolute -left-[29px] top-1 h-3.5 w-3.5 border-2 border-ink ${k === visible - 1 && !done ? 'blink bg-tyel' : t.node === 'escalate' ? 'bg-tyel' : 'bg-ink'}`} />
                <div className="text-sm font-bold leading-snug">{stepText(t.node, data)}</div>
                <div className="text-xs text-mute">{t.node === 'plan' && R.policy ? R.policy.reason : t.msg}</div>
              </li>))}
          </ol>

          {rc && seen('rca') && (
            <div className="mt-5 border-t-2 border-ink pt-3">
              <div className="mb-2 flex items-center justify-between"><span className="text-sm font-bold">Cause ranking</span>
                <Chip tone={rc.uncertain ? 'yel' : 'grn'}>{rc.uncertain ? 'Not confident' : 'Confident'}</Chip></div>
              {rc.ranked.slice(0, 3).map(([c, p], k) => (
                <div key={c} className="mb-1.5">
                  <div className="flex justify-between text-xs"><span className={k === 0 ? 'font-bold' : 'text-mute'}>{nice(c)}</span><span>{(p * 100).toFixed(0)}%</span></div>
                  <div className="h-2.5 border-2 border-ink bg-sheet"><motion.div initial={{ width: 0 }} animate={{ width: `${p * 100}%` }} transition={{ duration: 0.6 }} className={k === 0 ? 'h-full bg-ink' : 'hatch h-full'} /></div>
                </div>))}
              <ul className="mt-2 list-disc pl-4 text-xs text-mute">{rc.evidence.slice(0, 4).map((e, k) => <li key={k}>{e.replace(/^\+[\d.]+: /, '')}</li>)}</ul>
              {rc.missing.length > 0 && <p className="mt-2 text-xs font-semibold">Missing: {rc.missing.join(', ')}</p>}
            </div>)}

          {done && R.escalation_reason && (
            <div className="mt-4 border-2 border-ink bg-tyel p-3">
              <div className="text-sm font-bold">Paging the on-call engineer</div>
              <div className="text-xs">{REASONS[R.escalation_reason]}</div>
              {rc && <div className="mt-1 text-xs"><b>Next step:</b> {rc.next_step}</div>}
            </div>)}

          {done && data && <ExplainBox caseId={data.case_id} />}
          {done && data && <ReportActions data={data} />}
        </Sheet>
      </div>

      {done && R && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Sheet title="Safety checks before and after the fix" tone="mint">
            {R.action ? <>
              <div className="mb-2 text-sm"><b>{nice(R.action.action)}</b> on <b>{R.action.target}</b></div>
              <div className="mb-3 flex flex-wrap gap-1.5">
                <Chip tone={R.policy?.allowed ? 'grn' : 'red'}>{R.policy?.allowed ? 'On the approved list' : 'Blocked by policy'}</Chip>
                <Chip tone={R.policy?.risk === 'high' ? 'red' : 'ink'}>Risk: {R.policy?.risk}</Chip>
                {R.policy?.requires_approval && <Chip tone="yel">Needs a person to approve</Chip>}
              </div></> : <p className="mb-3 text-sm">No action was taken because the cause was uncertain.</p>}
            {R.execution && <p className="mb-3 text-xs text-mute">The simulator said the command succeeded. That alone does not count as fixed.</p>}
            {R.verification && <div className="space-y-2">
              <div className="text-sm font-bold">Metrics after the fix: {R.verification.overall}</div>
              {R.verification.series.map((x, k) => (
                <div key={k}><div className="flex justify-between text-xs"><span>{short(x.service)} {METRIC[x.metric]}</span><span>{x.ratio === null ? 'no data' : `${Math.round(Math.max(0, x.ratio) * 100)}% of the problem remains`}</span></div>
                  <div className="h-2.5 border-2 border-ink bg-sheet"><div className={x.state === 'resolved' ? 'h-full bg-tgrn' : x.state === 'unresolved' ? 'h-full bg-tred' : 'h-full bg-tyel'} style={{ width: `${Math.min(100, Math.max(0, (x.ratio || 0) * 100))}%` }} /></div></div>))}
            </div>}
          </Sheet>

          <Sheet title="Agent versus a simple rule-based system" tone="pink">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="border-2 border-ink p-3">
                <div className="mb-1 text-xs font-bold text-mute">Our agent says</div>
                <div className="font-bold">{R.final_status === 'resolved' ? 'Fixed' : R.final_status === 'escalated' ? 'Needs a human' : 'No incident'}</div>
                {R.final_status === 'resolved' && <div className={`mt-2 text-xs font-semibold ${R.execution?.post_mode === 'fixed' ? 'text-tgrn' : 'text-tred'}`}>{R.execution?.post_mode === 'fixed' ? 'Reality: really fixed' : 'Reality: not fixed'}</div>}
              </div>
              <div className={`border-2 border-ink p-3 ${B.status === 'resolved' && !B.actually_effective ? 'bg-tred/10' : ''}`}>
                <div className="mb-1 text-xs font-bold text-mute">Rule-based baseline says</div>
                <div className="font-bold">{B.status === 'resolved' ? 'Fixed' : B.status === 'escalated' ? 'Needs a human' : 'No incident'}</div>
                {B.status === 'resolved' && <div className={`mt-2 text-xs font-semibold ${B.actually_effective ? 'text-tgrn' : 'text-tred'}`}>{B.actually_effective ? 'Reality: really fixed' : 'Reality: still broken'}</div>}
              </div>
            </div>
            <p className="mt-3 text-xs text-mute">The baseline never re-checks the metrics, so it declares success whenever its command runs.{B.cause && ` It guessed: ${nice(B.cause)}.`}</p>
          </Sheet>

          <Sheet title="Alerts and ground truth" tone="yel" aside={<button onClick={() => setTruth(!truth)} className="border-2 border-ink bg-sheet px-2 py-0.5 text-xs font-bold hover:bg-tyel">{truth ? 'Hide answer' : 'Reveal answer'}</button>}>
            <div className="mb-2 text-sm"><b>{data.alerts.length}</b> raw alerts became <b>{data.n_groups}</b> group{data.n_groups === 1 ? '' : 's'}.</div>
            <div className="mb-3 max-h-24 space-y-1 overflow-y-auto text-xs">
              {data.alerts.slice(0, 14).map(a => (
                <div key={a.id} className="flex justify-between border-b border-rule pb-0.5"><span>{short(a.service)} {nice(a.type)}</span>
                  <span className={`px-1.5 font-semibold ${a.in_incident ? 'bg-ink text-sheet' : 'bg-rule'}`}>group {a.group}</span></div>))}
            </div>
            {truth ? <div className="space-y-1 border-2 border-ink p-2 text-xs">
              <div>True cause: <b>{nice(data.truth.root_cause)}</b> at <b>{data.truth.root_service}</b> {rc && <Chip tone={rc.top === data.truth.root_cause ? 'grn' : 'red'}>{rc.top === data.truth.root_cause ? 'agent was right' : 'agent was wrong'}</Chip>}</div>
              <div>Expected outcome: <b>{nice(data.truth.expected_final)}</b> <Chip tone={R.final_status === data.truth.expected_final ? 'grn' : 'red'}>{R.final_status === data.truth.expected_final ? 'matched' : 'differs'}</Chip></div>
            </div> : <p className="text-xs text-mute">The agent never sees the answer key. Reveal it to check the agent.</p>}
          </Sheet>
        </div>)}
      <p className="text-xs text-mute">Every case is synthetic. The pipeline runs for real on each click; the telemetry is replayed from pre-generated data at one sample per 15 simulated seconds.</p>
    </div>
  )
}