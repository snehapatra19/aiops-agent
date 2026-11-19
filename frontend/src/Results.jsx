import { useEffect, useState } from 'react'
import { Sheet, Chip, pct, num, nice } from './ui.jsx'

function Pair({ label, a, b, lower, note }) {
  const w = (v) => `${Math.max(0, Math.min(1, v ?? 0)) * 100}%`
  return (
    <div className="border-b-2 border-ink py-3 last:border-b-0">
      <div className="mb-1.5 flex items-baseline justify-between"><span className="text-sm font-bold">{label}</span>{lower && <span className="text-xs text-mute">lower is better</span>}</div>
      <div className="flex items-center gap-3"><span className="w-20 text-xs font-semibold">Agent</span>
        <div className="h-5 flex-1 border-2 border-ink bg-sheet"><div className="h-full bg-ink" style={{ width: w(a) }} /></div><span className="w-14 text-right text-sm font-bold">{pct(a)}</span></div>
      <div className="mt-1.5 flex items-center gap-3"><span className="w-20 text-xs font-semibold text-mute">Baseline</span>
        <div className="h-5 flex-1 border-2 border-ink bg-sheet"><div className="hatch h-full" style={{ width: w(b) }} /></div><span className="w-14 text-right text-sm font-bold text-mute">{pct(b)}</span></div>
      {note && <p className="mt-1 text-xs text-mute">{note}</p>}
    </div>
  )
}

const LABEL = { ours: 'Our detector', ours_2sided: 'Our detector, both directions', static: 'Static threshold', static_2sided: 'Static, both directions' }
const ORDER = ['ours', 'ours_2sided', 'static', 'static_2sided']

function RealTable({ ds }) {
  const have = ORDER.filter(m => ds.results[m])
  const top = Math.max(...have.map(m => ds.results[m].f1))
  return (
    <div className="mb-5 last:mb-0">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2"><span className="text-sm font-bold">{ds.name}</span><span className="text-xs text-mute">{ds.series} series</span></div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="border-b-2 border-ink text-left"><th className="py-1">Method</th><th>Recall</th><th>Precision</th><th>F1</th><th>Alarm load</th></tr></thead>
          <tbody>{have.map(m => { const r = ds.results[m]; return (
            <tr key={m} className={`border-b border-rule ${r.f1 === top ? 'bg-tyel/40 font-bold' : ''}`}>
              <td className="py-1.5">{LABEL[m]}</td><td>{pct(r.window_recall)}</td><td>{pct(r.alarm_precision)}</td><td>{num(r.f1)}</td>
              <td>{r.alarms_per_1000 != null ? `${r.alarms_per_1000} per 1000 samples` : `${r.alarms} alarms`}</td>
            </tr>) })}</tbody>
        </table>
      </div>
    </div>
  )
}

export function RealData({ real, extra }) {
  const n = real?.nab
  const list = [n && { name: 'NAB, AWS CloudWatch servers', series: n.series, results: n.results }, ...Object.values(real?.others?.datasets || {}), ...Object.values(extra?.datasets || {})].filter(Boolean)
  if (!list.length) return null
  return (
    <Sheet title="Real public datasets (detection only)" tone="mint">
      <p className="mb-3 text-xs text-mute">The same untuned thresholds are used on every dataset. Recall is the share of labelled anomalies that got an alarm. Precision is the share of alarms that landed on a real anomaly. The highlighted row has the best F1. A rule that alarms on everything gets high recall, so read recall and alarm load together. None of these datasets has root-cause or fix labels, so they test detection only.</p>
      {list.map(ds => <RealTable key={ds.name} ds={ds} />)}
    </Sheet>
  )
}

const TARGET = { handoff: 'Needs two or more hand-offs', sla_breach: 'Breaches its SLA' }
const SCORER = { rare_template: 'Rare log template', error_keywords: 'Error keywords', severity_level: 'Log severity level', keywords_plus_rare: 'Keywords plus rare template' }

