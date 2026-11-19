import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/unbounded'
import '@fontsource-variable/instrument-sans'
import App from './App.jsx'
import { initTheme } from './ThemePicker.jsx'
import './index.css'
initTheme()
createRoot(document.getElementById('root')).render(<App />)