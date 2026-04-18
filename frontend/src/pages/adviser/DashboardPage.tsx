import { useDashboard } from '../../lib/hooks'
import { useMajorContext } from '../../lib/MajorContext'
import { StatCard } from '../../components/StatCard'
import { useNavigate } from 'react-router-dom'

export function DashboardPage() {
  const navigate = useNavigate()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const dashboard = useDashboard(majorCode)

  return (
    <section className="dashboard-container stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Adviser Interface</div>
          <h2>Overview Dashboard</h2>
        </div>
        <div className="header-actions">
          <label className="inline-select">
            <span className="text-muted">Master Program:</span>
            <select className="select-input" value={majorCode} onChange={(event) => setMajorCode(event.target.value)}>
              {allowedMajors.map((major) => <option key={major.code} value={major.code}>{major.code}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="stats-grid mb-6">
        <StatCard label="Total Students" value={dashboard.data?.total_students ?? 0} detail="Loaded from active dataset" />
        <StatCard label="Advised" value={dashboard.data?.advised_students ?? 0} detail="Saved in active period" />
        <StatCard label="Not Advised" value={dashboard.data?.not_advised_students ?? 0} detail="Still pending" />
        <StatCard label="Progress" value={`${dashboard.data?.progress_percent ?? 0}%`} detail="Roster completion" />
      </div>

      <div className="grid-2">
        <div className="panel stack">
          <div className="panel-header mb-4">
            <h3>Graduating Soon (Not Advised)</h3>
            <p className="text-muted text-sm">Students requiring immediate attention for graduation clearance.</p>
          </div>

          {(!dashboard.data?.graduating_soon_unadvised || dashboard.data.graduating_soon_unadvised.length === 0) ? (
            <div className="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-muted mb-4"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
              <p>All graduating students have been advised.</p>
            </div>
          ) : (
            <div className="premium-table-wrapper">
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Student Name</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.data.graduating_soon_unadvised.map((student) => (
                    <tr key={student.student_id}>
                      <td className="font-semibold">{student.student_name}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => navigate(`/adviser/workspace?student_id=${encodeURIComponent(student.student_id)}&major=${encodeURIComponent(majorCode)}`)}
                        >
                          Advise Now
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="panel stack">
          <div className="panel-header mb-4">
            <h3>Recent Activity</h3>
            <p className="text-muted text-sm">Latest session updates and student selections.</p>
          </div>

          {(!dashboard.data?.recent_activity || dashboard.data.recent_activity.length === 0) ? (
            <div className="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-muted mb-4"><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
              <p>No activity recorded in this period yet.</p>
            </div>
          ) : (
            <ul className="activity-feed">
              {dashboard.data.recent_activity.map((item) => (
                <li key={item.created_at} className="activity-item">
                  <div className="activity-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
                  </div>
                  <div className="activity-content">
                    <strong>{item.student_name}</strong>
                    <span className="activity-time">{new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.created_at))}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Credit Distribution */}
      {dashboard.data?.credit_distribution && dashboard.data.credit_distribution.length > 0 && (() => {
        const maxCount = Math.max(...dashboard.data.credit_distribution.map((b) => b.count), 1)
        return (
          <div className="panel stack">
            <div className="panel-header mb-4">
              <h3>Credit Distribution</h3>
              <p className="text-muted text-sm">Remaining credits across all enrolled students.</p>
            </div>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', padding: '0 8px' }}>
              {dashboard.data.credit_distribution.map((bucket) => {
                const pct = Math.round((bucket.count / maxCount) * 100)
                const color = bucket.label === '≤18' ? '#22c55e' : bucket.label === '19–36' ? '#f59e0b' : bucket.label === '37–72' ? '#94a3b8' : '#64748b'
                return (
                  <div key={bucket.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>{bucket.count}</span>
                    <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '6px 6px 0 0', height: '80px', display: 'flex', alignItems: 'flex-end', overflow: 'hidden' }}>
                      <div style={{ width: '100%', height: `${Math.max(pct, 4)}%`, background: color, transition: 'height 0.4s ease', borderRadius: '6px 6px 0 0' }} />
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>{bucket.label} cr</span>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}
    </section>
  )
}