export function MoreData({ extra }) {
  if (!extra) return null
  const t = extra.triage, lg = extra.logs, hw = extra.hardware
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {t && (
        <Sheet title="Incident tickets: which ones need attention" tone="yel" aside={<Chip>UCI incident log</Chip>}>
          <p className="mb-3 text-xs text-mute">{t.incidents.toLocaleString()} real tickets with {t.events.toLocaleString()} update events. A simple model learns from the first {t.train.toLocaleString()} tickets and is tested on the {t.test.toLocaleString()} that came later. AUC is 0.5 for guessing and 1.0 for perfect.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b-2 border-ink text-left"><th className="py-1">Ticket outcome</th><th>Model AUC</th><th>Priority only</th><th>Top 20% flagged that really are</th></tr></thead>
              <tbody>{Object.entries(t.results).map(([k, r]) => (
                <tr key={k} className="border-b border-rule"><td className="py-1.5 font-semibold">{TARGET[k]}</td><td className="font-bold">{num(r.model.auc)}</td><td className="text-mute">{num(r.priority_only.auc)}</td>
                  <td>{pct(r.model.precision_at_top)} <span className="text-mute">(overall {pct(r.model.base_rate)})</span></td></tr>))}</tbody>
            </table>
          </div>
          <div className="mt-3 text-xs font-bold">Median time to resolve, by priority</div>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">{Object.entries(t.resolution).map(([p, v]) => <div key={p} className="flex justify-between border-b border-rule"><span>{p}</span><span className="font-semibold">{v.median_hours} h</span></div>)}</div>
        </Sheet>
      )}
      {lg && (
        <Sheet title="Log evidence: spotting the alert lines" tone="pink" aside={<Chip>Loghub</Chip>}>
          {lg.bgl && <>
            <p className="mb-3 text-xs text-mute">BGL supercomputer logs. Rules and rarity are learned on the first half and scored on the other {lg.bgl.lines_tested.toLocaleString()} lines, of which {lg.bgl.alert_lines} are labelled alerts. AUC is 0.5 for guessing.</p>
            <table className="w-full text-xs">
              <thead><tr className="border-b-2 border-ink text-left"><th className="py-1">How a line is scored</th><th>AUC</th></tr></thead>
              <tbody>{Object.entries(lg.bgl.results).map(([k, r]) => (
                <tr key={k} className="border-b border-rule"><td className="py-1.5">{SCORER[k]}</td><td className="font-bold">{num(r.auc)}</td></tr>))}</tbody>
            </table>
          </>}
          <div className="mt-3 text-xs font-bold">All {lg.systems.length} log systems, 2,000 lines each</div>
          <div className="mt-1 max-h-44 overflow-y-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b-2 border-ink text-left"><th className="py-1">System</th><th>Templates</th><th>Error-like lines</th></tr></thead>
              <tbody>{lg.systems.map(s => <tr key={s.system} className="border-b border-rule"><td className="py-1">{s.system}</td><td>{s.templates}</td><td>{s.error_like_pct}%</td></tr>)}</tbody>
            </table>
          </div>
        </Sheet>
      )}
      {hw && (
        <div className="lg:col-span-2">
          <Sheet title="Hardware layout used for alert grouping" tone="mint" aside={<Chip>Alibaba SSD data</Chip>}>
            <p className="text-sm">{hw.disks.toLocaleString()} disks in {hw.nodes.toLocaleString()} servers across {hw.racks.toLocaleString()} racks, with up to {hw.max_disks_per_node} disks in one server ({hw.mean_disks_per_node} on average). It tells the agent which alerts share a server or rack. This dataset has no failure labels, so there is no accuracy score for it.</p>
          </Sheet>
        </div>
      )}
    </div>
  )
}

