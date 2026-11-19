import { useMemo } from 'react'

const W = 640, H = 190, PAD = 26, TOTAL = 52

function stats(pre) {
  const ref = pre.slice(0, 20).slice().sort((a, b) => a - b)
  const med = ref[Math.floor(ref.length / 2)]
  const dev = pre.slice(0, 20).map(v => Math.abs(v - med)).sort((a, b) => a - b)
  const sigma = Math.max(1.4826 * dev[Math.floor(dev.length / 2)], 0.05 * Math.abs(med), 0.1)
  return { med, sigma }
}

export default function Trace({ s, shown, postShown }) {
  const { pre, post, onset } = s
  const { med, sigma } = useMemo(() => stats(pre), [pre])
  const all = [...pre, ...(post || [])]
  const lo = Math.min(...all, med - 6 * sigma), hi = Math.max(...all)
  const X = (i) => PAD + (i / (TOTAL - 1)) * (W - PAD - 8)
  const Y = (v) => H - PAD - ((v - lo) / (hi - lo || 1)) * (H - 2 * PAD)
  const path = (arr, off) => arr.map((v, i) => `${i ? 'L' : 'M'}${X(off + i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  const preShown = pre.slice(0, shown)
  const postArr = post ? post.slice(0, postShown) : []
  const lastI = postArr.length ? pre.length + postArr.length - 1 : preShown.length - 1
  const lastV = postArr.length ? postArr[postArr.length - 1] : preShown[preShown.length - 1]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label={`Live ${s.metric} trace for ${s.service}`}>
      <rect x={PAD} y={Y(med + 6 * sigma)} width={W - PAD - 8} height={Math.max(2, Y(med - 6 * sigma) - Y(med + 6 * sigma))} fill="rgb(var(--tgrn))" opacity="0.12" />
      <line x1={PAD} x2={W - 8} y1={Y(med + 6 * sigma)} y2={Y(med + 6 * sigma)} stroke="rgb(var(--tred))" strokeDasharray="5 4" strokeWidth="1.5" />
      <text x={W - 10} y={Y(med + 6 * sigma) - 5} textAnchor="end" className="fill-tred text-[10px] font-semibold">alarm line</text>
      <text x={PAD + 4} y={H - 8} className="fill-mute text-[10px]">normal range shaded</text>
      {shown > onset && <><line x1={X(onset)} x2={X(onset)} y1={8} y2={H - PAD} stroke="rgb(var(--tred))" strokeWidth="2" />
        <text x={X(onset) + 5} y={18} className="fill-tred text-[11px] font-bold">trouble starts</text></>}
      {post && postShown > 0 && <><line x1={X(pre.length)} x2={X(pre.length)} y1={8} y2={H - PAD} stroke="rgb(var(--ink))" strokeWidth="2" strokeDasharray="2 4" />
        <text x={X(pre.length) + 5} y={34} className="fill-ink text-[11px] font-bold">fix applied</text></>}
      <path d={path(preShown, 0)} fill="none" stroke="rgb(var(--ink))" strokeWidth="2.5" strokeLinejoin="round" />
      {postArr.length > 0 && <path d={path(postArr, pre.length)} fill="none" stroke="rgb(var(--tgrn))" strokeWidth="3.5" strokeLinejoin="round" />}
      {lastV !== undefined && <circle cx={X(lastI)} cy={Y(lastV)} r="5" fill="rgb(var(--tred))" stroke="rgb(var(--ink))" strokeWidth="2" />}
    </svg>
  )
}