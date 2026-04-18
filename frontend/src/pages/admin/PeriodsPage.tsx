import { FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { API_BASE_URL } from '../../lib/api'
import { useMajors, usePeriods } from '../../lib/hooks'

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

export function PeriodsPage() {
  const queryClient = useQueryClient()
  const [majorCode, setMajorCode] = useState('PBHL')
  const [semester, setSemester] = useState('Fall')
  const [year, setYear] = useState(new Date().getFullYear())
  const [advisorName, setAdvisorName] = useState('Default Adviser')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [deletingCode, setDeletingCode] = useState<string | null>(null)
  const majors = useMajors()
  const periods = usePeriods(majorCode)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const response = await authedFetch('/periods', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, semester, year, advisor_name: advisorName }),
    })
    if (!response.ok) {
      setMessage({ type: 'error', text: await response.text() })
      return
    }
    setMessage({ type: 'success', text: 'Period created and set as active.' })
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
  }

  async function handleActivate(periodCode: string) {
    const response = await authedFetch(`/periods/${periodCode}/activate`, { method: 'POST' })
    if (!response.ok) {
      setMessage({ type: 'error', text: await response.text() })
      return
    }
    setMessage({ type: 'success', text: 'Period activated.' })
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
  }

  async function handleDelete(periodCode: string) {
    const response = await authedFetch(`/periods/${majorCode}/${periodCode}`, { method: 'DELETE' })
    setDeletingCode(null)
    if (response.status !== 204 && !response.ok) {
      setMessage({ type: 'error', text: await response.text() })
      return
    }
    setMessage({ type: 'success', text: 'Period deleted.' })
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
  }

  return (
    <section className="stack" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Advising Periods</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Program:</span>
          <select className="select-input" value={majorCode} onChange={(e) => { setMajorCode(e.target.value); setMessage(null) }}>
            {majors.data?.map((m) => <option key={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* Create period form */}
      <form className="panel stack mb-6" onSubmit={handleSubmit}>
        <h3 style={{ margin: 0, marginBottom: '0.75rem' }}>Create New Period</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Semester</label>
            <select className="select-input" value={semester} onChange={(e) => setSemester(e.target.value)}>
              <option>Fall</option>
              <option>Spring</option>
              <option>Summer</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Year</label>
            <input className="select-input" type="number" value={year} min={2020} max={2040} onChange={(e) => setYear(Number(e.target.value))} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Advisor Name</label>
            <input className="select-input" value={advisorName} onChange={(e) => setAdvisorName(e.target.value)} placeholder="Advisor name" />
          </div>
        </div>
        <div>
          <button type="submit" className="btn-primary btn-sm">Create Period</button>
        </div>
      </form>

      {/* Period list */}
      <div className="panel">
        <h3 style={{ margin: '0 0 1rem' }}>Period History</h3>
        {periods.isLoading ? (
          <p className="text-muted text-sm">Loading…</p>
        ) : periods.data?.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No periods created yet for {majorCode}.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Period Code</th>
                  <th>Semester</th>
                  <th>Year</th>
                  <th>Advisor</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {periods.data?.map((period) => (
                  <tr key={period.id}>
                    <td style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'monospace' }}>{period.period_code}</td>
                    <td style={{ fontSize: '0.875rem' }}>{period.semester}</td>
                    <td style={{ fontSize: '0.875rem' }}>{period.year}</td>
                    <td style={{ fontSize: '0.875rem' }}>{period.advisor_name}</td>
                    <td>
                      {period.is_active
                        ? <span style={{ fontSize: '0.7rem', background: '#dcfce7', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>Active</span>
                        : <span style={{ fontSize: '0.7rem', color: 'var(--muted)', padding: '2px 8px' }}>Inactive</span>
                      }
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                        {!period.is_active && (
                          <button type="button" className="btn-sm btn-outline" onClick={() => handleActivate(period.period_code)}>
                            Activate
                          </button>
                        )}
                        {deletingCode === period.period_code ? (
                          <>
                            <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 500 }}>Confirm delete?</span>
                            <button type="button" className="btn-sm" style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer' }} onClick={() => handleDelete(period.period_code)}>
                              Yes, Delete
                            </button>
                            <button type="button" className="btn-sm btn-outline" onClick={() => setDeletingCode(null)}>
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button type="button" className="btn-sm btn-outline" style={{ color: '#ef4444', borderColor: '#fca5a5' }} onClick={() => setDeletingCode(period.period_code)}>
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
