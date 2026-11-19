import { useEffect, useState } from 'react'
import { Sheet, Chip } from './ui.jsx'

const W = 900, H = 300, PL = 44, PR = 12, PT = 30, PB = 46

function Chart({ d, shown }) {
  const n = d.values.length
  const lo = Math.min(...d.values), hi = Math.max(...d.values), pad = (hi - lo || 1) * 0.08
  const X = (i) => PL + (i / Math.max(n - 1, 1)) * (W - PL - PR)
  const Y = (v) => H - PB - ((Math.min(Math.max(v, lo - pad), hi + pad) - (lo - pad)) / (hi - lo + 2 * pad)) * (H - PT - PB)
  const path = (arr, k) => arr.slice(0, k).map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  const spans = []
  d.labels.forEach((l, i) => {
    if (l && (i === 0 || !d.labels[i - 1])) spans.push([i, i])
    if (l) spans[spans.length - 1][1] = i
  })
  const local = (arr) => arr.map(i => i - d.start).filter(i => i >= 0 && i < shown)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Real series replayed through the detector">
      {spans.map(([a, b], k) => <rect key={k} x={X(a)} y={PT - 6} width={Math.max(3, X(b) - X(a))} height={H - PT - PB + 6} fill="rgb(var(--tyel))" opacity="0.35" />)}
      <line x1={PL} x2={W - PR} y1={H - PB} y2={H - PB} stroke="rgb(var(--ink))" strokeWidth="1.5" />
      <path d={path(d.upper, shown)} fill="none" stroke="rgb(var(--tred))" strokeWidth="1.5" strokeDasharray="5 4" />
      <path d={path(d.values, shown)} fill="none" stroke="rgb(var(--ink))" strokeWidth="2" strokeLinejoin="round" />
      {local(d.static).map(i => <line key={'s' + i} x1={X(i)} x2={X(i)} y1={H - PB + 10} y2={H - PB + 26} stroke="rgb(var(--tora))" strokeWidth="2" />)}
      {local(d.ours).map(i => <path key={'o' + i} d={`M${X(i) - 7},8 L${X(i) + 7},8 L${X(i)},22 Z`} fill="rgb(var(--tred))" stroke="rgb(var(--ink))" strokeWidth="1.5" />)}
      <text x={PL} y={H - 8} className="fill-mute text-[11px]">sample {d.start}</text>
      <text x={W - PR} y={H - 8} textAnchor="end" className="fill-mute text-[11px]">sample {d.start + n}</text>
    </svg>
  )
}

function Card({ title, s, inView, tone }) {
  return (
    <div className="border-2 border-ink p-3">
      <div className="mb-1 flex items-center gap-2 text-xs font-bold text-mute"><span className={`inline-block h-3 w-3 border-2 border-ink ${tone}`} />{title}</div>
      <div className="font-display text-2xl font-extrabold leading-none">{s.hit} of {s.windows}</div>
      <div className="mt-1 text-xs">anomalies caught in the whole series</div>
      <div className="mt-2 text-xs text-mute">{s.alarms} alarms in total, {inView} in this view</div>
    </div>
  )
}

