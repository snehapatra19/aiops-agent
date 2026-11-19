import { useState } from 'react'
import Live from './Live.jsx'
import LiveMachine from './LiveMachine.jsx'
import Results from './Results.jsx'
import { Chip } from './ui.jsx'
import ThemePicker from './ThemePicker.jsx'
import EcgHeader from './EcgHeader.jsx'
import PipelineRail from './PipelineRail.jsx'
import StatusBar from './StatusBar.jsx'
import RealLab from './RealLab.jsx'

const IDLE = { seen: [], all: [], done: false, status: null }

export default function App() {
  const [tab, setTab] = useState('live')
  const [pulse, setPulse] = useState(IDLE)
  const go = (k) => {
    setTab(k)
    if (k !== 'live') setPulse(IDLE)
  }
  const mode = pulse.done
    ? pulse.status === 'resolved' ? 'healed' : pulse.status === 'escalated' ? 'human' : 'calm'
    : pulse.seen.length > 0 && pulse.status !== 'no_incident' ? 'alert' : 'calm'
  const T = (k, l) => (
    <button onClick={() => go(k)} aria-pressed={tab === k}
      className={`border-2 border-sheet px-4 py-2 text-sm font-bold ${tab === k ? 'bg-tyel text-ink' : 'bg-transparent text-sheet hover:bg-sheet/15'}`}>{l}</button>)
  return (
    <div className="mx-auto max-w-[1500px] px-5 pb-14 pt-5">
      <header className="mb-5 border-2 border-ink bg-ink text-sheet">
        <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex items-center gap-4">
            <div className="flex gap-1.5" aria-hidden="true"><span className="h-5 w-5 bg-tred" /><span className="h-5 w-5 bg-tyel" /><span className="h-5 w-5 bg-tgrn" /></div>
            <div>
              <h1 className="h-display text-xl leading-tight md:text-2xl">Systems that heal themselves, and know when to call a human</h1>
              <p className="mt-1 max-w-2xl text-sm text-rule">Inject a fault and watch an AI agent detect it, find the cause, apply a safe fix, check that it worked, or escalate.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="light">{tab === 'machine' ? 'Real CPU, sandbox action' : 'Synthetic data, simulated fixes'}</Chip>
            <div className="ml-2 flex flex-wrap">{T('live', 'Live board')}{T('machine', 'Live machine')}{T('lab', 'Real data lab')}{T('results', 'Scorecard')}</div>
            <ThemePicker />
          </div>
        </div>
        <EcgHeader mode={mode} />
      </header>
      {tab === 'live' && <PipelineRail pulse={pulse} />}
      {tab === 'live' ? <Live onPulse={setPulse} /> : tab === 'machine' ? <LiveMachine /> : tab === 'lab' ? <RealLab /> : <Results />}
      <StatusBar />
    </div>
  )
}