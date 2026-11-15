import { useEffect, useState } from 'react'
import { bridge } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { confirmAction } from '@/lib/use-confirm'
import { useJobs } from '@/lib/use-jobs'

export function CodeUpdateNotice() {
  const jobs = useJobs()
  const [frontendChanged, setFrontendChanged] = useState(false)
  const [restartRequired, setRestartRequired] = useState(false)
  const [restarting, setRestarting] = useState(false)
  useEffect(() => {
    let first: string | null = null
    let active = true
    const check = async () => {
      try {
        const update = await bridge.getCodeUpdate()
        if (!active) return
        if (first === null) first = update.interface_version
        setFrontendChanged(first !== update.interface_version)
        setRestartRequired(update.restart_required)
      } catch { /* The current interface remains usable while a build finishes. */ }
    }
    void check()
    const timer = setInterval(() => void check(), 5000)
    return () => { active = false; clearInterval(timer) }
  }, [])
  if (!frontendChanged && !restartRequired) return null

  async function restart() {
    const ok = await confirmAction({
      title: 'Apply the code update?',
      description: jobs.busy
        ? 'ReFlow will pause the active job, save completed work and reopen. Choose Resume after it opens.'
        : 'ReFlow will close and reopen with the updated code.',
      confirmLabel: 'Restart ReFlow',
    })
    if (!ok) return
    setRestarting(true)
    try {
      const result = await bridge.restartWindow()
      if (!result.ok) throw new Error(result.message ?? 'Restart could not begin.')
    } catch (error) {
      setRestarting(false)
      await confirmAction({ title: 'Restart unavailable', description: String(error), alertOnly: true })
    }
  }

  return <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-primary/10 px-4 py-2 text-sm" role="status">
    <span>{restartRequired ? 'A code update is ready. Restart to apply it.' : 'An interface update is ready. Reload to apply it.'}</span>
    <Button size="sm" disabled={restarting} onClick={() => {
      if (restartRequired) void restart()
      else window.location.reload()
    }}>{restarting ? 'Saving and restarting…' : restartRequired ? 'Restart ReFlow' : 'Reload interface'}</Button>
  </div>
}
