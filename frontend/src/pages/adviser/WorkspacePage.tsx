import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { API_BASE_URL, DegreePlanResponse, SessionSummary, apiFetch } from '../../lib/api'
import { useCourseCatalog, usePeriods, useStudentEligibility, useStudents, useTemplates, useSessions } from '../../lib/hooks'
import { useMajorContext } from '../../lib/MajorContext'

import { StudentProfileHeader } from '../../components/workspace/StudentProfileHeader'
import { CourseSelectionBuilder } from '../../components/workspace/CourseSelectionBuilder'
import { EligibilityTables } from '../../components/workspace/EligibilityTables'
import { ExceptionManagement } from '../../components/workspace/ExceptionManagement'
import { Tooltip } from '../../components/Tooltip'

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

const STATUS_DOT: Record<string, string> = {
  completed: '#22c55e', registered: '#eab308', available: '#3b82f6',
  advised: '#f97316', not_eligible: '#cbd5e1', failed: '#ef4444',
}
const STATUS_BG: Record<string, string> = {
  completed: '#f0fdf4', registered: '#fefce8', available: '#eff6ff',
  advised: '#fff7ed', failed: '#fef2f2',
}
const STATUS_BORDER: Record<string, string> = {
  completed: '#bbf7d0', registered: '#fde68a', available: '#bfdbfe',
  advised: '#fed7aa', failed: '#fecaca',
}

