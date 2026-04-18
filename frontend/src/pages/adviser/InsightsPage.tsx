import { ChangeEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  API_BASE_URL,
  AllStudentsInsightsResponse,
  CourseOfferingRecommendation,
  PlannerSelectionState,
  QAARow,
  ScheduleConflictRow,
  apiFetch,
} from '../../lib/api'
import { useStudents } from '../../lib/hooks'
import { useMajorContext } from '../../lib/MajorContext'
import { Tooltip } from '../../components/Tooltip'

type InsightTab = 'all' | 'qaa' | 'conflicts' | 'planner'
type MatrixTab = 'required' | 'intensive' | 'all-courses'

function getSelectedValues(event: ChangeEvent<HTMLSelectElement>) {
  return Array.from(event.target.selectedOptions).map((option) => option.value)
}

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

function summarizeStatuses(rows: AllStudentsInsightsResponse['rows'], courseCode: string) {
  const counts: Record<string, number> = {}
  rows.forEach((row) => {
    const code = row.courses[courseCode]
    if (!code) return
    counts[code] = (counts[code] || 0) + 1
  })
  return Object.entries(counts)
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([code, count]) => `${code}:${count}`)
    .join(' | ')
}

export function InsightsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const [tab, setTab] = useState<InsightTab>(() => {
    const t = searchParams.get('tab')
    return (t === 'planner' || t === 'qaa' || t === 'conflicts' || t === 'all') ? t as InsightTab : 'all'
  })
  const [matrixTab, setMatrixTab] = useState<MatrixTab>('required')
  const [graduatingThreshold, setGraduatingThreshold] = useState(36)
  const [targetGroups, setTargetGroups] = useState(10)
  const [maxCoursesPerGroup, setMaxCoursesPerGroup] = useState(10)
  const [minStudents, setMinStudents] = useState(1)
  const [minCourses, setMinCourses] = useState(2)
  const [remainingMin, setRemainingMin] = useState<number | ''>('')
  const [remainingMax, setRemainingMax] = useState<number | ''>('')
  const [semesterFilter, setSemesterFilter] = useState('All Courses')
  const [pendingSimulatedCourses, setPendingSimulatedCourses] = useState<string[]>([])
  const [appliedSimulatedCourses, setAppliedSimulatedCourses] = useState<string[]>([])
  const [requiredColumns, setRequiredColumns] = useState<string[]>([])
  const [intensiveColumns, setIntensiveColumns] = useState<string[]>([])
  const [showAllRows, setShowAllRows] = useState(false)
  const [nameSearch, setNameSearch] = useState('')
  const [notAdvisedOnly, setNotAdvisedOnly] = useState(false)
  const [sortKey, setSortKey] = useState<'student_name' | 'remaining_credits' | 'standing' | 'missed' | 'advising_status' | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [simExpanded, setSimExpanded] = useState(false)
  const [plannerThreshold, setPlannerThreshold] = useState(30)
  const [plannerMinEligible, setPlannerMinEligible] = useState(3)
  const [plannerSelection, setPlannerSelection] = useState<string[]>([])
  const [plannerMessage, setPlannerMessage] = useState('')
  const [pageMessage, setPageMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const allStudentsSearch = useStudents(majorCode, '')

  const allStudents = useQuery({
    queryKey: ['all-students', majorCode, semesterFilter, appliedSimulatedCourses],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('semester_filter', semesterFilter)
      appliedSimulatedCourses.forEach((course) => params.append('simulated_courses', course))
      return apiFetch<AllStudentsInsightsResponse>(`/insights/${majorCode}/all-students?${params.toString()}`)
    },
  })

  const planner = useQuery({
    queryKey: ['planner', majorCode, plannerThreshold, plannerMinEligible],
    queryFn: () => apiFetch<CourseOfferingRecommendation[]>(`/insights/${majorCode}/course-planner?graduation_threshold=${plannerThreshold}&min_eligible_students=${plannerMinEligible}`),
  })

  const plannerState = useQuery({
    queryKey: ['planner-state', majorCode],
    queryFn: () => apiFetch<PlannerSelectionState>(`/insights/${majorCode}/course-planner-state`),
  })

  const qaa = useQuery({
    queryKey: ['qaa', majorCode, graduatingThreshold],
    queryFn: () => apiFetch<QAARow[]>(`/insights/${majorCode}/qaa?graduating_threshold=${graduatingThreshold}`),
  })

  const conflicts = useQuery({
    queryKey: ['schedule-conflicts', majorCode, targetGroups, maxCoursesPerGroup, minStudents, minCourses],
    queryFn: () => apiFetch<ScheduleConflictRow[]>(`/insights/${majorCode}/schedule-conflicts?target_groups=${targetGroups}&max_courses_per_group=${maxCoursesPerGroup}&min_students=${minStudents}&min_courses=${minCourses}`),
  })

  useEffect(() => {
    if (!plannerState.data) return
    setPlannerThreshold(plannerState.data.graduation_threshold)
    setPlannerMinEligible(plannerState.data.min_eligible_students)
    setPlannerSelection(plannerState.data.selected_courses)
  }, [majorCode, plannerState.data])

  useEffect(() => {
    if (!allStudents.data) return
    setPendingSimulatedCourses(allStudents.data.simulated_courses)
  }, [majorCode, allStudents.data])

  useEffect(() => {
    if (!allStudents.data) return
    setRequiredColumns((current) => {
      const next = current.filter((course) => allStudents.data.required_courses.includes(course))
      return next.length ? next : allStudents.data.required_courses
    })
    setIntensiveColumns((current) => {
      const next = current.filter((course) => allStudents.data.intensive_courses.includes(course))
      return next.length ? next : allStudents.data.intensive_courses
    })
  }, [allStudents.data])

  const filteredRows = useMemo(() => {
    const rows = allStudents.data?.rows ?? []
    return rows.filter((row) => {
      if (remainingMin !== '' && row.remaining_credits < remainingMin) return false
      if (remainingMax !== '' && row.remaining_credits > remainingMax) return false
      if (notAdvisedOnly && row.advising_status === 'Advised') return false
      if (nameSearch) {
        const q = nameSearch.toLowerCase()
        if (!row.student_name.toLowerCase().includes(q) && !row.student_id.includes(nameSearch)) return false
      }
      return true
    })
  }, [allStudents.data?.rows, remainingMax, remainingMin, nameSearch, notAdvisedOnly])

  const matrixColumns = matrixTab === 'all-courses' ? Object.keys(allStudents.data?.course_metadata ?? {}) : matrixTab === 'required' ? requiredColumns : intensiveColumns
  const matrixOptions = matrixTab === 'all-courses' ? Object.keys(allStudents.data?.course_metadata ?? {}) : matrixTab === 'required' ? (allStudents.data?.required_courses ?? []) : (allStudents.data?.intensive_courses ?? [])

  const sortedRows = useMemo(() => {
    if (!sortKey) return filteredRows
    const cols = matrixTab === 'all-courses' ? Object.keys(allStudents.data?.course_metadata ?? {}) : matrixTab === 'required' ? requiredColumns : intensiveColumns
    return [...filteredRows].sort((a, b) => {
      let valA: number | string
      let valB: number | string
      if (sortKey === 'remaining_credits') {
        valA = a.remaining_credits
        valB = b.remaining_credits
      } else if (sortKey === 'missed') {
        valA = cols.filter((c) => a.courses[c] === 'na').length
        valB = cols.filter((c) => b.courses[c] === 'na').length
      } else if (sortKey === 'student_name') {
        valA = a.student_name
        valB = b.student_name
      } else if (sortKey === 'standing') {
        valA = a.standing
        valB = b.standing
      } else {
        valA = a.advising_status
        valB = b.advising_status
      }
      if (valA < valB) return sortDir === 'asc' ? -1 : 1
      if (valA > valB) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [filteredRows, sortKey, sortDir, matrixTab, requiredColumns, intensiveColumns, allStudents.data?.course_metadata])

  const visibleRows = showAllRows ? sortedRows : sortedRows.slice(0, 80)

  const plannerImpact = useMemo(() => {
    const selected = new Set(plannerSelection)
    const matching = (planner.data ?? []).filter((item) => selected.has(item.course))
    return {
      eligible: matching.reduce((sum, item) => sum + item.currently_eligible, 0),
      graduating: matching.reduce((sum, item) => sum + item.graduating_students, 0),
    }
  }, [planner.data, plannerSelection])

  function updateMatrixColumns(event: ChangeEvent<HTMLSelectElement>) {
    const next = getSelectedValues(event)
    if (matrixTab === 'required') {
      setRequiredColumns(next)
      return
    }
    setIntensiveColumns(next)
  }

  function toggleSort(key: 'student_name' | 'remaining_credits' | 'standing' | 'missed' | 'advising_status') {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function sortIcon(key: 'student_name' | 'remaining_credits' | 'standing' | 'missed' | 'advising_status') {
    if (sortKey !== key) return <span style={{ opacity: 0.3, fontSize: '0.65rem', marginLeft: '3px' }}>⇅</span>
    return <span style={{ fontSize: '0.65rem', marginLeft: '3px' }}>{sortDir === 'asc' ? '▲' : '▼'}</span>
  }

  async function download(path: string, filename: string) {
    const response = await authedFetch(path)
    if (!response.ok) {
      setPageMessage({ type: 'error', text: await response.text() })
      return
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  async function handleSavePlanner() {
    const response = await authedFetch(`/insights/${majorCode}/course-planner-state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selected_courses: plannerSelection,
        graduation_threshold: plannerThreshold,
        min_eligible_students: plannerMinEligible,
      }),
    })
    const body = await response.json().catch(() => null)
    if (!response.ok) {
      setPlannerMessage(body?.detail || 'Planner save failed.')
      return
    }
    setPlannerMessage(`Saved ${body?.selected_courses?.length ?? 0} course offerings.`)
    queryClient.invalidateQueries({ queryKey: ['planner-state', majorCode] })
  }

  return (
    <section className="insights-container stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Data Intelligence</div>
          <h2>Actionable Insights</h2>
        </div>
        <div className="header-actions">
          <label className="inline-select">
            <span className="text-muted">Master Program:</span>
            <select className="select-input" value={majorCode} onChange={(event) => {
              setMajorCode(event.target.value)
              setSemesterFilter('All Courses')
              setPendingSimulatedCourses([])
              setAppliedSimulatedCourses([])
              setPageMessage(null)
            }}>
              {allowedMajors.map((major) => <option key={major.code} value={major.code}>{major.code}</option>)}
            </select>
          </label>
        </div>
      </div>

      {pageMessage && (
        <div className={`alert mb-4 ${pageMessage.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {pageMessage.text}
          <button type="button" className="close-btn" onClick={() => setPageMessage(null)}>&times;</button>
        </div>
      )}

      <div className="workspace-tabs-nav mb-4">
        <button type="button" className={`tab-btn ${tab === 'all' ? 'active' : ''}`} onClick={() => setTab('all')} title="View the eligibility matrix for all students and run what-if simulations">All Students Report</button>
        <button type="button" className={`tab-btn ${tab === 'planner' ? 'active' : ''}`} onClick={() => setTab('planner')} title="Prioritize which courses to offer this semester based on demand and graduation impact">Course Offering Planner</button>
        <button type="button" className={`tab-btn ${tab === 'qaa' ? 'active' : ''}`} onClick={() => setTab('qaa')} title="Generate QAA-style projections showing advised vs skipped students per course">QAA Projections</button>
        <button type="button" className={`tab-btn ${tab === 'conflicts' ? 'active' : ''}`} onClick={() => setTab('conflicts')} title="Detect groups of courses where many students are eligible for all but can only take some">Schedule Conflicts</button>
      </div>

      {tab === 'all' && (
        <div className="stack">
          {/* Simulation Engine — collapsible */}
          <div className="panel">
            <button
              type="button"
              onClick={() => setSimExpanded((v) => !v)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left' }}
            >
              <span style={{ fontSize: '18px', lineHeight: 1, color: '#64748b', transition: 'transform 0.2s', transform: simExpanded ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block', flexShrink: 0 }}>▶</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <h3 style={{ margin: 0 }}>Simulation Engine</h3>
                {!simExpanded && (
                  <span style={{ fontSize: '0.9rem', color: '#334155', fontWeight: 700 }}>Simulate Course Offering</span>
                )}
              </div>
              {appliedSimulatedCourses.length > 0 && (
                <span style={{ marginLeft: '8px', padding: '2px 10px', background: '#dcfce7', border: '1px solid #bbf7d0', borderRadius: '999px', fontSize: '0.8rem', color: '#166534', fontWeight: 600 }}>
                  Active: {appliedSimulatedCourses.join(', ')}
                </span>
              )}
            </button>

            {simExpanded && (
              <div style={{ marginTop: '16px', display: 'flex', gap: '20px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <div style={{ flex: '1', minWidth: '240px' }}>
                  <p className="text-muted" style={{ margin: '0 0 8px 0' }}>Temporarily mark unoffered courses as offered to project how student eligibility would change.</p>
                  <p className="text-muted" style={{ margin: 0, fontStyle: 'italic' }}>Only courses <strong>not currently offered</strong> appear here — already-offered courses can't be simulated because they're already factored in. Completed/registered courses are also excluded.</p>
                  {planner.data && planner.data.length > 0 && pendingSimulatedCourses.length === 0 && appliedSimulatedCourses.length === 0 && (
                    <div style={{ marginTop: '10px', padding: '8px 12px', background: '#eff6ff', borderRadius: '8px', fontSize: '0.85rem', color: '#1e40af' }}>
                      💡 Try: <strong>{planner.data.slice(0, 3).map(i => i.course).join(', ')}</strong>
                    </div>
                  )}
                </div>
                <select className="select-input" multiple size={5} style={{ flex: '1', minWidth: '200px' }} value={pendingSimulatedCourses} onChange={(event) => setPendingSimulatedCourses(getSelectedValues(event))}>
                  {allStudents.data?.simulation_options.map((course) => <option key={course} value={course}>{course}</option>)}
                </select>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button type="button" className="btn-primary" onClick={() => setAppliedSimulatedCourses(pendingSimulatedCourses)}>Run Simulation</button>
                  <button type="button" className="btn-outline" onClick={() => { setPendingSimulatedCourses([]); setAppliedSimulatedCourses([]) }}>Clear</button>
                </div>
              </div>
            )}
          </div>

          <div className="panel stack mt-4">
            <div className="flex-between items-center mb-4">
              <h3>Global Student Matrix</h3>
              <button type="button" className="btn-secondary" onClick={() => download(`/reports/${majorCode}/all-advised`, 'All_Advised_Students.xlsx')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" /></svg>
                Export Excel
              </button>
            </div>

            <div className="filter-bar">
              <div className="filter-group">
                <label>Min Remaining Cr.</label>
                <input type="number" placeholder={String(allStudents.data?.remaining_range.min ?? 0)} value={remainingMin} onChange={(event) => setRemainingMin(event.target.value ? Number(event.target.value) : '')} />
              </div>
              <div className="filter-group">
                <label>Max Remaining Cr.</label>
                <input type="number" placeholder={String(allStudents.data?.remaining_range.max ?? 0)} value={remainingMax} onChange={(event) => setRemainingMax(event.target.value ? Number(event.target.value) : '')} />
              </div>
              <div className="filter-group">
                <label>Semester Goal</label>
                <select value={semesterFilter} onChange={(event) => setSemesterFilter(event.target.value)}>
                  {allStudents.data?.semester_options.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </div>

              <div className="filter-group">
                <label>Search Student</label>
                <input type="text" placeholder="Name or ID…" value={nameSearch} onChange={(event) => setNameSearch(event.target.value)} />
              </div>

              <div className="filter-group">
                <label>&nbsp;</label>
                <button type="button" className={notAdvisedOnly ? 'btn-primary btn-sm' : 'btn-outline btn-sm'} onClick={() => setNotAdvisedOnly((v) => !v)}>Not Advised Only</button>
              </div>

              <div className="filter-group ml-auto">
                <div className="workspace-tabs-nav p-0 border-none gap-0 scale-90 origin-right">
                  <button type="button" className={`tab-btn bg-white border ${matrixTab === 'all-courses' ? 'active shadow-sm' : ''}`} onClick={() => setMatrixTab('all-courses')}>All Courses</button>
                  <button type="button" className={`tab-btn bg-white border ${matrixTab === 'required' ? 'active shadow-sm' : ''}`} onClick={() => setMatrixTab('required')}>Required</button>
                  <button type="button" className={`tab-btn bg-white border ${matrixTab === 'intensive' ? 'active shadow-sm' : ''}`} onClick={() => setMatrixTab('intensive')}>Intensive</button>
                </div>
              </div>
            </div>

            <div className="legend-row mb-4 p-4 bg-gray-50 rounded-xl text-sm border">
              <span className="font-semibold text-muted mr-4">Legend:</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                {allStudents.data?.legend.map((item) => (
                  <span key={item.code} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <span className={`status-pill status-${item.code}`} style={{ minWidth: '1.75rem', textAlign: 'center', fontWeight: 700, fontSize: '0.7rem' }}>{item.code}</span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>{item.label}</span>
                  </span>
                ))}
              </div>
            </div>

            <div className="flex-between items-end mb-2">
              <p className="text-sm text-muted">Showing {visibleRows.length} of {sortedRows.length} students.</p>
              <button type="button" className="btn-outline btn-sm" onClick={() => setShowAllRows((current) => !current)}>{showAllRows ? 'Show Paginated (80 max)' : 'Show Full List'}</button>
            </div>

            <div className="premium-table-wrapper" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              <table className="premium-table">
                <thead>
                  <tr>
                    <th className="sticky-col z-20 min-w-48 bg-gray-50 border-r cursor-pointer select-none hover:bg-gray-100" onClick={() => toggleSort('student_name')}>Student Name {sortIcon('student_name')}</th>
                    <th>ID</th>
                    <th className="text-center cursor-pointer select-none hover:bg-gray-100" onClick={() => toggleSort('remaining_credits')}>Remaining {sortIcon('remaining_credits')}</th>
                    <th className="text-center cursor-pointer select-none hover:bg-gray-100" onClick={() => toggleSort('standing')}>Standing {sortIcon('standing')}</th>
                    <th className="text-center cursor-pointer select-none hover:bg-gray-100" onClick={() => toggleSort('advising_status')}>Status {sortIcon('advising_status')}</th>
                    <th className="text-center cursor-pointer select-none hover:bg-gray-100" onClick={() => toggleSort('missed')} title="Count of eligible-but-not-chosen (na) courses per student">Missed {sortIcon('missed')}</th>
                    {matrixColumns.map((courseCode) => {
                      const info = allStudents.data?.course_metadata[courseCode]
                      const summary = summarizeStatuses(filteredRows, courseCode)
                      return <th key={courseCode} title={`${info?.title || courseCode}\n${info?.requisites || 'None'}\n${summary}`} className="text-center min-w-24 border-l cursor-help hover:bg-gray-100">{courseCode}</th>
                    })}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.length === 0 ? (
                    <tr><td colSpan={6 + matrixColumns.length} className="text-center p-8 text-muted">No students found matching your filters.</td></tr>
                  ) : (
                    visibleRows.map((item) => {
                      const missedCount = matrixColumns.filter((c) => item.courses[c] === 'na').length
                      return (
                        <tr key={item.student_id} style={{ background: item.remaining_credits <= graduatingThreshold ? 'rgba(251,191,36,0.12)' : undefined }}>
                          <td className="sticky-col bg-white font-medium border-r shadow-[1px_0_0_rgba(0,0,0,0.05)]">
                            <button type="button" style={{ fontWeight: 600, color: 'inherit', padding: 0, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', width: '100%' }} onClick={() => navigate(`/adviser/workspace?student_id=${encodeURIComponent(item.student_id)}&major=${encodeURIComponent(majorCode)}`)}>
                              {item.student_name}
                            </button>
                          </td>
                          <td className="mono text-muted text-sm">{item.student_id}</td>
                          <td className="text-center">{item.remaining_credits}</td>
                          <td className="text-center">{item.standing}</td>
                          <td className="text-center">{item.advising_status}</td>
                          <td className="text-center font-semibold" style={{ color: missedCount > 0 ? '#d97706' : '#94a3b8' }}>{missedCount > 0 ? missedCount : '—'}</td>
                          {matrixColumns.map((courseCode) => (
                            <td key={`${item.student_id}-${courseCode}`} className="text-center border-l bg-gray-50/30">
                              {item.courses[courseCode] ? (
                                <span className={`status-pill status-${item.courses[courseCode]}`}>{item.courses[courseCode]}</span>
                              ) : (
                                <span className="text-gray-300">-</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === 'planner' && (
        <div className="stack">
          <div className="panel">
            <div className="flex-between mb-4">
              <div>
                <h3 style={{ margin: 0 }}>Course Offering Planner <Tooltip text="Ranks every unoffered course by how many students are ready for it, how critical it is for graduation, and how long it has been unavailable." /></h3>
                <p className="text-muted text-sm" style={{ margin: '4px 0 0' }}>Decide which courses to offer based on student demand, bottleneck analysis, and graduation impact. Intensive courses are excluded.</p>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button type="button" className="btn-primary btn-sm" onClick={handleSavePlanner} title="Save the current course selection to the server">Save Plan</button>
                <button type="button" className="btn-outline btn-sm" onClick={() => { setPlannerSelection([]); setPlannerMessage('Selection cleared.') }} title="Deselect all courses">Clear Selection</button>
                <button type="button" className="btn-outline btn-sm" onClick={() => download(`/reports/${majorCode}/all-advised`, `Planner_${majorCode}.xlsx`)}>Export</button>
              </div>
            </div>

            <div className="filter-bar mb-4 p-0 border-none justify-start">
              <div className="filter-group">
                <label>Graduating Threshold (Cr. Remaining) <Tooltip text="Students with this many or fewer credits remaining are counted as 'near graduation'. Lowering this focuses the planner on courses that unlock final-year students." /></label>
                <input type="number" value={plannerThreshold} onChange={(event) => setPlannerThreshold(Number(event.target.value || 30))} />
              </div>
              <div className="filter-group">
                <label>Min Eligible Students</label>
                <input type="number" value={plannerMinEligible} onChange={(event) => setPlannerMinEligible(Number(event.target.value || 3))} />
              </div>
            </div>

            {/* Summary stats */}
            {(() => {
              const meta = allStudents.data?.course_metadata ?? {}
              const items = (planner.data ?? []).filter(item => {
                const m = meta[item.course]
                return !m || m.course_type?.toLowerCase() !== 'intensive'
              })
              const selectedItems = items.filter(item => plannerSelection.includes(item.course))
              const totalEligible = selectedItems.reduce((s, i) => s + i.currently_eligible, 0)
              const totalGrad = selectedItems.reduce((s, i) => s + i.graduating_students, 0)
              return (
                <>
                  {plannerSelection.length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', padding: '12px 16px', background: '#f0fdf4', borderRadius: '10px', border: '1px solid #bbf7d0', marginBottom: '16px' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 700, color: '#166534' }}>{plannerSelection.length}</div>
                        <div style={{ fontSize: '10px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Selected Courses</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 700, color: '#166534' }}>{totalEligible}</div>
                        <div style={{ fontSize: '10px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Students Served</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 700, color: '#166534' }}>{totalGrad}</div>
                        <div style={{ fontSize: '10px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Graduating Impacted</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 700, color: '#166534' }}>{items.length - selectedItems.length}</div>
                        <div style={{ fontSize: '10px', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>Not Selected</div>
                      </div>
                    </div>
                  )}

                  {plannerMessage && <div style={{ padding: '8px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', marginBottom: '12px', fontSize: '12px', color: '#1e40af', fontWeight: 600 }}>{plannerMessage}</div>}

                  <div className="premium-table-wrapper">
                    <table className="premium-table">
                      <thead>
                        <tr>
                          <th style={{ width: '40px' }}></th>
                          <th>Course</th>
                          <th>Priority Score</th>
                          <th>Eligible Students</th>
                          <th>Graduating Students</th>
                          <th>Bottleneck Score</th>
                          <th>Cascading Eligible</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.length === 0 ? (
                          <tr><td colSpan={8} className="text-center p-8 text-muted">No course offering recommendations available. Adjust the thresholds above.</td></tr>
                        ) : (
                          items.map((item) => {
                            const maxScore = Math.max(...items.map(i => i.priority_score), 1)
                            const barPct = Math.round((item.priority_score / maxScore) * 100)
                            const isSelected = plannerSelection.includes(item.course)
                            return (
                              <tr key={item.course} style={{ background: isSelected ? '#f0fdf4' : undefined }}>
                                <td className="text-center">
                                  <input type="checkbox" checked={isSelected} onChange={() => {
                                    setPlannerSelection(prev => prev.includes(item.course) ? prev.filter(c => c !== item.course) : [...prev, item.course])
                                  }} />
                                </td>
                                <td className="font-semibold font-mono">{item.course}</td>
                                <td>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <div style={{ flex: 1, height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                                      <div style={{ height: '100%', width: `${barPct}%`, background: barPct > 70 ? '#22c55e' : barPct > 40 ? '#f59e0b' : '#94a3b8', borderRadius: '4px', transition: 'width 0.3s' }} />
                                    </div>
                                    <span style={{ fontSize: '12px', fontWeight: 600, minWidth: '36px' }}>{item.priority_score.toFixed(1)}</span>
                                  </div>
                                </td>
                                <td className="text-center text-lg font-semibold">{item.currently_eligible}</td>
                                <td className="text-center" style={{ color: item.graduating_students > 0 ? '#dc2626' : undefined, fontWeight: item.graduating_students > 0 ? 700 : undefined }}>{item.graduating_students}</td>
                                <td className="text-center font-mono text-sm">{item.bottleneck_score.toFixed(1)}</td>
                                <td className="text-center font-mono text-sm">{item.cascading_eligible}</td>
                                <td className="text-sm text-muted" style={{ maxWidth: '250px' }}>{item.reason}</td>
                              </tr>
                            )
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {tab === 'qaa' && (
        <div className="stack">
          <div className="filter-bar panel">
            <div className="filter-group">
              <label>Graduating Threshold Level</label>
              <input type="number" value={graduatingThreshold} onChange={(event) => setGraduatingThreshold(Number(event.target.value || 36))} />
            </div>
            <div className="filter-group ml-auto">
              <button type="button" className="btn-secondary" onClick={() => download(`/reports/${majorCode}/qaa?graduating_threshold=${graduatingThreshold}`, `QAA_Sheet_${majorCode}.xlsx`)}>
                Export Workbook
              </button>
            </div>
          </div>          {/* QAA Summary Banner */}
          {qaa.data && qaa.data.length > 0 && (() => {
            const totalCourses = qaa.data.length
            const totalEligible = qaa.data.reduce((s, i) => s + i.eligibility, 0)
            const totalAdvised = qaa.data.reduce((s, i) => s + i.advised, 0)
            const totalSkipped = qaa.data.reduce((s, i) => s + i.skipped_advising, 0)
            const totalSkipGrad = qaa.data.reduce((s, i) => s + i.skipped_graduating, 0)
            return (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', padding: '16px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0', marginBottom: '12px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#0f172a' }}>{totalCourses}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Courses</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#0f172a' }}>{totalEligible}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Eligible</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#22c55e' }}>{totalAdvised}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Advised</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#f59e0b' }}>{totalSkipped}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Skipped Advising</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: totalSkipGrad > 0 ? '#ef4444' : '#0f172a' }}>{totalSkipGrad}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Skipped + Graduating</div>
                </div>
              </div>
            )
          })()}

          <div className="panel premium-table-wrapper">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Course Code</th>
                  <th>Course Name</th>
                  <th>Eligibility</th>
                  <th className="bg-green-50/30">Advised</th>
                  <th className="bg-yellow-50/30">Optional</th>
                  <th className="bg-red-50/30">Not Advised</th>
                  <th className="border-l">Skipped Advising</th>
                  <th className="bg-orange-50/10">Attended + Graduating</th>
                  <th className="bg-red-50/10">Skipped + Graduating</th>
                </tr>
              </thead>
              <tbody>
                {qaa.data?.length === 0 ? (
                  <tr><td colSpan={9} className="text-center p-8 text-muted">No QAA projections generated for this program.</td></tr>
                ) : (
                  qaa.data?.map((item) => (
                    <tr key={item.course_code}>
                      <td className="font-semibold font-mono">{item.course_code}</td>
                      <td className="text-sm text-muted truncate max-w-xs" title={item.course_name}>{item.course_name}</td>
                      <td className="text-center text-lg">{item.eligibility}</td>
                      <td className="text-center font-medium bg-green-50/10">{item.advised}</td>
                      <td className="text-center bg-yellow-50/10">{item.optional}</td>
                      <td className="text-center bg-red-50/10">{item.not_advised}</td>
                      <td className="text-center border-l font-mono text-sm">{item.skipped_advising}</td>
                      <td className="text-center bg-orange-50/5 font-mono text-sm">{item.attended_graduating}</td>
                      <td className="text-center font-mono text-sm" style={{ background: item.skipped_graduating > 0 ? '#fef2f2' : undefined, color: item.skipped_graduating > 0 ? '#dc2626' : undefined, fontWeight: item.skipped_graduating > 0 ? 700 : undefined }}>{item.skipped_graduating}</td>
                    </tr>
                  )))
                }
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'conflicts' && (
        <div className="stack">
          {/* Conflict Summary Card */}
          {conflicts.data && conflicts.data.length > 0 && (() => {
            const totalGroups = conflicts.data.length
            const totalStudents = new Set(conflicts.data.flatMap(i => i.student_ids)).size
            const totalCourses = new Set(conflicts.data.flatMap(i => i.courses)).size
            return (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', padding: '16px', background: '#fefce8', borderRadius: '12px', border: '1px solid #fde68a', marginBottom: '12px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#92400e' }}>{totalGroups}</div>
                  <div style={{ fontSize: '11px', color: '#92400e', textTransform: 'uppercase', fontWeight: 600 }}>Conflict Groups</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#92400e' }}>{totalStudents}</div>
                  <div style={{ fontSize: '11px', color: '#92400e', textTransform: 'uppercase', fontWeight: 600 }}>Affected Students</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: '#92400e' }}>{totalCourses}</div>
                  <div style={{ fontSize: '11px', color: '#92400e', textTransform: 'uppercase', fontWeight: 600 }}>Courses Involved</div>
                </div>
              </div>
            )
          })()}

          <div className="filter-bar panel">
            <div className="filter-group">
              <label>Target Groups Limit</label>
              <input type="number" value={targetGroups} onChange={(event) => setTargetGroups(Number(event.target.value || 10))} />
            </div>
            <div className="filter-group">
              <label>Max Courses / Group</label>
              <input type="number" value={maxCoursesPerGroup} onChange={(event) => setMaxCoursesPerGroup(Number(event.target.value || 10))} />
            </div>
            <div className="filter-group border-l pl-4 ml-2">
              <label>Minimums</label>
              <div className="flex-gap-4">
                <input type="number" placeholder="Students" title="Min Students" className="w-24" value={minStudents} onChange={(event) => setMinStudents(Number(event.target.value || 1))} />
                <input type="number" placeholder="Courses" title="Min Courses" className="w-24" value={minCourses} onChange={(event) => setMinCourses(Number(event.target.value || 2))} />
              </div>
            </div>
            <div className="filter-group ml-auto">
              <button type="button" className="btn-secondary" onClick={() => download(`/reports/${majorCode}/schedule-conflicts?target_groups=${targetGroups}&max_courses_per_group=${maxCoursesPerGroup}&min_students=${minStudents}&min_courses=${minCourses}`, `schedule_conflict_${majorCode}.xlsx`)}>Download Excel</button>
            </div>
          </div>

          <div className="panel premium-table-wrapper">
            <table className="premium-table">
              <thead><tr><th>Conflict Cluster</th><th>At Risk Students</th><th>Courses</th><th>Affected Student Roster</th></tr></thead>
              <tbody>
                {conflicts.data?.length === 0 ? (
                  <tr><td colSpan={4} className="text-center p-8 text-muted">No schedule conflicts detected under the current constraints.</td></tr>
                ) : (
                  conflicts.data?.map((item) => (
                    <tr key={item.group_name}>
                      <td style={{ maxWidth: '300px' }}><div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>{item.courses.map(c => <span key={c} style={{ display: 'inline-block', padding: '2px 8px', background: '#e0e7ff', color: '#3730a3', borderRadius: '12px', fontSize: '11px', fontWeight: 600, fontFamily: 'monospace' }}>{c}</span>)}</div></td>
                      <td className="text-center text-lg font-semibold">{item.student_count}</td>
                      <td className="text-center text-muted">{item.course_count}</td>
                      <td className="text-xs" style={{ maxWidth: '400px' }}>
                        {item.student_ids.slice(0, 8).map(id => {
                          const stu = allStudentsSearch.data?.find(s => s.student_id === id)
                          return <span key={id} style={{ display: 'inline-block', margin: '1px 3px', padding: '1px 6px', background: '#f1f5f9', borderRadius: '4px', fontSize: '10px' }}>{stu ? stu.student_name : id}</span>
                        })}
                        {item.student_ids.length > 8 && <span style={{ fontSize: '10px', color: '#94a3b8' }}> +{item.student_ids.length - 8} more</span>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </section>
  )
}