export default function Results() {
  const [d, setD] = useState(null), [cm, setCm] = useState('proposed'), [err, setErr] = useState(null)
  useEffect(() => { fetch('/api/results').then(r => { if (!r.ok) throw new Error(); return r.json() }).then(setD).catch(() => setErr('No results yet. Run: python cli.py experiments')) }, [])
  if (err) return <Sheet><p className="font-semibold">{err}</p></Sheet>
  if (!d) return <Sheet><p className="text-mute">Loading…</p></Sheet>
  const A = d.aggregate, P = A.proposed, B = A.baseline
  const M = d.confusion[cm], rows = M ? Object.keys(M.matrix) : []
  const mx = M ? Math.max(1, ...rows.flatMap(r => Object.values(M.matrix[r]))) : 1
  const rep = d.repeated?.repeated || {}
  const keys = ['detection.f1', 'correlation.pair_f1', 'rca.top1_acc', 'remediation.false_resolution_rate', 'remediation.final_decision_accuracy']
  return (
    <div className="space-y-4">
      <div className="sheet flex flex-wrap items-center gap-3 bg-tyel px-4 py-3 text-sm font-medium">
        <Chip>Synthetic benchmark</Chip>
        <span>{A.n_cases} generated cases (seed {A.seed}, dataset hash {A.dataset_hash}). These scores show the pipeline works on this benchmark. They do not show it works on real production systems.</span>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Sheet title="Same 120 cases, two systems">
          <Pair label="Spots real incidents (F1)" a={P.detection.f1} b={B.detection.f1} />
          <Pair label="Groups related alerts together (pair F1)" a={P.correlation.pair_f1} b={B.correlation.pair_f1} />
          <Pair label="Finds the right root cause (top 1)" a={P.rca.top1_acc} b={B.rca.top1_acc} />
          <Pair label="Declares success when it was not fixed" a={P.remediation.false_resolution_rate} b={B.remediation.false_resolution_rate} lower
            note={`Agent ${P.remediation.false_resolution_claims} of ${P.remediation.claimed_resolved}. Baseline ${B.remediation.false_resolution_claims} of ${B.remediation.claimed_resolved}. Several scenarios are designed to test exactly this, so part of the gap is by design.`} />
          <Pair label="Makes the right final decision" a={P.remediation.final_decision_accuracy} b={B.remediation.final_decision_accuracy} />
        </Sheet>
        <div className="space-y-4">
          <Sheet title="Where the root-cause guesses went" aside={<div className="flex gap-1">{['proposed', 'baseline'].map(k => (
            <button key={k} onClick={() => setCm(k)} className={`border-2 border-ink px-2 py-0.5 text-xs font-bold ${cm === k ? 'bg-ink text-sheet' : 'bg-sheet hover:bg-tyel'}`}>{k === 'proposed' ? 'Agent' : 'Baseline'}</button>))}</div>}>
            {M && <div className="overflow-x-auto"><table className="w-full border-collapse text-center text-xs"><thead><tr><th className="p-1 text-left font-semibold text-mute">true cause / guess</th>
              {M.labels.map(l => <th key={l} className="p-1 font-semibold">{nice(l)}</th>)}</tr></thead>
              <tbody>{rows.map(r => <tr key={r}><td className="p-1 text-left font-semibold">{nice(r)}</td>
                {M.labels.map(l => { const v = M.matrix[r][l]; return <td key={l} className="border border-rule p-0"><div className="py-1.5 font-bold" style={{ background: `rgb(var(--ink) / ${v / mx * 0.9})`, color: v / mx > 0.45 ? 'rgb(var(--sheet))' : 'rgb(var(--ink))' }}>{v}</div></td> })}</tr>)}</tbody></table></div>}
          </Sheet>
          <Sheet title="Does it hold across different random seeds?">
            <table className="w-full text-xs"><thead><tr className="border-b-2 border-ink text-left"><th className="py-1">Metric</th><th>Agent</th><th>Baseline</th></tr></thead>
              <tbody>{keys.map(k => { const p = rep['proposed.' + k], b = rep['baseline.' + k]; return (
                <tr key={k} className="border-b border-rule"><td className="py-1.5 font-semibold">{nice(k.split('.')[1])}</td>
                  <td>{p ? `${num(p.mean)} ± ${num(p.std)}` : 'n/a'}</td><td className="text-mute">{b ? `${num(b.mean)} ± ${num(b.std)}` : 'n/a'}</td></tr>) })}</tbody></table>
            <p className="mt-2 text-xs text-mute">Mean ± standard deviation over 5 generator seeds. This is synthetic-data variability, not a real-world confidence interval.</p>
          </Sheet>
        </div>
      </div>
      <RealData real={d.real} extra={d.extra} />
      <MoreData extra={d.extra} />
      <Sheet title="Safety and honesty notes">
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          <li>Policy test: {A.safety.prevented_or_escalated} of {A.safety.unsafe_proposals} unsafe or high-risk proposals were blocked or escalated, and {A.safety.valid_allowed} of {A.safety.valid_proposals} valid ones were allowed. These are hand-written test cases, not an adversarial study.</li>
          <li>Time to resolution is simulated: mean {P.time.mean_ttr_sim_s} s over {P.time.n_truly_resolved_with_ttr} cases. It is not comparable to real-world MTTR.</li>
          <li>Not integrated: OpenTelemetry, Prometheus, Grafana, ELK and Kubernetes. The MHP-RCA paper was not reproduced.</li>
        </ul>
      </Sheet>
    </div>
  )
}