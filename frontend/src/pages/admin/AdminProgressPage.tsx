import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMajorContext } from '../../lib/MajorContext'
import {
  useProgressStatus,
  useProgressAssignmentTypes,
  useProgressAssignments,
} from '../../lib/hooks'
import { resetProgressAssignments } from '../../lib/api'

export function AdminProgressPage() {
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const qc = useQueryClient()
  const status = useProgressStatus(majorCode)
  const typesQuery = useProgressAssignmentTypes(majorCode)
  const assignmentsQuery = useProgressAssignments(majorCode)

  const [resetting, setResetting] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  async function handleReset() {
    if (!window.confirm('Reset ALL student assignments for this major? This cannot be undone.')) return
    setResetting(true)
    setMsg(null)
    try {
      const result = await resetProgressAssignments(majorCode)
      qc.invalidateQueries({ queryKey: ['progress-assignments', majorCode] })
      setMsg({ type: 'success', text: result.message })
    } catch (err: unknown) {
      setMsg({ type: 'error', text: err instanceof Error ? err.message : 'Reset failed.' })
    } finally {
      setResetting(false)
    }
  }

  const s = status.data

  return (
    <section className="stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Admin › Academic Progress</div>
          <h2>Progress Management</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Major:</span>
          <select className="select-input" value={majorCode} onChange={(e) => setMajorCode(e.target.value)}>
            {allowedMajors.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {/* Data status */}
      {s && (
        <div className="grid-2 mb-6">
          <div className={`status-badge-card ${s.progress_report.has_report ? 'status-ok' : 'status-missing'}`}>
            <div className="status-badge-label">Progress Report</div>
            {s.progress_report.has_report ? (
              <>
                <div className="status-badge-value">{s.progress_report.student_count} students</div>
                {s.progress_report.uploaded_at && (
                  <div className="text-muted text-xs mt-1">
                    Uploaded {new Date(s.progress_report.uploaded_at).toLocaleDateString()}
                  </div>
                )}
              </>
            ) : (
              <div className="status-badge-value text-muted">Not uploaded</div>
            )}
          </div>
          <div className={`status-badge-card ${s.course_config.has_config ? 'status-ok' : 'status-missing'}`}>
            <div className="status-badge-label">Course Configuration</div>
            {s.course_config.has_config ? (
              <div className="status-badge-value">
                {s.course_config.required_count} required · {s.course_config.intensive_count} intensive
              </div>
            ) : (
              <div className="status-badge-value text-muted">Not uploaded</div>
            )}
          </div>
        </div>
      )}

      <div className="grid-2">
        {/* Assignment types */}
        <div className="panel stack">
          <div className="panel-header mb-3">
            <h3>Assignment Types</h3>
            <p className="text-muted text-sm">Labels defined for this major.</p>
          </div>
          {typesQuery.isLoading ? (
            <div className="text-muted text-sm">Loading…</div>
          ) : !typesQuery.data?.length ? (
            <div className="text-muted text-sm">None defined. Add them in the <strong>Configure</strong> page.</div>
          ) : (
            <ul className="tag-list">
              {typesQuery.data.map((at) => (
                <li key={at.id} className="tag">{at.label}</li>
              ))}
            </ul>
          )}
        </div>

        {/* Assignments summary + reset */}
        <div className="panel stack">
          <div className="panel-header mb-3">
            <h3>Student Assignments</h3>
            <p className="text-muted text-sm">
              Total assignments saved across all students for this major.
            </p>
          </div>
          {assignmentsQuery.isLoading ? (
            <div className="text-muted text-sm">Loading…</div>
          ) : (
            <>
              <div className="font-semibold mb-3">
                {assignmentsQuery.data?.length ?? 0} assignment{(assignmentsQuery.data?.length ?? 0) !== 1 ? 's' : ''}
              </div>
              {(assignmentsQuery.data?.length ?? 0) > 0 && (
                <>
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={resetting}
                    onClick={handleReset}
                  >
                    {resetting ? 'Resetting…' : 'Reset All Assignments'}
                  </button>
                  {msg && <div className={`alert alert-${msg.type} mt-2`}>{msg.text}</div>}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Assignment list */}
      {(assignmentsQuery.data?.length ?? 0) > 0 && (
        <div className="panel stack mt-4">
          <div className="panel-header mb-3">
            <h3>All Assignments</h3>
          </div>
          <div className="premium-table-wrapper">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Student ID</th>
                  <th>Type</th>
                  <th>Course</th>
                </tr>
              </thead>
              <tbody>
                {assignmentsQuery.data!.map((a) => (
                  <tr key={a.id}>
                    <td>{a.student_id}</td>
                    <td>{a.assignment_type}</td>
                    <td>{a.course_code}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
