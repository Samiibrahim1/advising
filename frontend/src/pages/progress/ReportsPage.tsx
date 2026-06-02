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

// ─── Sort types + helpers ────────────────────────────────────────
type SortKey = 'id' | 'name' | 'major' | 'done' | 'reg' | 'rem'

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  return (
    <span style={{ marginLeft: 3, opacity: active ? 1 : 0.3, fontSize: '0.7em' }}>
      {active ? (dir === 'asc' ? '▲' : '▼') : '▲▼'}
    </span>
  )
}

function sortRows(rows: StudentProgressRow[], sortBy: SortKey, sortDir: 'asc' | 'desc'): StudentProgressRow[] {
  return [...rows].sort((a, b) => {
    let cmp = 0
    switch (sortBy) {
      case 'id':   cmp = a.student_id.localeCompare(b.student_id); break
      case 'name': cmp = a.name.localeCompare(b.name); break
      case 'major': cmp = (a.major ?? '').localeCompare(b.major ?? ''); break
      case 'done': cmp = a.completed_credits - b.completed_credits; break
      case 'reg':  cmp = a.registered_credits - b.registered_credits; break
      case 'rem':  cmp = a.remaining_credits - b.remaining_credits; break
    }
    return sortDir === 'desc' ? -cmp : cmp
  })
}

// ─── Progress Table ──────────────────────────────────────────────
function ProgressTable({
  title,
  rows,
  courses,
  onStudentClick,
  collapseMode,
  sortBy,
  sortDir,
  onSort,
}: {
  title: string
  rows: StudentProgressRow[]
  courses: string[]
  onStudentClick: (id: string) => void
  collapseMode: boolean
  sortBy: SortKey | null
  sortDir: 'asc' | 'desc'
  onSort: (key: SortKey) => void
}) {
  if (rows.length === 0) return null

  const sortableTh = (key: SortKey, label: string, minWidth: number) => (
    <th
      style={{ minWidth, cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
      onClick={() => onSort(key)}
    >
      {label} <SortIcon active={sortBy === key} dir={sortDir} />
    </th>
  )

  return (
    <div className="panel stack mb-6">
      <div className="panel-header mb-3">
        <h3>{title}</h3>
      </div>
      <div className="premium-table-wrapper" style={{ overflowX: 'auto' }}>
        <table className="premium-table progress-report-table">
          <thead>
            <tr>
              {sortableTh('id', 'ID', 90)}
              {sortableTh('name', 'Name', 160)}
              {sortableTh('major', 'Major', 120)}
              {courses.map((c) => <th key={c} style={{ minWidth: 70 }}>{c}</th>)}
              {sortableTh('done', 'Done', 60)}
              {sortableTh('reg', 'Reg', 60)}
              {sortableTh('rem', 'Rem', 60)}
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
                <td>{row.major || '—'}</td>
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
  const [pageSize, setPageSize] = useState<50 | 100 | 500>(50)
  const [sortBy, setSortBy] = useState<SortKey | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [maxRem, setMaxRem] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)

  function handleSort(key: SortKey) {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(key)
      setSortDir('asc')
    }
  }
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
    pageSize,
    search: deferredSearch,
  })

  const report = reportQuery.data
  const requiredCourses = report?.required[0] ? Object.keys(report.required[0].courses) : []
  const intensiveCourses = report?.intensive[0] ? Object.keys(report.intensive[0].courses) : []
  const totalPages = report ? Math.ceil(report.total_students / pageSize) : 1

  // Apply Rem ≤ filter then sort — client-side on the loaded page
  const maxRemNum = maxRem !== '' ? parseInt(maxRem, 10) : null
  let requiredRows = report?.required ?? []
  let intensiveRows = report?.intensive ?? []

  if (maxRemNum !== null && !isNaN(maxRemNum)) {
    requiredRows = requiredRows.filter((r) => r.remaining_credits <= maxRemNum)
    const allowedIds = new Set(requiredRows.map((r) => r.student_id))
    intensiveRows = intensiveRows.filter((r) => allowedIds.has(r.student_id))
  }

  if (sortBy !== null) {
    requiredRows = sortRows(requiredRows, sortBy, sortDir)
    const intMap = new Map(intensiveRows.map((r) => [r.student_id, r]))
    intensiveRows = requiredRows.flatMap((r) => (intMap.has(r.student_id) ? [intMap.get(r.student_id)!] : []))
  }

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

        <label className="inline-select" title="Filter by remaining credits">
          <span className="text-muted text-sm" style={{ whiteSpace: 'nowrap' }}>Rem ≤</span>
          <input
            type="number"
            className="text-input"
            placeholder="—"
            value={maxRem}
            min={0}
            onChange={(e) => setMaxRem(e.target.value)}
            style={{ width: 64 }}
          />
        </label>

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
          <label className="inline-select" title="Rows per page">
            <span className="text-muted text-sm">Show</span>
            <select
              className="select-input"
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value) as 50 | 100 | 500); setPage(1) }}
              style={{ width: 72 }}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>All</option>
            </select>
          </label>
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
            rows={requiredRows}
            courses={requiredCourses}
            onStudentClick={(id) => navigate(`/progress/students?id=${encodeURIComponent(id)}`)}
            collapseMode={collapseMode}
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={handleSort}
          />
          <ProgressTable
            title="Intensive Courses"
            rows={intensiveRows}
            courses={intensiveCourses}
            onStudentClick={(id) => navigate(`/progress/students?id=${encodeURIComponent(id)}`)}
            collapseMode={collapseMode}
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={handleSort}
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
