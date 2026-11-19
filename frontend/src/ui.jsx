export const pct = (v) => (v === null || v === undefined ? 'n/a' : (v * 100).toFixed(1) + '%')
export const num = (v, d = 3) => (v === null || v === undefined ? 'n/a' : Number(v).toFixed(d))
export const short = (s) => s.replace('-service', '').replace('-primary', '').replace('api-', 'api ')
export const nice = (s) => (s || '').replaceAll('_', ' ')

export const REASONS = {
  uncertain_rca: 'The agent was not confident about the cause, so a person decides.',
  high_risk_requires_approval: 'The fix is high-risk and needs a person to approve it.',
  policy_blocked: 'Safety policy blocked the proposed action.',
  action_unavailable: 'The fix could not run (for example a capacity limit).',
  execution_error: 'The fix failed to execute.',
  verification_failed: 'The fix ran, but the metrics did not recover.',
  verification_inconclusive: 'Metrics only partly recovered, so the result is unclear.',
}

export const SCENARIOS = [
  ['db_pool_exhaustion', 'Database runs out of connections', 'Payments stall waiting for the database'],
  ['cpu_saturation', 'A service maxes out its CPU', 'Requests queue up and slow down'],
  ['memory_leak', 'Memory leak', 'A service slowly eats all its memory'],
  ['dependency_failure', 'A dependency goes down', 'Callers get 503 errors'],
  ['bad_deployment', 'A bad release ships', 'Errors jump right after a deploy'],
  ['ambiguous', 'Confusing symptoms', 'Two causes look equally likely'],
  ['failed_remediation', 'The fix does not work', 'Action runs but nothing improves'],
  ['partial_recovery', 'The fix half-works', 'Metrics improve but not enough'],
  ['action_unavailable', 'The fix is unavailable', 'No capacity to run the action'],
  ['missing_evidence', 'Logs and traces are missing', 'Only a latency alert to go on'],
  ['normal', 'A normal day', 'Only harmless blips and false alarms'],
]

const TONE = { yel: 'bg-tyel', mint: 'bg-mint', pink: 'bg-pink', ora: 'bg-tora', ink: 'bg-ink text-sheet', none: 'bg-sheet' }
export function Sheet({ title, aside, children, className = '', tone = 'none' }) {
  return (
    <section className={`sheet ${className}`}>
      {(title || aside) && (
        <header className={`flex items-center justify-between border-b-2 border-ink px-4 py-2 ${TONE[tone]}`}>
          <h3 className="text-sm font-bold">{title}</h3>{aside}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export const Chip = ({ tone = 'ink', children }) => {
  const t = { ink: 'border-ink text-ink', red: 'border-tred bg-tred text-white', grn: 'border-tgrn bg-tgrn text-white', yel: 'border-ink bg-tyel text-ink', mute: 'border-rule text-mute', light: 'border-sheet text-sheet' }
  return <span className={`inline-block rounded-full border-2 px-2.5 py-0.5 text-xs font-semibold ${t[tone]}`}>{children}</span>
}