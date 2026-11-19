const ORDER = [
  ['detect', 'Detect', 'Scanning metrics for signals that stay abnormal'],
  ['correlate', 'Correlate', 'Grouping related alerts into one incident'],
  ['evidence', 'Evidence', 'Pulling logs, traces and deploy events'],
  ['rca', 'Root cause', 'Ranking the most likely root causes'],
  ['plan', 'Plan', 'Choosing a safe action and checking the policy'],
  ['execute', 'Fix', 'Running the fix in the simulator'],
  ['verify', 'Verify', 'Re-measuring to check that the fix really worked'],
  ['escalate', 'Human', 'Not safe or not sure enough, so a person is paged'],
  ['report', 'Report', 'Writing the incident report'],
]

const END = {
  resolved: 'Done. The agent fixed it and the metrics confirm it.',
  escalated: 'Done. The agent handed this over to a human.',
  no_incident: 'Done. Nothing stayed abnormal, so there was nothing to fix.',
}

function stateOf(node, p) {
  if (p.seen.includes(node)) return !p.done && node === p.seen[p.seen.length - 1] ? 'current' : 'done'
  if (p.done && p.all.length && !p.all.includes(node)) return 'skipped'
  return 'pending'
}

const STYLE = {
  done: 'border-ink bg-ink text-sheet',
  current: 'border-ink bg-tyel text-ink',
  pending: 'border-rule bg-sheet text-mute',
  skipped: 'border-dashed border-rule bg-paper text-mute line-through',
}

export default function PipelineRail({ pulse }) {
  const p = pulse || { seen: [], all: [], done: false, status: null }
  const now = ORDER.find(([k]) => stateOf(k, p) === 'current')
  const caption = p.done ? END[p.status] || 'Done.' : now ? now[2] : 'Pick a fault on the left to start the agent.'
  return (
    <div className="sheet mb-4 px-4 py-3">
      <ol className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-9">
        {ORDER.map(([k, label], i) => {
          const s = stateOf(k, p)
          const human = k === 'escalate' && s === 'done'
          return (
            <li key={k} aria-current={s === 'current' ? 'step' : undefined}
              className={`flex items-center gap-2 border-2 px-2 py-1.5 text-xs font-bold transition-colors ${human ? 'border-ink bg-tyel text-ink' : STYLE[s]}`}>
              <span className="font-display text-sm">{i + 1}</span>
              <span className="min-w-0 flex-1 leading-tight">{label}</span>
              {s === 'current' && <span className="blink h-2.5 w-2.5 shrink-0 bg-tred" aria-hidden="true" />}
            </li>
          )
        })}
      </ol>
      <p aria-live="polite" className="mt-2 text-xs font-semibold">{caption}</p>
    </div>
  )
}