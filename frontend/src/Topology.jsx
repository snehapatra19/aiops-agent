import { motion } from 'framer-motion'
import { short } from './ui.jsx'

export const POS = {
  frontend: [350, 36], 'api-gateway': [350, 120], 'payment-service': [120, 215], 'order-service': [350, 215],
  'auth-service': [580, 215], 'cache-redis': [470, 320], 'db-primary': [230, 320],
}
const EDGES = [['frontend', 'api-gateway'], ['api-gateway', 'payment-service'], ['api-gateway', 'order-service'],
  ['api-gateway', 'auth-service'], ['payment-service', 'db-primary'], ['order-service', 'db-primary'],
  ['order-service', 'cache-redis'], ['auth-service', 'cache-redis']]
const FILL = { green: 'rgb(var(--tgrn))', yellow: 'rgb(var(--tyel))', red: 'rgb(var(--tred))' }
const TINT = { green: 'rgb(var(--mint) / 0.6)', yellow: 'rgb(var(--tyel) / 0.45)', red: 'rgb(var(--tred) / 0.3)' }

/* state: {service: 'green'|'yellow'|'red'}, vitals: {service: 'cpu 91'} */
export default function Topology({ state = {}, vitals = {}, root = null, truth = null }) {
  return (
    <svg viewBox="0 0 700 360" className="h-full w-full" role="img" aria-label="Service dependency map with health colours">
      {EDGES.map(([a, b]) => {
        const hot = state[a] === 'red' && state[b] === 'red'
        return <line key={a + b} x1={POS[a][0]} y1={POS[a][1]} x2={POS[b][0]} y2={POS[b][1]}
          stroke={hot ? 'rgb(var(--tred))' : 'rgb(var(--ink))'} strokeWidth={hot ? 4 : 1.5} strokeDasharray={hot ? '8 5' : '3 9'} className={hot ? 'flow-fast' : 'flow'} opacity={hot ? 1 : 0.5} />
      })}
      {Object.entries(POS).map(([s, [x, y]]) => {
        const st = state[s] || 'green'
        return (
          <g key={s}>
            {truth === s && <rect x={x - 66} y={y - 33} width={132} height={66} fill="none" stroke="rgb(var(--ink))" strokeWidth={2} strokeDasharray="3 4" />}
            {root === s && <motion.rect x={x - 62} y={y - 29} width={124} height={58} fill="none" stroke="rgb(var(--ink))" strokeWidth={4}
              animate={{ opacity: [1, 0.25, 1] }} transition={{ repeat: Infinity, duration: 1.1 }} />}
            <rect x={x - 54} y={y - 22} width={108} height={44} fill={TINT[st]} stroke="rgb(var(--ink))" strokeWidth={2} />
            <rect x={x - 54} y={y - 22} width={12} height={44} fill={FILL[st]} stroke="rgb(var(--ink))" strokeWidth={2} />
            <text x={x - 34} y={y - 3} className="fill-ink text-[13px] font-bold">{short(s)}</text>
            <text x={x - 34} y={y + 13} className="fill-ink text-[11px]">{vitals[s] || (st === 'green' ? 'healthy' : st === 'yellow' ? 'degrading' : 'failing')}</text>
          </g>
        )
      })}
      {root && <text x={POS[root][0]} y={POS[root][1] - 40} textAnchor="middle" className="fill-ink text-[11px] font-bold">suspected root cause</text>}
    </svg>
  )
}