export default function RealLab() {
  const [cat, setCat] = useState(null)
  const [key, setKey] = useState('skab')
  const [name, setName] = useState(null)
  const [dim, setDim] = useState(-1)
  const [win, setWin] = useState(0)
  const [d, setD] = useState(null)
  const [shown, setShown] = useState(0)
  const [err, setErr] = useState(null)

  useEffect(() => {
    fetch('/api/real/catalog').then(r => r.json()).then(c => {
      setCat(c)
      const k = c.skab ? 'skab' : Object.keys(c)[0]
      if (k) { setKey(k); setName(c[k].series[0]) }
    }).catch(() => setErr('Cannot reach the backend. Start it with: uvicorn api:app --port 8000'))
  }, [])

  const pick = (k) => { setKey(k); setName(cat[k].series[0]); setDim(-1); setWin(0) }
  const choose = (v) => { setName(v); setDim(-1); setWin(0) }

  useEffect(() => {
    if (!name) return
    let alive = true
    setD(null); setErr(null)
    fetch(`/api/real/replay?dataset=${key}&series=${encodeURIComponent(name)}&dim=${dim}&win=${win}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(x => { if (alive) { setD(x); setShown(0) } })
      .catch(() => alive && setErr('Could not load this series. Check that the zip files are in data/real.'))
    return () => { alive = false }
  }, [key, name, dim, win])

  useEffect(() => {
    if (!d) return
    const step = Math.max(4, Math.ceil(d.values.length / 100))
    const h = setInterval(() => setShown(s => (s >= d.values.length ? s : Math.min(d.values.length, s + step))), 40)
    return () => clearInterval(h)
  }, [d])

  if (err && !cat) return <Sheet><p className="font-semibold text-tred">{err}</p></Sheet>
  if (!cat) return <Sheet><p className="text-mute">Loading the dataset list. The first load can take about 15 seconds.</p></Sheet>
  const keys = Object.keys(cat)
  if (!keys.length) return <Sheet><p className="font-semibold">No dataset zips found. Copy them into data/real and restart the backend.</p></Sheet>
  const inView = (a) => (d ? a.filter(i => i - d.start < shown).length : 0)

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        <Sheet title="Real data lab" tone="mint" aside={<Chip>Real recorded data</Chip>}>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {keys.map(k => <button key={k} onClick={() => pick(k)} aria-pressed={key === k}
              className={`border-2 border-ink px-3 py-1.5 text-sm font-bold ${key === k ? 'bg-ink text-sheet' : 'bg-sheet hover:bg-tyel'}`}>{k.toUpperCase()}</button>)}
            <select value={name || ''} onChange={e => choose(e.target.value)} aria-label="Series" className="border-2 border-ink bg-sheet px-2 py-1.5 text-sm">
              {cat[key].series.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            {d && d.dims > 1 && <select value={dim} onChange={e => setDim(Number(e.target.value))} aria-label="Metric" className="border-2 border-ink bg-sheet px-2 py-1.5 text-sm">
              <option value={-1}>Metric: most informative</option>
              {Array.from({ length: d.dims }, (_, i) => <option key={i} value={i}>Metric {i + 1}</option>)}
            </select>}
          </div>
          <div className="h-[300px]">
            {!d && !err && <p className="pt-24 text-center text-sm text-mute">Running the detector on the real series…</p>}
            {err && <p className="pt-24 text-center text-sm font-semibold text-tred">{err}</p>}
            {d && <Chart d={d} shown={shown} />}
          </div>
          {d && <div className="mt-3 flex flex-wrap items-center gap-3 text-xs font-medium">
            <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-4 bg-tyel/60" />labelled anomaly</span>
            <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 bg-tred" />our alarm</span>
            <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-1 bg-tora" />static-rule alarm</span>
            <span className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed border-tred" />our alarm line</span>
            <span className="ml-auto flex items-center gap-2">
              <button disabled={win <= 0} onClick={() => setWin(win - 1)} className="border-2 border-ink bg-sheet px-2 py-1 font-bold hover:bg-tyel disabled:opacity-40">Previous</button>
              <span>Anomaly {d.n_windows ? d.win + 1 : 0} of {d.n_windows}</span>
              <button disabled={win >= d.n_windows - 1} onClick={() => setWin(win + 1)} className="border-2 border-ink bg-sheet px-2 py-1 font-bold hover:bg-tyel disabled:opacity-40">Next</button>
              <button onClick={() => setShown(0)} className="border-2 border-ink bg-ink px-3 py-1 font-bold text-sheet">Replay</button>
            </span>
          </div>}
        </Sheet>
      </div>
      <div className="space-y-4">
        <Sheet title="Same data, two detectors" tone="yel">
          {d ? <div className="space-y-3">
            <Card title="Our detector" s={d.stats.ours} inView={inView(d.ours)} tone="bg-tred" />
            <Card title="Static threshold" s={d.stats.static} inView={inView(d.static)} tone="bg-tora" />
            <p className="text-xs text-mute">Counts cover the whole series for the metric shown. This is one series, so use the Scorecard for the totals over all of them.</p>
          </div> : <p className="text-sm text-mute">Loading…</p>}
        </Sheet>
        <Sheet title="What is happening here" tone="pink">
          <p className="text-sm">The detector runs on the real recorded series and the chart replays the result. Nothing here is generated, and the thresholds are the same untuned ones used in the Scorecard.</p>
        </Sheet>
      </div>
    </div>
  )
}