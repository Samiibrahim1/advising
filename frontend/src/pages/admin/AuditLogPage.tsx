import { useState } from 'react'

import { useAuditLog } from '../../lib/hooks'

const EVENT_FILTERS = [
  { label: 'All Events', value: '' },
  { label: 'Email Sends', value: 'email' },
  { label: 'Dataset Uploads', value: 'dataset' },
  { label: 'Period Changes', value: 'period' },
  { label: 'User Changes', value: 'user' },
  { label: 'Sessions', value: 'session' },
]

const EVENT_COLORS: Record<string, { bg: string; color: string }> = {
  'email.sent':        { bg: '#eff6ff', color: '#1d4ed8' },
  'dataset.uploaded':  { bg: '#f0fdf4', color: '#15803d' },
  'period.created':    { bg: '#fef9c3', color: '#854d0e' },
  'period.activated':  { bg: '#fef9c3', color: '#854d0e' },
  'user.created':      { bg: '#fdf4ff', color: '#7e22ce' },
  'user.deactivated':  { bg: '#fef2f2', color: '#dc2626' },
  'user.activated':    { bg: '#f0fdf4', color: '#15803d' },
  'session.restored':  { bg: '#f1f5f9', color: '#475569' },
}

function eventBadge(eventType: string) {
  const style = EVENT_COLORS[eventType] ?? { bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '5px', fontWeight: 600, background: style.bg, color: style.color, whiteSpace: 'nowrap' }}>
      {eventType}
    </span>
  )
}

export function AuditLogPage() {
  const [filterType, setFilterType] = useState('')
  const [search, setSearch] = useState('')
  const events = useAuditLog(filterType || undefined)

  const filtered = (events.data ?? []).filter(e => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      e.event_type.toLowerCase().includes(q) ||
      e.entity_id.toLowerCase().includes(q) ||
      (e.actor_name ?? '').toLowerCase().includes(q) ||
      JSON.stringify(e.payload).toLowerCase().includes(q)
    )
  })

  return (
    <section className="stack" style={{ maxWidth: '1100px', margin: '0 auto' }}>
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Audit Log</h2>
        </div>
        <span className="badge badge-info">{events.data?.length ?? 0} events</span>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {EVENT_FILTERS.map(f => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilterType(f.value)}
              style={{ padding: '0.35rem 0.75rem', borderRadius: '20px', border: `1px solid ${filterType === f.value ? 'var(--accent)' : 'var(--line)'}`, background: filterType === f.value ? 'var(--accent)' : 'transparent', color: filterType === f.value ? 'white' : 'var(--ink)', fontSize: '0.8rem', cursor: 'pointer', fontWeight: filterType === f.value ? 600 : 400 }}
            >
              {f.label}
            </button>
          ))}
        </div>
        <input type="search" className="search-input" placeholder="Search actor, entity, payload…" value={search} onChange={e => setSearch(e.target.value)} style={{ marginLeft: 'auto', width: '260px' }} />
      </div>

      <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        {events.isLoading ? (
          <p className="text-muted text-sm" style={{ padding: '2rem', textAlign: 'center' }}>Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="text-muted text-sm" style={{ padding: '2.5rem', textAlign: 'center' }}>No events found.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th style={{ width: '170px' }}>Time</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Entity</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(e => (
                  <tr key={e.id}>
                    <td style={{ fontSize: '0.8rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                      {new Date(e.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td>{eventBadge(e.event_type)}</td>
                    <td style={{ fontSize: '0.875rem' }}>{e.actor_name ?? <span style={{ color: 'var(--muted)' }}>System</span>}</td>
                    <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                      <span style={{ color: 'var(--muted)' }}>{e.entity_type}/</span>{e.entity_id}
                    </td>
                    <td style={{ fontSize: '0.78rem', color: 'var(--muted)', maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {Object.entries(e.payload).map(([k, v]) => `${k}: ${v}`).join(' · ') || '—'}
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
