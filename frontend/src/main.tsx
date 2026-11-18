import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { BootScreen } from './components/shell/BootScreen'
import { initializePreferences } from './lib/preference-storage'
import { initializeLogs } from './lib/use-logs'

const root = createRoot(document.getElementById('root')!)
let starting = false
async function start() {
  if (starting) return
  starting = true
  root.render(<BootScreen visible statusText="LOADING SAVED SETTINGS…" />)
  try {
    await initializePreferences()
    root.render(<StrictMode><App /></StrictMode>)
  } catch {
    root.render(<BootScreen visible statusText="STARTUP NEEDS ATTENTION"
      error="ReFlow could not load your saved settings or connect to the desktop core. Retry, or close and reopen the app."
      onRetry={() => { void start() }} />)
  } finally {
    starting = false
  }
}
initializeLogs()
void start()
