import { useState, useDeferredValue } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMajorContext } from '../../lib/MajorContext'
import { useProgressReport } from '../../lib/hooks'
import { apiFetch, progressExportPath, pushProgressToAdvising, createPeriod, type StudentProgressRow } from '../../lib/api'

// ─── Collapse pass/fail helper ───────────────────────────────────
// Returns 'c' (completed), 'cr' (currently registered), 'nc' (not completed)
function collapsePassFail(val: string): 'c' | 'cr' | 'nc' {
  if (!val || val === 'NR') return 'nc'
  if (val.toUpperCase().startsWith('CR')) return 'cr'
  const entries = val.split(',').map((e) => e.trim())
  for (const e of entries) {
    if (e.toUpperCase().startsWith('CR')) return 'cr'
  }
  for (const e of entries) {
    const parts = e.split('|')
    if (parts.length === 2) {
      const right = parts[1].trim().toUpperCase()
      const n = parseInt(right, 10)
      if (!isNaN(n) && n > 0) return 'c'
      if (right === 'PASS') return 'c'
      if (right === 'FAIL' || n === 0) return 'nc'
    }
  }
  return 'nc'
}

// ─── Grade cell CSS class (full mode) ───────────────────────────
function gradeCellClass(val: string): string {
  if (!val || val === 'NR') return 'grade-cell grade-cell--empty'
  if (val.toUpperCase().startsWith('CR')) return 'grade-cell grade-cell--progress'
  const entries = val.split(',').map((e) => e.trim())
  for (const e of entries) {
    if (e.toUpperCase().startsWith('CR')) return 'grade-cell grade-cell--progress'
  }
  for (const e of entries) {
    const parts = e.split('|')
    if (parts.length === 2) {
      const right = parts[1].trim().toUpperCase()
      const n = parseInt(right, 10)
      if ((!isNaN(n) && n > 0) || right === 'PASS') return 'grade-cell grade-cell--passed'
    }
  }
  return 'grade-cell grade-cell--failed'
}

