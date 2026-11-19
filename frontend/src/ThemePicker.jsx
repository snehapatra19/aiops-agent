import { useEffect, useRef, useState } from 'react'

const KEY = 'aiops-theme'

export const THEMES = [
  { id: 'chart-paper', label: 'Chart paper', note: 'Warm grey sheet with the ECG grid' },
  { id: 'blueprint', label: 'Blueprint', note: 'Cool blue, like a drafting table' },
  { id: 'night-shift', label: 'Night shift', note: 'Dark and easy on the eyes' },
  { id: 'terminal', label: 'Terminal', note: 'Neon green on black, like a console' },
  { id: 'cyber', label: 'Cyber', note: 'Cyan on deep violet' },
  { id: 'high-contrast', label: 'High contrast', note: 'Black on white, easiest to read' },
]

const read = () => {
  try {
    const v = localStorage.getItem(KEY)
    return THEMES.some((t) => t.id === v) ? v : THEMES[0].id
  } catch {
    return THEMES[0].id
  }
}

const apply = (id) => {
  document.documentElement.dataset.theme = id
}

export const initTheme = () => apply(read())

function Swatch({ id, size = 'h-9 w-20' }) {
  return (
    <span data-theme={id} aria-hidden="true" className={`flex shrink-0 overflow-hidden border-2 border-ink bg-paper ${size}`}>
      <span className="w-1/5 bg-sheet" />
      <span className="w-1/5 bg-ink" />
      <span className="w-1/5 bg-tred" />
      <span className="w-1/5 bg-tyel" />
      <span className="w-1/5 bg-tgrn" />
    </span>
  )
}

export default function ThemePicker() {
  const [theme, setTheme] = useState(read)
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  const trigger = useRef(null)

  useEffect(() => {
    apply(theme)
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      return
    }
  }, [theme])

  useEffect(() => {
    if (!open) return undefined
    const away = (e) => {
      if (box.current && !box.current.contains(e.target)) setOpen(false)
    }
    const esc = (e) => {
      if (e.key === 'Escape') {
        setOpen(false)
        trigger.current?.focus()
      }
    }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const current = THEMES.find((t) => t.id === theme) || THEMES[0]

  return (
    <div ref={box} className="relative">
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className="flex items-center gap-2 border-2 border-sheet px-3 py-2 text-sm font-bold text-sheet hover:bg-sheet/15"
      >
        <Swatch id={theme} size="h-4 w-10" />
        <span>Theme: {current.label}</span>
      </button>
      {open && (
        <div role="radiogroup" aria-label="Colour theme" className="sheet absolute right-0 top-full z-30 mt-2 w-80 max-w-[90vw] p-2 text-ink shadow-[4px_4px_0_0_rgb(var(--ink))]">
          {THEMES.map((t) => {
            const on = t.id === theme
            return (
              <label key={t.id} className="block cursor-pointer">
                <input
                  type="radio"
                  name="theme"
                  value={t.id}
                  checked={on}
                  onChange={() => setTheme(t.id)}
                  className="peer sr-only"
                />
                <span className={`flex items-center gap-3 border-2 p-2 peer-focus-visible:ring-2 peer-focus-visible:ring-ink ${on ? 'border-ink bg-paper' : 'border-transparent hover:bg-paper'}`}>
                  <Swatch id={t.id} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-bold">{t.label}</span>
                    <span className="block text-xs text-mute">{t.note}</span>
                  </span>
                  {on && <span className="text-xs font-bold">In use</span>}
                </span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}