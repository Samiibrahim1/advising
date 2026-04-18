import { useState } from 'react'

import { apiFetch } from '../../lib/api'

const MAJORS = ['PBHL', 'SPTH-New', 'SPTH-Old', 'NURS']

export function ImportsPage() {
  const [majorCode, setMajorCode] = useState('PBHL')
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function runAction(action: 'snapshot-export' | 'snapshot-import' | 'google-drive') {
    setBusyAction(action)
    setMessage(null)
    try {
      const result = await apiFetch<Record<string, unknown>>(`/imports/${action}/${majorCode}`, { method: 'POST' })
      setMessage(JSON.stringify(result, null, 2))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <section className="stack">
      <div className="page-header">
        <div>
          <div className="eyebrow">Admin Panel</div>
          <h2>Legacy Imports</h2>
        </div>
      </div>
      <div className="panel stack">
        <label>
          <span>Major code</span>
          <select value={majorCode} onChange={(event) => setMajorCode(event.target.value)}>
            {MAJORS.map((major) => (
              <option key={major} value={major}>
                {major}
              </option>
            ))}
          </select>
        </label>
        <div className="stack" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', display: 'grid' }}>
          <button type="button" onClick={() => runAction('snapshot-export')} disabled={busyAction !== null}>
            {busyAction === 'snapshot-export' ? 'Exporting snapshot...' : '1. Export Drive to local snapshot'}
          </button>
          <button type="button" onClick={() => runAction('snapshot-import')} disabled={busyAction !== null}>
            {busyAction === 'snapshot-import' ? 'Importing snapshot...' : '2. Import local snapshot into v2'}
          </button>
          <button type="button" onClick={() => runAction('google-drive')} disabled={busyAction !== null}>
            {busyAction === 'google-drive' ? 'Importing from Drive...' : 'Direct Drive import'}
          </button>
        </div>
        <p className="muted">
          Recommended path: export a local snapshot first, then import that snapshot. This avoids repeated live Google reads during the v2 import.
        </p>
        {message ? <pre className="code-block">{message}</pre> : null}
      </div>
    </section>
  )
}
