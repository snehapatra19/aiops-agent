import { useEffect, useState } from 'react'
import { Sheet, pct } from './ui.jsx'

const STEPS = [
  ['Detect', 'Finds metrics that stay abnormal, not one-off blips'],
  ['Correlate', 'Groups related alerts into a single incident'],
  ['Evidence', 'Pulls logs, traces and recent deploys'],
  ['Root cause', 'Ranks likely causes and says how sure it is'],
  ['Plan', 'Picks a safe action and checks it against policy'],
  ['Fix', 'Runs only actions on the approved list'],
  ['Verify', 'Re-measures to confirm the fix really worked'],
  ['Human', 'Pages an engineer when unsafe or unsure'],
  ['Report', 'Writes the incident report and saves it'],
]

const PROBLEMS = [
  ['Too many alerts', 'One failure sets off dozens of alarms. Engineers lose time deciding which ones belong together.'],
  ['Fixes that did not fix', 'A script can run without error and the system can still be broken. Most tools stop checking there.'],
  ['No clear hand-off', 'Automation that never says "I am not sure" is dangerous. Knowing when to stop is part of the job.'],
]

const REAL = [
  ['Live machine', 'machine', 'Watches the real CPU of this computer, finds a real spike and pauses a real stress process.'],
  ['Real data lab', 'lab', 'Reads real recorded datasets from their zip files and runs the detector on them in Python.'],
  ['Incident database', 'machine', 'Every incident is saved in SQLite and served back through the API.'],
]

const STACK = ['Python', 'FastAPI', 'LangGraph', 'NumPy', 'SQLite', 'React', 'Vite', 'Tailwind']

function Tile({ big, label, tone }) {
  return (
    <div className={`border-2 border-ink p-4 ${tone}`}>
      <div className="font-display text-3xl font-extrabold leading-none md:text-4xl">{big}</div>
      <div className="mt-2 text-xs font-semibold">{label}</div>
    </div>
  )
}

export default function Home({ go }) {
  const [d, setD] = useState(null)
  useEffect(() => { fetch('/api/results').then(r => r.json()).then(setD).catch(() => {}) }, [])
  const A = d?.aggregate
  const real = d?.real
  const series = (real?.nab?.series || 0) + Object.values(real?.others?.datasets || {}).reduce((s, x) => s + x.series, 0)
  const sets = (real?.nab ? 1 : 0) + Object.keys(real?.others?.datasets || {}).length
  return (
    <div className="space-y-6">
      <section className="border-2 border-ink bg-ink p-8 text-sheet md:p-12">
        <div className="mb-4 inline-block border-2 border-sheet px-3 py-1 text-xs font-bold uppercase tracking-wide">7th semester capstone, AIOps</div>
        <h2 className="h-display max-w-4xl text-3xl leading-tight md:text-5xl">An AI agent for the engineer who gets paged at 3 a.m.</h2>
        <p className="mt-5 max-w-2xl text-base text-rule md:text-lg">It watches the metrics, works out the likely cause, applies a safe fix, checks that the fix worked, and hands over to a human when it is not sure.</p>
        <div className="mt-7 flex flex-wrap gap-3">
          <button onClick={() => go('live')} className="border-2 border-sheet bg-tyel px-5 py-3 text-sm font-bold text-ink">Try the live board</button>
          <button onClick={() => go('lab')} className="border-2 border-sheet px-5 py-3 text-sm font-bold text-sheet hover:bg-sheet/15">See it on real data</button>
        </div>
      </section>

      {A && <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile big={A.n_cases} label="synthetic incident cases, five fault types" tone="bg-tyel" />
        <Tile big={`${sets} real datasets`} label={`${series} real series, same untuned thresholds`} tone="bg-mint" />
        <Tile big={pct(A.proposed.remediation.false_resolution_rate)} label={`false "fixed" claims by the agent, against ${pct(A.baseline.remediation.false_resolution_rate)} for the baseline`} tone="bg-pink" />
        <Tile big={pct(A.proposed.remediation.final_decision_accuracy)} label="right final decision: fix, or call a human" tone="bg-tora" />
      </section>}

      <section>
        <h3 className="h-display mb-3 text-xl">Why this problem matters</h3>
        <div className="grid gap-3 md:grid-cols-3">
          {PROBLEMS.map(([t, s], i) => <div key={t} className="sheet p-4"><div className="font-display text-3xl font-extrabold text-mute">0{i + 1}</div><div className="mt-2 text-base font-bold">{t}</div><p className="mt-1 text-sm">{s}</p></div>)}
        </div>
      </section>

      <section>
        <h3 className="h-display mb-3 text-xl">How the agent works, step by step</h3>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map(([t, s], i) => <li key={t} className="sheet flex gap-3 p-3"><span className="font-display text-2xl font-extrabold">{i + 1}</span><div><div className="text-sm font-bold">{t}</div><div className="text-xs text-mute">{s}</div></div></li>)}
        </ol>
      </section>

      <section>
        <h3 className="h-display mb-3 text-xl">The backend is real, not a mock-up</h3>
        <div className="grid gap-3 md:grid-cols-3">
          {REAL.map(([t, k, s], i) => (
            <Sheet key={t} title={t} tone={['mint', 'yel', 'pink'][i]}>
              <p className="mb-3 text-sm">{s}</p>
              <button onClick={() => go(k)} className="border-2 border-ink bg-ink px-3 py-1.5 text-xs font-bold text-sheet">Open</button>
            </Sheet>))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Sheet title="Honest limits">
          <ul className="list-disc space-y-1.5 pl-5 text-sm">
            <li>The fault-and-fix demo runs on synthetic data with simulated fixes.</li>
            <li>On real datasets our detector raises very few false alarms but misses many anomalies. A simple static rule catches more on three of four datasets and floods the engineer with alarms.</li>
            <li>The real datasets test detection only. They have no root-cause or fix labels.</li>
            <li>Not integrated yet: OpenTelemetry, Prometheus, Grafana and Kubernetes.</li>
          </ul>
        </Sheet>
        <Sheet title="Built with">
          <div className="flex flex-wrap gap-2">{STACK.map(s => <span key={s} className="border-2 border-ink bg-paper px-3 py-1 text-sm font-bold">{s}</span>)}</div>
          <p className="mt-3 text-xs text-mute">Datasets: NAB, SMD, KPI (AIOps 2018) and SKAB for detection, plus a generated benchmark of 120 incident cases.</p>
        </Sheet>
      </section>
    </div>
  )
}