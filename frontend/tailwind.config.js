const c = (n) => `rgb(var(--${n}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        paper: c('paper'), ink: c('ink'), sheet: c('sheet'), rule: c('rule'), mute: c('mute'),
        tred: c('tred'), tyel: c('tyel'), tgrn: c('tgrn'), mint: c('mint'), pink: c('pink'), tora: c('tora'),
      },
      fontFamily: {
        display: ['"Unbounded Variable"', 'Unbounded', 'system-ui', 'sans-serif'],
        sans: ['"Instrument Sans Variable"', 'Instrument Sans', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}