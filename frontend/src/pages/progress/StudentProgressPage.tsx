import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMajorContext } from '../../lib/MajorContext'
import { useProgressReport, useProgressAssignments, useProgressAssignmentTypes, useExemptions } from '../../lib/hooks'
import {
  saveProgressAssignment,
  deleteProgressAssignment,
  addExemption,
  deleteExemption,
  type StudentProgressRow,
} from '../../lib/api'

// ─── Grade cell CSS class (mirrors ReportsPage) ──────────────────
function gradeCellClass(val: string): string {
  if (!val || val === 'NR') return 'grade-cell grade-cell--empty'
  for (const e of val.split(',').map((x) => x.trim())) {
    if (e.toUpperCase().startsWith('CR')) return 'grade-cell grade-cell--progress'
  }
  for (const e of val.split(',').map((x) => x.trim())) {
    const parts = e.split('|')
    if (parts.length === 2) {
      const right = parts[1].trim().toUpperCase()
      const n = parseInt(right, 10)
      if ((!isNaN(n) && n > 0) || right === 'PASS') return 'grade-cell grade-cell--passed'
    }
  }
  return 'grade-cell grade-cell--failed'
}

// ─── Assignment slot (dropdown, auto-save on change) ────────────
function AssignmentSlot({
  label,
  currentValue,
  extraCourses,
  saving,
  savedRecently,
  onChange,
}: {
  label: string
  currentValue: string
  extraCourses: string[]
  saving: boolean
  savedRecently: boolean
  onChange: (val: string) => void
}) {
  // Build deduplicated option list: currentValue first (if set and not in extraCourses), then all extra courses
  const options: string[] = []
  if (currentValue && !extraCourses.includes(currentValue)) {
    options.push(currentValue)
  }
  for (const c of extraCourses) {
    options.push(c)
  }

  return (
    <div className="assignment-slot">
      <span className="assignment-slot-label">{label}</span>
      <select
        className="assignment-slot-select"
        value={currentValue}
        disabled={saving}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— unassigned —</option>
        {options.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <span className={`assignment-slot-status${savedRecently ? ' assignment-slot-status--saved' : ''}`}>
        {saving ? 'Saving…' : savedRecently ? '✓ Saved' : ''}
      </span>
    </div>
  )
}

// ─── Assignment panel ────────────────────────────────────────────
function AssignmentPanel({
  majorCode,
  studentId,
  extraCourses,
  exemptedCourses,
  onToggleExemption,
}: {
  majorCode: string
  studentId: string
  extraCourses: string[]
  exemptedCourses: string[]
  onToggleExemption: (courseCode: string, isExempt: boolean) => void
}) {
  const qc = useQueryClient()
  const assignmentsQuery = useProgressAssignments(majorCode, studentId)
  const typesQuery = useProgressAssignmentTypes(majorCode)
  const [saving, setSaving] = useState<string | null>(null)
  const [savedRecently, setSavedRecently] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const assignments = assignmentsQuery.data ?? []
  const types = typesQuery.data ?? []

  const byType: Record<string, string> = {}
  for (const a of assignments) byType[a.assignment_type] = a.course_code

  async function handleChange(typeLabel: string, courseCode: string) {
    setSaving(typeLabel)
    setErrorMsg(null)
    try {
      if (!courseCode) {
        const existing = assignments.find((a) => a.assignment_type === typeLabel)
        if (existing) {
          await deleteProgressAssignment(majorCode, studentId, typeLabel)
        }
      } else {
        await saveProgressAssignment(majorCode, {
          student_id: studentId,
          assignment_type: typeLabel,
          course_code: courseCode,
        })
      }
      qc.invalidateQueries({ queryKey: ['progress-assignments', majorCode] })
      qc.invalidateQueries({ queryKey: ['progress-report', majorCode] })
      setSavedRecently(typeLabel)
      setTimeout(() => setSavedRecently((prev) => (prev === typeLabel ? null : prev)), 2500)
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Save failed.')
    } finally {
      setSaving(null)
    }
  }

  if (assignmentsQuery.isLoading || typesQuery.isLoading) {
    return <div className="text-muted text-sm">Loading assignments…</div>
  }

  if (types.length === 0 && exemptedCourses.length === 0) {
    return (
      <div className="blank-slate-panel" style={{ padding: '1rem' }}>
        <p className="text-muted text-sm">
          No assignment type labels defined yet. Add them in the <strong>Configure</strong> page.
        </p>
      </div>
    )
  }

  if (extraCourses.length === 0 && exemptedCourses.length === 0) {
    return (
      <div className="blank-slate-panel" style={{ padding: '1rem' }}>
        <p className="text-muted text-sm">
          No extra courses in this progress report to assign. Extra courses are courses recorded
          in the report but not found in the course configuration.
        </p>
      </div>
    )
  }

  return (
    <div>
      {types.map((at) => (
        <AssignmentSlot
          key={at.id}
          label={at.label}
          currentValue={byType[at.label] ?? ''}
          extraCourses={extraCourses}
          saving={saving === at.label}
          savedRecently={savedRecently === at.label}
          onChange={(val) => handleChange(at.label, val)}
        />
      ))}

      {/* Exemption substitute slots — one per exempted course */}
      {exemptedCourses.length > 0 && (
        <div style={{ marginTop: types.length > 0 ? '1rem' : 0 }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Exempt Course Substitutes
          </div>
          {exemptedCourses.map((courseCode) => (
            <div key={courseCode} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
              <AssignmentSlot
                label={`${courseCode} substitute`}
                currentValue={byType[`${courseCode}_substitute`] ?? ''}
                extraCourses={extraCourses}
                saving={saving === `${courseCode}_substitute`}
                savedRecently={savedRecently === `${courseCode}_substitute`}
                onChange={(val) => handleChange(`${courseCode}_substitute`, val)}
              />
              <button
                type="button"
                title={`Remove ${courseCode} exemption`}
                style={{ fontSize: '0.75rem', color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', padding: '0 0.25rem' }}
                onClick={() => onToggleExemption(courseCode, false)}
              >
                ✕ Remove exemption
              </button>
            </div>
          ))}
        </div>
      )}

      {errorMsg && <div className="alert alert-error mt-2">{errorMsg}</div>}
    </div>
  )
}

// ─── Student detail panel ────────────────────────────────────────
function StudentDetailPanel({
  majorCode,
  student,
  extraCourses,
}: {
  majorCode: string
  student: StudentProgressRow
  extraCourses: string[]
}) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'courses' | 'assignments'>('courses')
  const [exemptionBusy, setExemptionBusy] = useState(false)
  const allCourses = Object.keys(student.courses)

  // Narrow the global extra-courses list to only courses this specific student has
  const studentExtraCourses = extraCourses.filter((c) => allCourses.includes(c))

  const exemptionsQuery = useExemptions(majorCode, student.student_id)
  const exemptedCourses = (exemptionsQuery.data ?? []).map((e) => e.course_code)

  // Candidate courses that can be exempted — currently just ARAB201
  const EXEMPTABLE_COURSES = ['ARAB201']
  const exemptablePresentInCourses = EXEMPTABLE_COURSES.filter((c) => allCourses.includes(c))

  async function handleToggleExemption(courseCode: string, makeExempt: boolean) {
    setExemptionBusy(true)
    try {
      if (makeExempt) {
        await addExemption(majorCode, student.student_id, courseCode)
      } else {
        await deleteExemption(majorCode, student.student_id, courseCode)
        // Also remove the substitute assignment if it existed
        try {
          await deleteProgressAssignment(majorCode, student.student_id, `${courseCode}_substitute`)
        } catch {
          // ignore — may not exist
        }
      }
      qc.invalidateQueries({ queryKey: ['exemptions', majorCode, student.student_id] })
      qc.invalidateQueries({ queryKey: ['progress-assignments', majorCode, student.student_id] })
    } finally {
      setExemptionBusy(false)
    }
  }

  return (
    <div className="panel stack">
      {/* Profile header */}
      <div className="profile-flat-row mb-4">
        <div>
          <div className="eyebrow text-muted text-xs mb-1">{student.student_id}</div>
          <h3 style={{ margin: 0, fontFamily: "'Space Grotesk', sans-serif", fontSize: '1.1rem' }}>{student.name}</h3>
        </div>
        <div className="flex-row gap-3">
          <div className="stat-mini">
            <span className="text-muted text-xs">Done</span>
            <span className="font-semibold">{student.completed_credits}</span>
          </div>
          <div className="stat-mini">
            <span className="text-muted text-xs">Reg</span>
            <span className="font-semibold">{student.registered_credits}</span>
          </div>
          <div className="stat-mini">
            <span className="text-muted text-xs">Rem</span>
            <span className="font-semibold">{student.remaining_credits}</span>
          </div>
          <div className="stat-mini">
            <span className="text-muted text-xs">GPA</span>
            <span className="font-semibold">{student.gpa != null ? student.gpa.toFixed(2) : '—'}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="page-tabs">
        <button
          type="button"
          className={`page-tab-btn${tab === 'courses' ? ' active' : ''}`}
          onClick={() => setTab('courses')}
        >
          Courses
        </button>
        <button
          type="button"
          className={`page-tab-btn${tab === 'assignments' ? ' active' : ''}`}
          onClick={() => setTab('assignments')}
        >
          Elective Assignments
        </button>
      </div>

      {/* Tab content */}
      {tab === 'courses' ? (
        <div className="premium-table-wrapper">
          <table className="premium-table">
            <thead>
              <tr>
                <th>Course</th>
                <th style={{ textAlign: 'center' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {allCourses.map((c) => {
                const val = student.courses[c] ?? 'NR'
                return (
                  <tr key={c}>
                    <td>{c}</td>
                    <td style={{ textAlign: 'center', padding: '0.3rem 0.5rem' }}>
                      <span className={gradeCellClass(val)}>{val === 'NR' ? '—' : val}</span>
                    </td>
                  </tr>
                )
              })}
              {allCourses.length === 0 && (
                <tr><td colSpan={2} className="text-muted text-center">No course data.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="stack">
          {/* Exemption toggles */}
          {exemptablePresentInCourses.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              {exemptablePresentInCourses.map((courseCode) => {
                const isExempt = exemptedCourses.includes(courseCode)
                return (
                  <button
                    key={courseCode}
                    type="button"
                    disabled={exemptionBusy}
                    className={isExempt ? 'btn-sm btn-outline' : 'btn-sm btn-primary'}
                    onClick={() => handleToggleExemption(courseCode, !isExempt)}
                    style={{ fontSize: '0.78rem' }}
                  >
                    {isExempt ? `✓ ${courseCode} exempt — remove` : `Mark ${courseCode} exempt`}
                  </button>
                )
              })}
            </div>
          )}
          <AssignmentPanel
            majorCode={majorCode}
            studentId={student.student_id}
            extraCourses={studentExtraCourses}
            exemptedCourses={exemptedCourses}
            onToggleExemption={(code, isExempt) => handleToggleExemption(code, isExempt)}
          />
        </div>
      )}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────
export function StudentProgressPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const [search, setSearch] = useState(searchParams.get('id') ?? '')
  const [selectedId, setSelectedId] = useState(searchParams.get('id') ?? '')

  const reportQuery = useProgressReport(majorCode, { search, pageSize: 500 })
  const assignmentTypesQuery = useProgressAssignmentTypes(majorCode)
  const allAssignmentsQuery = useProgressAssignments(majorCode)

  // Deduplicate students (required + intensive overlap)
  const studentMap = new Map<string, StudentProgressRow>()
  for (const r of reportQuery.data?.required ?? []) studentMap.set(r.student_id, r)
  const students = Array.from(studentMap.values())

  const totalStudents = useMemo(() => {
    const ids = new Set([
      ...(reportQuery.data?.required ?? []).map((r) => r.student_id),
      ...(reportQuery.data?.intensive ?? []).map((r) => r.student_id),
    ])
    return ids.size
  }, [reportQuery.data])

  const coverageStats = useMemo(() => {
    if (!assignmentTypesQuery.data?.length) return []
    const allAssignments = allAssignmentsQuery.data ?? []
    return assignmentTypesQuery.data.map((type) => {
      const assignedSet = new Set(
        allAssignments.filter((a) => a.assignment_type === type.label).map((a) => a.student_id)
      )
      return {
        label: type.label,
        assigned: assignedSet.size,
        total: totalStudents,
        pct: totalStudents > 0 ? Math.round((assignedSet.size / totalStudents) * 100) : 0,
      }
    })
  }, [assignmentTypesQuery.data, allAssignmentsQuery.data, totalStudents])

  const selected = students.find((s) => s.student_id === selectedId) ?? null
  const extraCourses = reportQuery.data?.extra_courses ?? []

  function handleSelect(id: string) {
    setSelectedId(id)
    setSearchParams({ id })
  }

  return (
    <section className="stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Academic Progress</div>
          <h2>Students</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Major:</span>
          <select className="select-input" value={majorCode} onChange={(e) => { setMajorCode(e.target.value); setSelectedId('') }}>
            {allowedMajors.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {/* Assignment Coverage */}
      {coverageStats.length > 0 && (
        <div className="panel mb-4" style={{ padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>Assignment Coverage</span>
            {coverageStats.map((s) => (
              <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{s.label}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <div style={{ width: '64px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${s.pct}%`, background: s.pct === 100 ? '#22c55e' : s.pct > 50 ? '#f59e0b' : '#ef4444', borderRadius: '3px', transition: 'width 0.3s' }} />
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{s.assigned}/{s.total} ({s.pct}%)</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid-layout-sidebar">
        {/* Sidebar: student list */}
        <div className="sidebar-panel">
          <input
            type="search"
            className="text-input"
            placeholder="Search by ID or name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: '100%', marginBottom: '0.75rem' }}
          />
          {reportQuery.isLoading && <div className="text-muted text-sm">Loading…</div>}
          {!reportQuery.isLoading && students.length === 0 && (
            <div className="text-muted text-sm">{search ? 'No students match.' : 'No data — upload a progress report first.'}</div>
          )}
          <ul className="student-list">
            {students.map((s) => (
              <li key={s.student_id}>
                <button
                  type="button"
                  className={`student-list-item${selectedId === s.student_id ? ' active' : ''}`}
                  onClick={() => handleSelect(s.student_id)}
                >
                  <span className="font-semibold" style={{ fontSize: '0.88rem' }}>{s.name}</span>
                  <span className="text-muted text-xs">{s.student_id}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Main: student detail */}
        <div className="main-panel">
          {selected ? (
            <StudentDetailPanel
              majorCode={majorCode}
              student={selected}
              extraCourses={extraCourses}
            />
          ) : (
            <div className="blank-slate-panel">
              <div className="blank-slate-content">
                <p className="text-muted">Select a student from the list to view their progress and elective assignments.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