// ─── Progress Table ──────────────────────────────────────────────
function ProgressTable({
  title,
  rows,
  courses,
  onStudentClick,
  collapseMode,
}: {
  title: string
  rows: StudentProgressRow[]
  courses: string[]
  onStudentClick: (id: string) => void
  collapseMode: boolean
}) {
  if (rows.length === 0) return null

  return (
    <div className="panel stack mb-6">
      <div className="panel-header mb-3">
        <h3>{title}</h3>
      </div>
      <div className="premium-table-wrapper" style={{ overflowX: 'auto' }}>
        <table className="premium-table progress-report-table">
          <thead>
            <tr>
              <th style={{ minWidth: 90 }}>ID</th>
              <th style={{ minWidth: 160 }}>Name</th>
              {courses.map((c) => <th key={c} style={{ minWidth: 70 }}>{c}</th>)}
              <th style={{ minWidth: 60 }}>Done</th>
              <th style={{ minWidth: 60 }}>Reg</th>
              <th style={{ minWidth: 60 }}>Rem</th>
              <th style={{ minWidth: 55 }}>GPA</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.student_id}>
                <td>
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => onStudentClick(row.student_id)}
                  >
                    {row.student_id}
                  </button>
                </td>
                <td>{row.name}</td>
                {courses.map((c) => {
                  const raw = row.courses[c] ?? 'NR'
                  if (collapseMode) {
                    const collapsed = collapsePassFail(raw)
                    return (
                      <td key={c} title={raw} style={{ textAlign: 'center', padding: '0.3rem 0.4rem' }}>
                        <span className={`grade-cell grade-cell--${collapsed}`}>{collapsed}</span>
                      </td>
                    )
                  }
                  return (
                    <td key={c} title={raw} style={{ textAlign: 'center', padding: '0.3rem 0.4rem' }}>
                      <span className={gradeCellClass(raw)}>{raw === 'NR' ? '—' : raw}</span>
                    </td>
                  )
                })}
                <td style={{ textAlign: 'right' }}>{row.completed_credits}</td>
                <td style={{ textAlign: 'right' }}>{row.registered_credits}</td>
                <td style={{ textAlign: 'right' }}>{row.remaining_credits}</td>
                <td style={{ textAlign: 'right' }}>{row.gpa != null ? row.gpa.toFixed(2) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────
export function ReportsPage() {
  const navigate = useNavigate()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const [showAllGrades, setShowAllGrades] = useState(false)
  const [collapseMode, setCollapseMode] = useState(false)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [exporting, setExporting] = useState(false)
  const [pushing, setPushing] = useState(false)
  const [pushMsg, setPushMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [pushStudentCount, setPushStudentCount] = useState<number | null>(null)
  const [showNewPeriodForm, setShowNewPeriodForm] = useState(false)
  const [newSemester, setNewSemester] = useState('Fall')
  const [newYear, setNewYear] = useState(new Date().getFullYear())
  const [newAdvisorName, setNewAdvisorName] = useState('')
  const [creatingPeriod, setCreatingPeriod] = useState(false)
  const [periodMsg, setPeriodMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await apiFetch<Blob>(progressExportPath(majorCode, showAllGrades, collapseMode))
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `progress_${majorCode}${collapseMode ? '_collapsed' : ''}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      // silent — network errors will surface via standard error boundary
    } finally {
      setExporting(false)
    }
  }

  async function handlePushToAdvising() {
    setPushing(true)
    setPushMsg(null)
    setShowNewPeriodForm(false)
    setPeriodMsg(null)
    try {
      const res = await pushProgressToAdvising(majorCode)
      setPushMsg({ ok: true, text: res.message })
      setPushStudentCount(res.student_count ?? null)
      setShowNewPeriodForm(true)
    } catch (err: unknown) {
      setPushMsg({ ok: false, text: err instanceof Error ? err.message : 'Push failed.' })
    } finally {
      setPushing(false)
    }
  }

  async function handleCreatePeriod() {
    setCreatingPeriod(true)
    setPeriodMsg(null)
    try {
      const res = await createPeriod({
        major_code: majorCode,
        semester: newSemester,
        year: newYear,
        advisor_name: newAdvisorName.trim() || 'Adviser',
      })
      setPeriodMsg({ ok: true, text: `Period ${res.period_code} created and activated.` })
      setShowNewPeriodForm(false)
    } catch (err: unknown) {
      setPeriodMsg({ ok: false, text: err instanceof Error ? err.message : 'Could not create period.' })
    } finally {
      setCreatingPeriod(false)
    }
  }

  const reportQuery = useProgressReport(majorCode, {
    showAllGrades,
    page,
    pageSize: 50,
    search: deferredSearch,
  })

  const report = reportQuery.data
  const requiredCourses = report?.required[0] ? Object.keys(report.required[0].courses) : []
  const intensiveCourses = report?.intensive[0] ? Object.keys(report.intensive[0].courses) : []
  const totalPages = report ? Math.ceil(report.total_students / 50) : 1

  function handleSearch(val: string) {
    setSearch(val)
    setPage(1)
  }

  return (
    <section className="stack">
      {/* Page header */}
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Academic Progress</div>
          <h2>Progress Reports</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Major:</span>
          <select className="select-input" value={majorCode} onChange={(e) => { setMajorCode(e.target.value); setPage(1) }}>
            {allowedMajors.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {/* Toolbar / filter bar */}
      <div className="filter-bar mb-5">
        <input
          type="search"
          className="text-input"
          placeholder="Search by ID or name…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          style={{ minWidth: 220, flex: 1 }}
        />

        <button
          type="button"
          className={`toggle-pill${showAllGrades ? ' active' : ''}`}
          onClick={() => { setShowAllGrades((v) => !v); setPage(1) }}
          title="Include all historical attempts in each cell, not just the most recent"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 5v14" /><path d="M5 12l7-7 7 7" />
          </svg>
          All attempts
        </button>

        <button
          type="button"
          className={`toggle-pill${collapseMode ? ' active' : ''}`}
          onClick={() => setCollapseMode((v) => !v)}
          title="Show c (completed) / cr (registered) / nc (not completed) instead of raw grades"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <circle cx="12" cy="12" r="3" />
            <path d="M20.188 10.934c.2.646.312 1.338.312 2.066s-.112 1.42-.312 2.066M12 3.812c-.728 0-1.42.112-2.066.312" />
          </svg>
          Collapse c/cr/nc
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {report && (
            <span className="text-muted text-sm">
              {report.total_students} student{report.total_students !== 1 ? 's' : ''}
            </span>
          )}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleExport}
            disabled={exporting}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {exporting ? 'Exporting…' : 'Export'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handlePushToAdvising}
            disabled={pushing}
            title="Generate collapsed c/cr/nc report and push it to the Advising app as the progress dataset"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M22 2L11 13" /><path d="M22 2L15 22l-4-9-9-4 20-7z" />
            </svg>
            {pushing ? 'Pushing…' : 'Push to Advising'}
          </button>
        </div>
      </div>

      {/* Push-to-advising feedback + new period prompt */}
      {pushMsg && (
        <div className={`inline-alert ${pushMsg.ok ? 'inline-alert--success' : 'inline-alert--error'} mb-3`}>
          {pushMsg.text}
        </div>
      )}
      {showNewPeriodForm && (
        <div className="panel stack mb-4" style={{ padding: '1rem 1.25rem' }}>
          <p className="text-sm mb-3" style={{ fontWeight: 600 }}>
            Start a new advising period{pushStudentCount != null ? ` for ${pushStudentCount} students` : ''}?
          </p>
          <div className="flex-row gap-3 align-center" style={{ flexWrap: 'wrap' }}>
            <select
              className="select-input"
              value={newSemester}
              onChange={(e) => setNewSemester(e.target.value)}
              style={{ minWidth: 110 }}
            >
              <option>Fall</option>
              <option>Spring</option>
              <option>Summer</option>
            </select>
            <input
              type="number"
              className="text-input"
              value={newYear}
              onChange={(e) => setNewYear(Number(e.target.value))}
              style={{ width: 90 }}
            />
            <input
              type="text"
              className="text-input"
              placeholder="Adviser name (optional)"
              value={newAdvisorName}
              onChange={(e) => setNewAdvisorName(e.target.value)}
              style={{ minWidth: 180 }}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleCreatePeriod}
              disabled={creatingPeriod}
            >
              {creatingPeriod ? 'Creating…' : 'Create & Activate Period'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowNewPeriodForm(false)}
            >
              Skip
            </button>
          </div>
        </div>
      )}
      {periodMsg && (
        <div className={`inline-alert ${periodMsg.ok ? 'inline-alert--success' : 'inline-alert--error'} mb-3`}>
          {periodMsg.text}
        </div>
      )}

      {/* Legend when in collapse mode */}
      {collapseMode && (
        <div className="flex-row gap-3 mb-4 align-center" style={{ flexWrap: 'wrap' }}>
          <span className="text-muted text-sm" style={{ fontWeight: 600 }}>Legend:</span>
          <span className="grade-cell grade-cell--c">c</span>
          <span className="text-sm">Completed</span>
          <span className="grade-cell grade-cell--cr">cr</span>
          <span className="text-sm">Currently Registered</span>
          <span className="grade-cell grade-cell--nc">nc</span>
          <span className="text-sm">Not Completed</span>
        </div>
      )}

      {/* Content */}
      {reportQuery.isLoading ? (
        <div className="loading-screen">Generating report…</div>
      ) : reportQuery.isError ? (
        <div className="alert alert-error">
          {reportQuery.error instanceof Error ? reportQuery.error.message : 'Failed to load report.'}
          <br />
          <span className="text-sm">Make sure both a progress report and course configuration have been uploaded.</span>
        </div>
      ) : report ? (
        <>
          <ProgressTable
            title="Required Courses"
            rows={report.required}
            courses={requiredCourses}
            onStudentClick={(id) => navigate(`/progress/students?id=${encodeURIComponent(id)}`)}
            collapseMode={collapseMode}
          />
          <ProgressTable
            title="Intensive Courses"
            rows={report.intensive}
            courses={intensiveCourses}
            onStudentClick={(id) => navigate(`/progress/students?id=${encodeURIComponent(id)}`)}
            collapseMode={collapseMode}
          />

          {report.extra_courses.length > 0 && (
            <div className="panel stack">
              <div className="panel-header mb-2">
                <h3>Extra Courses</h3>
                <p className="text-muted text-sm">
                  Courses in the progress report not found in the course configuration.
                  These can be assigned to students in the Students view.
                </p>
              </div>
              <div className="flex-row gap-2" style={{ flexWrap: 'wrap' }}>
                {report.extra_courses.map((c) => (
                  <span key={c} className="tag">{c}</span>
                ))}
              </div>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex-between mt-4">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </button>
              <span className="text-muted text-sm">Page {page} of {totalPages}</span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="blank-slate-panel">
          <div className="blank-slate-content">
            <p className="text-muted">No data to display. Upload a progress report and course configuration first.</p>
          </div>
        </div>
      )}
    </section>
  )
}

