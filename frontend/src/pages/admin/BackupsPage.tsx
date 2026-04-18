import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { API_BASE_URL } from '../../lib/api'
import { useBackups } from '../../lib/hooks'

async function authedFetch(path: string, init?: RequestInit) {
  const token = window.localStorage.getItem('advising_v2_token')
  return fetch(`${API_BASE_URL}/api${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
}

export function BackupsPage() {
  const queryClient = useQueryClient()
  const backups = useBackups()
  const [triggering, setTriggering] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<{ id: number; date: string } | null>(null)
  const [restoring, setRestoring] = useState(false)

  async function handleTrigger() {
    setTriggering(true)
    setMessage(null)
    const r = await authedFetch('/backups/trigger', { method: 'POST' })
    setTriggering(false)
    if (!r.ok) {
      const body = await r.json().catch(() => null)
      setMessage({ type: 'error', text: body?.detail || 'Backup failed.' })
      return
    }
    setMessage({ type: 'success', text: 'Backup completed successfully.' })
    queryClient.invalidateQueries({ queryKey: ['backups'] })
  }

  async function handleRestore() {
    if (!restoreTarget) return
    setRestoring(true)
    setMessage(null)
    const r = await authedFetch(`/backups/${restoreTarget.id}/restore`, { method: 'POST' })
    setRestoring(false)
    setRestoreTarget(null)
    if (!r.ok) {
      const body = await r.json().catch(() => null)
      setMessage({ type: 'error', text: body?.detail || 'Restore failed.' })
      return
    }
    setMessage({ type: 'success', text: 'Database restored successfully. Reload the page to see updated data.' })
  }

  return (
    <section className="stack" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Backups</h2>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={handleTrigger}
          disabled={triggering}
          title="Run a full database + file backup now"
        >
          {triggering ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
              Running…
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" /></svg>
              Run Manual Backup
            </>
          )}
        </button>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      <div className="panel">
        <h3 style={{ margin: '0 0 0.5rem' }}>Backup History</h3>
        <p className="text-muted text-sm" style={{ margin: '0 0 1rem' }}>Monthly automated backups run on the 1st of each month via the scheduled job. Manual backups can be triggered above.</p>

        {backups.isLoading ? (
          <p className="text-muted text-sm">Loading…</p>
        ) : backups.data?.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No backups have been created yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Status</th>
                  <th>Triggered By</th>
                  <th>Storage Key</th>
                  <th>File Counts</th>
                  <th>Notes</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {backups.data?.map((b) => {
                  const triggeredBy = (b.manifest as Record<string, unknown>)?.triggered_by as string | undefined
                  const fileCounts = (b.manifest as Record<string, unknown>)?.storage_file_counts as Record<string, number> | undefined
                  return (
                    <tr key={b.id}>
                      <td style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'monospace' }}>{b.id}</td>
                      <td>
                        <span style={{
                          fontSize: '0.7rem',
                          background: b.status === 'completed' ? '#dcfce7' : b.status === 'failed' ? '#fee2e2' : '#fef9c3',
                          color: b.status === 'completed' ? '#15803d' : b.status === 'failed' ? '#dc2626' : '#92400e',
                          padding: '2px 8px', borderRadius: '4px', fontWeight: 700,
                        }}>
                          {b.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.875rem' }}>{triggeredBy ?? '—'}</td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--muted)', fontFamily: 'monospace', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.storage_key ?? '—'}</td>
                      <td style={{ fontSize: '0.8rem' }}>
                        {fileCounts
                          ? Object.entries(fileCounts).map(([k, v]) => `${k}: ${v}`).join(', ')
                          : '—'}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{b.notes ?? '—'}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{new Date(b.created_at).toLocaleString()}</td>
                      <td>
                        {b.status === 'completed' && (
                          <button
                            className="btn-sm"
                            style={{ fontSize: '0.7rem', padding: '2px 8px', color: '#dc2626' }}
                            onClick={() => setRestoreTarget({ id: b.id, date: new Date(b.created_at).toLocaleString() })}
                          >
                            Restore
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Restore confirmation modal */}
      {restoreTarget && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
             onClick={() => !restoring && setRestoreTarget(null)}>
          <div className="panel stack" style={{ width: '420px' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: 0, color: '#dc2626' }}>Restore Database</h3>
            <p style={{ margin: '0.5rem 0', fontSize: '0.875rem' }}>
              This will <strong>overwrite the current database</strong> with backup #{restoreTarget.id} from <strong>{restoreTarget.date}</strong>.
            </p>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--muted)' }}>
              This action cannot be undone. Consider creating a new backup first.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
              <button className="btn-sm" disabled={restoring} onClick={() => setRestoreTarget(null)}>Cancel</button>
              <button className="btn-sm" disabled={restoring} onClick={handleRestore}
                style={{ background: '#dc2626', color: '#fff', fontWeight: 700 }}>
                {restoring ? 'Restoring…' : 'Confirm Restore'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