export function WorkspacePage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()

  // Combobox
  const [comboQuery, setComboQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [selectedStudentId, setSelectedStudentId] = useState<string | undefined>()
  const [selectedStudentName, setSelectedStudentName] = useState('')

  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'schedule' | 'academic' | 'exceptions' | 'degree' | 'history'>('schedule')
  const [restoreTarget, setRestoreTarget] = useState<{ id: number; title: string } | null>(null)
  const [viewTarget, setViewTarget] = useState<SessionSummary | null>(null)
  const [restoring, setRestoring] = useState(false)
  const [emailSending, setEmailSending] = useState(false)
  const [templateKey, setTemplateKey] = useState('default')
  const [bypassCourse, setBypassCourse] = useState('')
  const [bypassNote, setBypassNote] = useState('')
  const [excludedCourses, setExcludedCourses] = useState<string[]>([])
  const [originalExcludedCourses, setOriginalExcludedCourses] = useState<string[]>([])
  const [formState, setFormState] = useState({ advised: [] as string[], optional: [] as string[], repeat: [] as string[], note: '' })
  const [recommendPreview, setRecommendPreview] = useState<string[] | null>(null)

  const loadedForStudentRef = useRef<string | undefined>(undefined)

  const majors = allowedMajors
  const periods = usePeriods(majorCode)
  const students = useStudents(majorCode, comboQuery)
  const courseCatalog = useCourseCatalog(majorCode)
  const student = useStudentEligibility(majorCode, selectedStudentId)
  const templates = useTemplates(majorCode)
  const sessions = useSessions(majorCode, undefined, selectedStudentId)
  const activePeriod = periods.data?.find((p) => p.is_active)

  const degreePlan = useQuery({
    queryKey: ['degree-plan', majorCode, selectedStudentId],
    queryFn: () => apiFetch<DegreePlanResponse>(`/insights/${majorCode}/degree-plan/${selectedStudentId}`),
    enabled: Boolean(selectedStudentId),
  })

  useEffect(() => {
    const requestedMajor = searchParams.get('major')
    if (requestedMajor && requestedMajor !== majorCode && allowedMajors.some((major) => major.code === requestedMajor)) {
      setMajorCode(requestedMajor)
    }

    const requestedStudentId = searchParams.get('student_id')
    if (requestedStudentId && requestedStudentId !== selectedStudentId) {
      setSelectedStudentId(requestedStudentId)
      setSelectedStudentName(requestedStudentId)
      setComboQuery('')
      setShowDropdown(false)
      setMessage(null)
    }
  }, [allowedMajors, majorCode, searchParams, selectedStudentId, setMajorCode])

  useEffect(() => {
    if (!student.data) return
    setFormState({
      advised: student.data.selection.advised,
      optional: student.data.selection.optional,
      repeat: student.data.selection.repeat,
      note: student.data.selection.note,
    })
    setExcludedCourses(student.data.excluded_courses)
    if (selectedStudentId !== loadedForStudentRef.current) {
      setOriginalExcludedCourses(student.data.excluded_courses)
      loadedForStudentRef.current = selectedStudentId
    }
  }, [student.data, selectedStudentId])

  useEffect(() => {
    if (templates.data?.length && !templates.data.some((t) => t.template_key === templateKey)) {
      setTemplateKey(templates.data[0].template_key)
    }
  }, [templateKey, templates.data])

  const intensiveCourses = useMemo(
    () => student.data?.eligibility.filter((c) => c.course_type.toLowerCase() === 'intensive') ?? [],
    [student.data],
  )



  function selectStudent(id: string, name: string) {
    setSelectedStudentId(id)
    setSelectedStudentName(name)
    setComboQuery('')
    setShowDropdown(false)
    setMessage(null)
  }

  function handleComboBlur() {
    closeTimer.current = setTimeout(() => setShowDropdown(false), 150)
  }

  async function handleSaveSelection() {
    if (!student.data || !activePeriod) return
    const r = await authedFetch('/advising/selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        major_code: majorCode, period_code: activePeriod.period_code,
        student_id: student.data.student_id, student_name: student.data.student_name, selection: formState,
      }),
    })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Schedule saved.' })
    queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode, selectedStudentId] })
    queryClient.invalidateQueries({ queryKey: ['sessions', majorCode, activePeriod.period_code, selectedStudentId] })
    queryClient.invalidateQueries({ queryKey: ['dashboard', majorCode] })
  }

  async function handleRestoreSnapshot(snapshotId: number) {
    setRestoring(true)
    const r = await authedFetch(`/advising/sessions/${majorCode}/snapshot/${snapshotId}/restore`, { method: 'POST' })
    setRestoring(false)
    setRestoreTarget(null)
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Session restored to active period.' })
    queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode, selectedStudentId] })
    setActiveTab('schedule')
  }

  async function handleDeleteSession(snapshotId: number) {
    if (!confirm('Delete this advising session? This cannot be undone.')) return
    const r = await authedFetch(`/advising/sessions/${majorCode}/snapshot/${snapshotId}`, { method: 'DELETE' })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Session deleted.' })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  async function handleRecommend() {
    if (!selectedStudentId) return
    const r = await apiFetch<{ courses: string[] }>(`/advising/recommendations/${majorCode}/${selectedStudentId}`)
    if (!r.courses.length) { setMessage({ type: 'success', text: 'All available courses are already selected.' }); return }
    setRecommendPreview(r.courses)
  }

  function applyRecommendPreview() {
    if (!recommendPreview) return
    setFormState((cur) => ({
      ...cur,
      advised: Array.from(new Set([...cur.advised, ...recommendPreview])),
      optional: cur.optional.filter((c) => !recommendPreview.includes(c)),
      repeat: cur.repeat.filter((c) => !recommendPreview.includes(c)),
    }))
    setMessage({ type: 'success', text: `Recommended ${recommendPreview.length} courses.` })
    setRecommendPreview(null)
  }

  async function handleDownloadReport() {
    if (!selectedStudentId) return
    const r = await authedFetch(`/reports/${majorCode}/student/${selectedStudentId}`)
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    const blob = await r.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `Advising_${selectedStudentId}.xlsx`
    document.body.appendChild(a); a.click(); a.remove()
    window.URL.revokeObjectURL(url)
  }

  async function handleSendEmail() {
    if (!selectedStudentId) return
    setEmailSending(true)
    try {
      const r = await authedFetch(`/emails/${majorCode}/${selectedStudentId}?template_key=${encodeURIComponent(templateKey)}`, { method: 'POST' })
      const body = await r.json().catch(() => null)
      if (!r.ok) { setMessage({ type: 'error', text: body?.detail || body?.message || `Email failed (${r.status}).` }); return }
      setMessage({ type: 'success', text: body?.message || 'Email sent.' })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Network error sending email.' })
    } finally {
      setEmailSending(false)
    }
  }

  async function handleSavePlacements() {
    if (!selectedStudentId) return
    const r = await authedFetch('/advising/exclusions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, student_ids: [selectedStudentId], course_codes: excludedCourses }),
    })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Intensive placement saved.' })
    setOriginalExcludedCourses(excludedCourses)
    queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode, selectedStudentId] })
  }


  async function handleBypassSave() {
    if (!selectedStudentId || !bypassCourse) return
    const r = await authedFetch('/advising/bypasses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, student_id: selectedStudentId, course_code: bypassCourse, note: bypassNote, advisor_name: activePeriod?.advisor_name || '' }),
    })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setBypassCourse(''); setBypassNote('')
    setMessage({ type: 'success', text: 'Bypass saved.' })
    queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode, selectedStudentId] })
  }

  async function handleBypassDelete(courseCode: string) {
    if (!selectedStudentId) return
    const r = await authedFetch(`/advising/bypasses/${majorCode}/${selectedStudentId}/${courseCode}`, { method: 'DELETE' })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Bypass removed.' })
    queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode, selectedStudentId] })
  }

  return (
    <section className="workspace-container stack">

      {/* Page Header */}
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow text-muted">Adviser Interface</div>
          <h2>Advising Workspace</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Master Program:</span>
          <select className="select-input" value={majorCode} onChange={(e) => {
            setMajorCode(e.target.value)
            setSelectedStudentId(undefined)
            setSelectedStudentName('')
            setComboQuery('')
            setMessage(null)
          }}>
            {majors.map((m) => <option key={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {/* Student Combobox */}
      <div className="student-combobox-wrap">
        <div className="student-combobox-inner">
          <svg className="combobox-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            className="combobox-input"
            placeholder={selectedStudentId ? selectedStudentName : 'Search students by name or ID…'}
            value={comboQuery}
            onChange={(e) => { setComboQuery(e.target.value); setShowDropdown(true) }}
            onFocus={() => { if (closeTimer.current) clearTimeout(closeTimer.current); setShowDropdown(true) }}
            onBlur={handleComboBlur}
          />
          {selectedStudentId && (
            <button
              type="button"
              className="combobox-clear"
              onMouseDown={(e) => { e.preventDefault(); setSelectedStudentId(undefined); setSelectedStudentName(''); setComboQuery(''); setMessage(null) }}
            >
              &times;
            </button>
          )}
        </div>
        {showDropdown && (
          <div className="combobox-dropdown">
            {(students.data ?? []).length === 0 ? (
              <div className="combobox-empty">{comboQuery ? 'No students found.' : 'Type to search…'}</div>
            ) : (
              (students.data ?? []).map((s) => (
                <button
                  key={s.student_id}
                  type="button"
                  className={`combobox-item ${selectedStudentId === s.student_id ? 'active' : ''}`}
                  onMouseDown={() => selectStudent(s.student_id, s.student_name)}
                >
                  <span className="combobox-item-name">{s.student_name}</span>
                  <span className="combobox-item-id">{s.student_id}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {message && (
        <div className={`alert ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* Content */}
      {!student.data ? (
        <div className="blank-slate-panel panel">
          <div className="blank-slate-content">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-muted">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
              <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            <h3>Select a Student</h3>
            <p className="text-muted">Use the search bar above to find and select a student.</p>
          </div>
        </div>
      ) : (
        <div className="student-workspace stack">

          <StudentProfileHeader
            student={student.data}
            eligibility={student.data.eligibility}
            activePeriod={activePeriod}
            majorCode={majorCode}
            templateKey={templateKey}
            templates={templates.data || []}
            onTemplateChange={setTemplateKey}
            onEmail={handleSendEmail}
            emailSending={emailSending}
            onRecommend={handleRecommend}
            onDownloadReport={handleDownloadReport}
          />

          <div className="workspace-tabs-nav">
            <button type="button" className={`tab-btn ${activeTab === 'schedule' ? 'active' : ''}`} onClick={() => setActiveTab('schedule')}>Schedule Builder</button>
            <button type="button" className={`tab-btn ${activeTab === 'academic' ? 'active' : ''}`} onClick={() => setActiveTab('academic')}>Academic Record</button>
            <button type="button" className={`tab-btn ${activeTab === 'degree' ? 'active' : ''}`} onClick={() => setActiveTab('degree')}>Degree Plan</button>
            <button type="button" className={`tab-btn ${activeTab === 'exceptions' ? 'active' : ''}`} onClick={() => setActiveTab('exceptions')}>Bypass</button>
            <button type="button" className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>History</button>
          </div>

          <div className="workspace-tab-content">

            {activeTab === 'schedule' && (
              <CourseSelectionBuilder
                eligibility={student.data.eligibility}
                remainingCredits={student.data.credits_remaining}
                formState={formState}
                onChange={setFormState}
                onSave={handleSaveSelection}
              />
            )}

            {activeTab === 'academic' && (
              <div className="stack">
                {intensiveCourses.length > 0 && (
                  <div className="panel stack">
                    <div className="flex-between">
                      <div>
                        <h3 style={{ margin: 0 }}>Intensive Course Placement <Tooltip text="Mark a course as 'Excluded' to remove it from this student's eligible list during intensive semesters." /></h3>
                        <p className="text-muted text-sm" style={{ margin: '4px 0 0' }}>Select which intensive course(s) apply to this student.</p>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button type="button" className="btn-sm btn-outline" onClick={() => setExcludedCourses(originalExcludedCourses)}>Reset</button>
                        <button type="button" className="btn-primary btn-sm" onClick={handleSavePlacements}>Save Placement</button>
                      </div>
                    </div>
                    <div className="placement-grid">
                      {intensiveCourses.map((course) => {
                        const isExcluded = excludedCourses.includes(course.course_code)
                        return (
                          <button key={course.course_code} type="button" className={`placement-card ${isExcluded ? 'excluded' : 'active'}`}
                            onClick={() => setExcludedCourses((prev) => isExcluded ? prev.filter((c) => c !== course.course_code) : [...prev, course.course_code])}>
                            <span className="placement-card-code">{course.course_code}</span>
                            <span className="placement-card-title">{course.title}</span>
                            <span className="placement-card-status">{isExcluded ? '✗ Excluded' : '✓ Active'}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
                <EligibilityTables eligibility={student.data.eligibility} intensiveCourses={intensiveCourses} />
              </div>
            )}

            {activeTab === 'degree' && (
              <div className="stack">
                {degreePlan.isLoading && <div className="panel" style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>Loading degree plan…</div>}
                {degreePlan.isError && <div className="panel" style={{ textAlign: 'center', padding: '3rem', color: '#dc2626' }}>Could not load degree plan. The degree plan dataset may not be configured for this major.</div>}
                {degreePlan.data && (
                  <>
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '1.25rem', background: 'white', padding: '0.75rem', borderRadius: '12px', border: '1px solid var(--line)' }}>
                      {degreePlan.data.legend.map((item) => (
                        <span key={item.status} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', fontWeight: 500 }}>
                          <span style={{ width: '11px', height: '11px', borderRadius: '50%', background: STATUS_DOT[item.status] ?? '#cbd5e1', display: 'inline-block', flexShrink: 0 }} />
                          {item.label}
                        </span>
                      ))}
                    </div>
                    <div className="grid-2">
                      {degreePlan.data.years.map((year) => (
                        <div key={year.year_name} className="panel">
                          <div className="flex-between" style={{ borderBottom: '1px solid var(--line)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                            <h3 style={{ margin: 0, color: 'var(--accent)' }}>{year.year_name}</h3>
                          </div>
                          <div className="degree-grid">
                            {year.semesters.map((semester) => (
                              <div key={semester.semester_key} className="degree-card">
                                <div className="flex-between">
                                  <strong style={{ fontSize: '0.85rem' }}>{semester.semester_key}</strong>
                                  <span className="badge badge-info">{semester.total_credits} cr</span>
                                </div>
                                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                                  {semester.courses.map((course) => (
                                    <div key={course.code} style={{ background: STATUS_BG[course.status] ?? '#f8f9fa', borderRadius: '8px', padding: '0.5rem 0.75rem', border: `1px solid ${STATUS_BORDER[course.status] ?? 'var(--line)'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <div>
                                        <div style={{ fontWeight: 700, fontSize: '0.75rem', fontFamily: 'monospace' }}>{course.code}</div>
                                        <div style={{ fontSize: '0.7rem', color: 'var(--muted)', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{course.title}</div>
                                      </div>
                                      <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: STATUS_DOT[course.status] ?? '#cbd5e1', flexShrink: 0, display: 'inline-block' }} />
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                {!degreePlan.data && !degreePlan.isLoading && !degreePlan.isError && (
                  <div className="blank-slate-panel panel">
                    <div className="blank-slate-content">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-muted"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" /></svg>
                      <h3>Degree Plan Unavailable</h3>
                      <p className="text-muted">No degree plan data found for this student.</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'exceptions' && (
              <ExceptionManagement
                student={student.data}
                eligibility={student.data.eligibility}
                bypassCourse={bypassCourse}
                setBypassCourse={setBypassCourse}
                bypassNote={bypassNote}
                setBypassNote={setBypassNote}
                onBypassSave={handleBypassSave}
                onBypassDelete={handleBypassDelete}
              />
            )}

            {activeTab === 'history' && (
              <div className="panel stack">
                <h3 style={{ margin: 0 }}>Advising History</h3>
                <p className="text-muted text-sm" style={{ margin: '4px 0 0' }}>Saved advising sessions for this student. Restore any session to the current active period.</p>
                {sessions.isLoading && <p className="text-muted text-sm">Loading sessions…</p>}
                {!sessions.isLoading && (!sessions.data || sessions.data.length === 0) && (
                  <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No saved sessions found.</p>
                )}
                {sessions.data && sessions.data.length > 0 && (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="premium-table">
                      <thead>
                        <tr>
                          <th>Session</th>
                          <th>Period</th>
                          <th>Date</th>
                          <th>Advised</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.data.map((s) => (
                          <tr key={s.id}>
                            <td style={{ fontSize: '0.875rem', fontWeight: 500 }}>{s.title}</td>
                            <td style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'monospace' }}>{s.period_code ?? '—'}</td>
                            <td style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{new Date(s.created_at).toLocaleString()}</td>
                            <td style={{ fontSize: '0.8rem' }}>
                              {Array.isArray((s.summary as Record<string, unknown>).advised)
                                ? ((s.summary as Record<string, unknown[]>).advised.length) + ' courses'
                                : '—'}
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                                <button type="button" className="btn-sm btn-outline" onClick={() => setViewTarget(s)}>
                                  View
                                </button>
                                <button
                                  type="button"
                                  className="btn-sm btn-outline"
                                  onClick={() => setRestoreTarget({ id: s.id, title: s.title })}
                                  disabled={!activePeriod}
                                  title={activePeriod ? 'Restore this session to the active period' : 'No active period'}
                                >
                                  Restore
                                </button>
                                <button
                                  type="button"
                                  className="btn-sm btn-outline"
                                  style={{ color: '#ef4444', borderColor: '#fca5a5' }}
                                  onClick={() => handleDeleteSession(s.id)}
                                  title="Delete this session"
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {viewTarget && (
                  <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div className="panel stack" style={{ maxWidth: '760px', width: '94%', maxHeight: '84vh', overflowY: 'auto' }}>
                      <div className="flex-between items-center">
                        <h3 style={{ margin: 0 }}>Session Details</h3>
                        <button type="button" className="btn-sm btn-outline" onClick={() => setViewTarget(null)}>Close</button>
                      </div>

                      <div style={{ display: 'grid', gap: '0.5rem' }}>
                        <p className="text-sm" style={{ margin: 0 }}><strong>Session:</strong> {viewTarget.title}</p>
                        <p className="text-sm" style={{ margin: 0 }}><strong>Period:</strong> {viewTarget.period_code ?? '—'}</p>
                        <p className="text-sm" style={{ margin: 0 }}><strong>Saved:</strong> {new Date(viewTarget.created_at).toLocaleString()}</p>
                      </div>

                      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                        <div>
                          <h4 style={{ margin: '0 0 0.4rem' }}>Advised Courses</h4>
                          {Array.isArray((viewTarget.summary as Record<string, unknown>).advised) && (viewTarget.summary as Record<string, string[]>).advised.length > 0 ? (
                            <ul className="text-sm" style={{ margin: 0, paddingLeft: '1rem' }}>
                              {(viewTarget.summary as Record<string, string[]>).advised.map((course) => <li key={`advised-${course}`}>{course}</li>)}
                            </ul>
                          ) : <p className="text-muted text-sm" style={{ margin: 0 }}>No advised courses.</p>}
                        </div>

                        <div>
                          <h4 style={{ margin: '0 0 0.4rem' }}>Optional Courses</h4>
                          {Array.isArray((viewTarget.summary as Record<string, unknown>).optional) && (viewTarget.summary as Record<string, string[]>).optional.length > 0 ? (
                            <ul className="text-sm" style={{ margin: 0, paddingLeft: '1rem' }}>
                              {(viewTarget.summary as Record<string, string[]>).optional.map((course) => <li key={`optional-${course}`}>{course}</li>)}
                            </ul>
                          ) : <p className="text-muted text-sm" style={{ margin: 0 }}>No optional courses.</p>}
                        </div>

                        <div>
                          <h4 style={{ margin: '0 0 0.4rem' }}>Repeat Courses</h4>
                          {Array.isArray((viewTarget.summary as Record<string, unknown>).repeat) && (viewTarget.summary as Record<string, string[]>).repeat.length > 0 ? (
                            <ul className="text-sm" style={{ margin: 0, paddingLeft: '1rem' }}>
                              {(viewTarget.summary as Record<string, string[]>).repeat.map((course) => <li key={`repeat-${course}`}>{course}</li>)}
                            </ul>
                          ) : <p className="text-muted text-sm" style={{ margin: 0 }}>No repeat courses.</p>}
                        </div>
                      </div>

                      <div>
                        <h4 style={{ margin: '0 0 0.4rem' }}>Advising Note</h4>
                        <p className="text-sm" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{String((viewTarget.summary as Record<string, unknown>).note || '—')}</p>
                      </div>

                      {/* Period-to-period diff */}
                      {(() => {
                        const idx = sessions.data?.findIndex((s) => s.id === viewTarget.id) ?? -1
                        const prior = (sessions.data && idx >= 0) ? sessions.data[idx + 1] : undefined
                        if (!prior) {
                          return (
                            <p className="text-muted text-sm" style={{ margin: 0, borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                              First recorded session — no earlier session to compare.
                            </p>
                          )
                        }
                        const vt = viewTarget.summary as Record<string, string[]>
                        const pr = prior.summary as Record<string, string[]>
                        const diffSection = (label: string, key: string) => {
                          const curr = vt[key] ?? []
                          const prev = pr[key] ?? []
                          const added = curr.filter((c) => !prev.includes(c))
                          const removed = prev.filter((c) => !curr.includes(c))
                          if (added.length === 0 && removed.length === 0) return null
                          return (
                            <div key={key}>
                              <div style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600, marginBottom: '4px' }}>{label}</div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {added.map((c) => <span key={`+${c}`} style={{ background: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0', borderRadius: '4px', padding: '1px 7px', fontSize: '0.78rem', fontFamily: 'monospace' }}>+{c}</span>)}
                                {removed.map((c) => <span key={`-${c}`} style={{ background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca', borderRadius: '4px', padding: '1px 7px', fontSize: '0.78rem', fontFamily: 'monospace' }}>&minus;{c}</span>)}
                              </div>
                            </div>
                          )
                        }
                        const sections = [
                          diffSection('Advised Courses', 'advised'),
                          diffSection('Optional Courses', 'optional'),
                          diffSection('Repeat Courses', 'repeat'),
                        ].filter(Boolean)
                        return (
                          <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                            <h4 style={{ margin: '0 0 0.6rem', fontSize: '0.9rem' }}>
                              Changes from <code style={{ fontSize: '0.8rem', background: '#f1f5f9', padding: '1px 5px', borderRadius: '3px' }}>{prior.period_code ?? '—'}</code>
                              {' → '}
                              <code style={{ fontSize: '0.8rem', background: '#f1f5f9', padding: '1px 5px', borderRadius: '3px' }}>{viewTarget.period_code ?? '—'}</code>
                            </h4>
                            {sections.length > 0 ? (
                              <div style={{ display: 'grid', gap: '0.6rem' }}>{sections}</div>
                            ) : (
                              <p className="text-muted text-sm" style={{ margin: 0 }}>No changes to courses between these sessions.</p>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                )}

                {/* Confirm restore dialog */}
                {restoreTarget && (
                  <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div className="panel" style={{ maxWidth: '420px', width: '90%' }}>
                      <h3 style={{ margin: '0 0 0.5rem' }}>Confirm Restore</h3>
                      <p className="text-muted text-sm" style={{ margin: '0 0 1rem' }}>
                        Restore session <strong>&ldquo;{restoreTarget.title}&rdquo;</strong> to the current active period? This will overwrite the current selection for this student.
                      </p>
                      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn-sm btn-outline" onClick={() => setRestoreTarget(null)} disabled={restoring}>Cancel</button>
                        <button type="button" className="btn-primary btn-sm" onClick={() => handleRestoreSnapshot(restoreTarget.id)} disabled={restoring}>
                          {restoring ? 'Restoring…' : 'Confirm Restore'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recommend Preview Modal */}
      {recommendPreview && student.data && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div className="panel stack" style={{ maxWidth: '520px', width: '94%', maxHeight: '70vh', overflowY: 'auto' }}>
            <h3 style={{ margin: 0 }}>Recommended Courses</h3>
            <p className="text-muted text-sm" style={{ margin: '4px 0 0' }}>
              The following {recommendPreview.length} course{recommendPreview.length !== 1 ? 's' : ''} will be added to your advised list.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.5rem' }}>
              {recommendPreview.map((code) => {
                const c = student.data!.eligibility.find((x) => x.course_code === code)
                return (
                  <div key={code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0.6rem', background: '#f0fdf4', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                    <span style={{ fontSize: '0.85rem' }}><strong style={{ fontFamily: 'monospace' }}>{code}</strong>{c ? ` — ${c.title}` : ''}</span>
                    <span className="badge badge-primary" style={{ fontSize: '0.7rem' }}>{c?.credits ?? 3} cr</span>
                  </div>
                )
              })}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
              <button type="button" className="btn-sm btn-outline" onClick={() => setRecommendPreview(null)}>Cancel</button>
              <button type="button" className="btn-primary btn-sm" onClick={applyRecommendPreview}>Accept</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
