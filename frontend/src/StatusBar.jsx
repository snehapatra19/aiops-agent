import { useEffect, useState } from 'react'

export default function StatusBar() {
  const [s, setS] = useState({ up: null, ms: null, lg: null, mode: null })
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    let alive = true
    const ping = () => {
      const t = performance.now()
      fetch('/api/health')
        .then(r => r.json())
        .then(d => alive && setS({ up: true, ms: Math.round(performance.now() - t), lg: d.langgraph, mode: d.mode }))
        .catch(() => alive && setS({ up: false, ms: null, lg: null, mode: null }))
    }
    ping()
    const a = setInterval(ping, 5000)
    const b = setInterval(() => setNow(new Date()), 1000)
    return () => {
      alive = false
      clearInterval(a)
      clearInterval(b)
    }
  }, [])

  const dot = s.up === null ? 'bg-rule' : s.up ? 'bg-tgrn' : 'bg-tred'
  const label = s.up === null ? 'Connecting' : s.up ? 'API online' : 'API offline'

  return (
    <div role="status" className="fixed inset-x-0 bottom-0 z-20 border-t-2 border-ink bg-sheet font-mono text-xs">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-6 gap-y-1 px-5 py-1.5">
        <span className="flex items-center gap-2 font-bold"><span className={`inline-block h-2.5 w-2.5 ${dot} ${s.up ? 'blink' : ''}`} aria-hidden="true" />{label}</span>
        {s.up && <span className="text-mute">latency {s.ms} ms</span>}
        {s.up && <span className="text-mute">engine {s.lg ? 'LangGraph' : 'built-in graph'}</span>}
        {s.up && <span className="text-mute">mode {s.mode}</span>}
        <span className="ml-auto font-bold">{now.toLocaleTimeString([], { hour12: false })}</span>
      </div>
    </div>
  )
}