const MODES = {
  calm: { label: 'All systems normal', color: 'var(--tgrn)', secs: 3.2 },
  alert: { label: 'Incident in progress', color: 'var(--tred)', secs: 0.9 },
  healed: { label: 'Fixed and verified', color: 'var(--tgrn)', secs: 3.2 },
  human: { label: 'Waiting for a human', color: 'var(--tyel)', secs: 1.8 },
}

const BEAT = 'M0 20 H58 L66 20 L72 13 L79 20 H98 L106 25 L114 3 L123 38 L131 20 H148 L158 14 L170 20 H200'
const COUNT = 10
const FADE = 'linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)'

export default function EcgHeader({ mode = 'calm' }) {
  const m = MODES[mode] || MODES.calm
  const stroke = `rgb(${m.color})`
  return (
    <div role="status" className="flex items-center gap-4 border-t-2 border-sheet/30 px-5">
      <style>{`@keyframes ecg-scroll { to { transform: translateX(-200px); } } .ecg-run { animation: ecg-scroll var(--d) linear infinite; } @media (prefers-reduced-motion: reduce) { .ecg-run { animation: none; } }`}</style>
      <div className="flex w-52 shrink-0 items-center gap-2 py-2 text-xs font-bold uppercase tracking-wide">
        <span className="inline-block h-3 w-3" style={{ background: stroke }} aria-hidden="true" />
        <span>{m.label}</span>
      </div>
      <div className="h-9 min-w-0 flex-1 overflow-hidden" style={{ maskImage: FADE, WebkitMaskImage: FADE }} aria-hidden="true">
        <svg width={COUNT * 200} height="36" viewBox={`0 0 ${COUNT * 200} 40`} preserveAspectRatio="none">
          <defs><path id="ecg-beat" d={BEAT} fill="none" /></defs>
          <g className="ecg-run" style={{ '--d': `${m.secs}s` }} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinejoin="round">
            {Array.from({ length: COUNT }, (_, i) => <use key={i} href="#ecg-beat" x={i * 200} />)}
          </g>
        </svg>
      </div>
    </div>
  )
}