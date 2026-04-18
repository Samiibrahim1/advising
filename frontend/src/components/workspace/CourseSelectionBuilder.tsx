import { useCallback, useMemo, useRef, useState } from 'react'
import { StudentEligibility } from '../../lib/api'
import { Tooltip } from '../Tooltip'

interface Props {
  eligibility: StudentEligibility['eligibility']
  remainingCredits?: number
  formState: { advised: string[]; optional: string[]; repeat: string[]; note: string }
  onChange: (state: { advised: string[]; optional: string[]; repeat: string[]; note: string }) => void
  onSave: () => void
}

type EligibilityItem = StudentEligibility['eligibility'][number]

function getCourseStatus(course: EligibilityItem): 'eligible' | 'ineligible' | 'completed' | 'registered' | 'not_offered' {
  if (course.registered) return 'registered'
  if (course.completed) return 'completed'
  if (!course.offered) return 'not_offered'
  if (course.eligibility_status === 'Eligible' || course.eligibility_status === 'Eligible (Bypass)') return 'eligible'
  return 'ineligible'
}

const STATUS_LABELS: Record<string, string> = {
  eligible: '✓ Eligible',
  ineligible: '✗ Not eligible',
  completed: '● Done',
  registered: '◎ Registered',
  not_offered: '○ Not offered',
}

const STATUS_DOT: Record<string, string> = {
  eligible: '#22c55e',
  ineligible: '#cbd5e1',
  completed: '#94a3b8',
  registered: '#eab308',
  not_offered: '#e2e8f0',
}

const STATUS_BG: Record<string, string> = {
  eligible: '#ffffff',
  ineligible: '#f8f9fa',
  completed: '#f0fdf4',
  registered: '#fefce8',
  not_offered: '#f8f9fa',
}

const STATUS_BORDER: Record<string, string> = {
  eligible: 'var(--line)',
  ineligible: 'var(--line)',
  completed: '#bbf7d0',
  registered: '#fde68a',
  not_offered: 'var(--line)',
}

export function CourseSelectionBuilder({ eligibility, remainingCredits = 0, formState, onChange, onSave }: Props) {
  const undoStack = useRef<Array<typeof formState>>([])

  const creditLookup = useMemo(() => {
    const map: Record<string, number> = {}
    for (const c of eligibility) {
      map[c.course_code] = typeof c.credits === 'number' ? c.credits : 3
    }
    return map
  }, [eligibility])

  const advisedCredits = useMemo(
    () => [...formState.advised, ...formState.optional, ...formState.repeat].reduce((s, code) => s + (creditLookup[code] || 3), 0),
    [formState, creditLookup],
  )

  const creditPercent = remainingCredits > 0 ? Math.min(100, Math.round((advisedCredits / remainingCredits) * 100)) : 0

  const advisedCr = useMemo(() => formState.advised.reduce((s, c) => s + (creditLookup[c] || 3), 0), [formState.advised, creditLookup])
  const optionalCr = useMemo(() => formState.optional.reduce((s, c) => s + (creditLookup[c] || 3), 0), [formState.optional, creditLookup])
  const repeatCr = useMemo(() => formState.repeat.reduce((s, c) => s + (creditLookup[c] || 3), 0), [formState.repeat, creditLookup])

  const [searchQuery, setSearchQuery] = useState('')
  const [showNotOffered, setShowNotOffered] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  const pushUndo = useCallback(() => {
    undoStack.current = [
      ...undoStack.current.slice(-19),
      { ...formState, advised: [...formState.advised], optional: [...formState.optional], repeat: [...formState.repeat] },
    ]
  }, [formState])

  const handleUndo = useCallback(() => {
    const prev = undoStack.current.pop()
    if (prev) onChange(prev)
  }, [onChange])

  const handleAdd = (courseCode: string, type: 'advised' | 'optional' | 'repeat') => {
    pushUndo()
    onChange({
      ...formState,
      advised: type === 'advised' ? [...formState.advised, courseCode] : formState.advised,
      optional: type === 'optional' ? [...formState.optional, courseCode] : formState.optional,
      repeat: type === 'repeat' ? [...formState.repeat, courseCode] : formState.repeat,
    })
  }

  const handleRemove = (courseCode: string, type: 'advised' | 'optional' | 'repeat') => {
    pushUndo()
    onChange({
      ...formState,
      advised: type === 'advised' ? formState.advised.filter((c) => c !== courseCode) : formState.advised,
      optional: type === 'optional' ? formState.optional.filter((c) => c !== courseCode) : formState.optional,
      repeat: type === 'repeat' ? formState.repeat.filter((c) => c !== courseCode) : formState.repeat,
    })
  }

  const selected = useMemo(() => new Set([...formState.advised, ...formState.optional, ...formState.repeat]), [formState])

  // Split courses: main (non-intensive) vs intensive, apply search filter
  const searchLower = searchQuery.toLowerCase()

  const availableMain = useMemo(
    () => eligibility.filter((c) =>
      c.course_type.toLowerCase() !== 'intensive' &&
      !selected.has(c.course_code) &&
      (showNotOffered || c.offered || c.completed || c.registered) &&
      (!searchQuery || c.course_code.toLowerCase().includes(searchLower) || c.title.toLowerCase().includes(searchLower))
    ),
    [eligibility, selected, showNotOffered, searchQuery, searchLower],
  )

  const availableIntensive = useMemo(
    () => eligibility.filter((c) =>
      c.course_type.toLowerCase() === 'intensive' &&
      !selected.has(c.course_code) &&
      (showNotOffered || c.offered || c.completed || c.registered) &&
      (!searchQuery || c.course_code.toLowerCase().includes(searchLower) || c.title.toLowerCase().includes(searchLower))
    ),
    [eligibility, selected, showNotOffered, searchQuery, searchLower],
  )

  // Group main courses by suggested_semester
  const semesterGroups = useMemo(() => {
    const groups = new Map<string, EligibilityItem[]>()
    for (const c of availableMain) {
      const sem = c.suggested_semester || 'Other'
      if (!groups.has(sem)) groups.set(sem, [])
      groups.get(sem)!.push(c)
    }
    // Sort keys: Fall < Spring < Summer per cycle, "Other" last
    const semOrder = (s: string): number => {
      if (s === 'Other') return 9999
      const m = s.match(/^(fall|spring|summer)[^0-9]*(\d+)?/i)
      if (!m) return 9998
      const season = m[1].toLowerCase()
      const num = parseInt(m[2] || '0', 10)
      const seasonIdx = season === 'fall' ? 0 : season === 'spring' ? 1 : 2
      return num * 3 + seasonIdx
    }
    const sorted = new Map<string, EligibilityItem[]>()
    for (const key of [...groups.keys()].sort((a, b) => semOrder(a) - semOrder(b))) {
      sorted.set(key, groups.get(key)!)
    }
    return sorted
  }, [availableMain])

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function CourseCard({ course }: { course: EligibilityItem }) {
    const status = getCourseStatus(course)
    const isIneligible = status === 'ineligible'
    const isNotOffered = status === 'not_offered'
    const isDimmed = isIneligible || isNotOffered
    const isCompleted = status === 'completed'
    const isRegistered = status === 'registered'
    return (
      <div
        className={`course-grid-card ${isDimmed ? 'course-grid-card--ineligible' : ''}`}
        style={{ background: STATUS_BG[status], borderColor: STATUS_BORDER[status] }}
      >
        <div className="course-grid-card__header">
          <strong className="course-grid-card__code">{course.course_code}</strong>
          <span className="course-grid-card__dot" style={{ background: STATUS_DOT[status] }} title={STATUS_LABELS[status]} />
        </div>
        <span className="course-grid-card__title">{course.title}</span>
        {isNotOffered && (
          <span className="course-grid-card__ineligible-label">○ Not offered</span>
        )}
        {isIneligible && (
          <>
            <span className="course-grid-card__ineligible-label">
              ✗ Not eligible{course.justification ? <Tooltip text={course.justification} /> : null}
            </span>
            {course.requisites && course.requisites !== 'None' && (
              <span className="course-grid-card__prereqs">{course.requisites}</span>
            )}
          </>
        )}
        {!isDimmed && (
          <div className="course-grid-card__actions">
            {!isCompleted && !isRegistered && (
              <>
                <button type="button" className="btn-sm" onClick={() => handleAdd(course.course_code, 'advised')}>Advise</button>
                <button type="button" className="btn-sm btn-outline" onClick={() => handleAdd(course.course_code, 'optional')}>Optional</button>
              </>
            )}
            {(isCompleted || isRegistered) && (
              <button type="button" className="btn-sm btn-warning" onClick={() => handleAdd(course.course_code, 'repeat')}>Repeat</button>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="course-selection-builder">
      {/* Credit bar + save */}
      <div className="builder-topbar">
        <div className="credit-counter-bar">
          <div className="credit-counter-bar__labels">
            <span>
              Advising <strong style={{ color: '#0f172a', fontSize: '16px' }}>{advisedCredits}</strong> of <strong>{remainingCredits}</strong> remaining credits
            </span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button type="button" onClick={handleUndo} disabled={undoStack.current.length === 0} className="btn-sm btn-outline" style={{ fontSize: '12px', padding: '2px 10px' }}>↩ Undo</button>
              <span style={{ fontSize: '12px', color: '#64748b' }}>{creditPercent}%</span>
            </div>
          </div>
          <div className="credit-bar-track">
            <div className="credit-bar-fill" style={{ width: `${creditPercent}%`, background: creditPercent > 100 ? '#ef4444' : creditPercent > 75 ? '#f59e0b' : '#22c55e' }} />
          </div>
          <div className="credit-breakdown">
            <span>Advised: {advisedCr} cr</span>
            <span>Optional: {optionalCr} cr</span>
            <span>Repeat: {repeatCr} cr</span>
          </div>
          {advisedCredits > remainingCredits && (
            <div className="credit-warning credit-warning--red">⚠ Exceeds remaining credits</div>
          )}
          {advisedCredits <= remainingCredits && advisedCredits > 18 && (
            <div className="credit-warning credit-warning--orange">⚠ Heavy load ({advisedCredits} cr) — verify with student</div>
          )}
        </div>
        <button type="button" className="btn-primary" onClick={onSave} style={{ flexShrink: 0 }}>Save Selections</button>
      </div>

      {/* Stacked layout: full-width course pool, then selections below */}
      <div className="builder-stacked">

        {/* Course Pool — full width */}
        <div className="course-pool scrollable">

          {/* Toolbar: search + toggle */}
          <div className="course-pool-toolbar">
            <input
              type="text"
              className="course-pool-search"
              placeholder="Filter courses by code or title…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1 }}
            />
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={showNotOffered}
                onChange={(e) => setShowNotOffered(e.target.checked)}
              />
              Show not offered
            </label>
          </div>

          {/* Required / main courses — grouped by semester */}
          {availableMain.length === 0 ? (
            <p className="empty-state" style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.85rem' }}>
              {searchQuery ? 'No courses match your search.' : 'No courses to display.'}
            </p>
          ) : (
            [...semesterGroups.entries()].map(([sem, courses]) => (
              <div key={sem} className="semester-group">
                <button
                  type="button"
                  className="semester-group-header"
                  onClick={() => toggleGroup(sem)}
                >
                  <span>{sem === 'Other' ? 'Other Courses' : sem}</span>
                  <span className="semester-group-count">{courses.length}</span>
                  <span className="semester-group-chevron">{collapsedGroups.has(sem) ? '▸' : '▾'}</span>
                </button>
                {!collapsedGroups.has(sem) && (
                  <div className="course-3col-grid">
                    {courses.map((course) => <CourseCard key={course.course_code} course={course} />)}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Intensive — separate section below */}
          {availableIntensive.length > 0 && (
            <div className="intensive-section">
              <div className="intensive-divider">
                <span>Intensive Courses</span>
              </div>
              <div className="course-3col-grid">
                {availableIntensive.map((course) => <CourseCard key={course.course_code} course={course} />)}
              </div>
            </div>
          )}

        </div>

        {/* Selections row — full width, horizontal */}
        <div className="selections-row">

          {/* Advised */}
          <div className="selection-group">
            <div className="group-header">
              <h4>Advised <span className="badge badge-primary">{formState.advised.length}</span></h4>
            </div>
            <div className="selected-list">
              {formState.advised.length === 0 && <p className="empty-state-sm">None.</p>}
              {formState.advised.map((code) => {
                const c = eligibility.find((x) => x.course_code === code)
                return (
                  <div key={code} className="selected-item">
                    <span><strong>{code}</strong>{c ? ` — ${c.title}` : ''}</span>
                    <button type="button" onClick={() => handleRemove(code, 'advised')} className="remove-btn">&times;</button>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Optional */}
          <div className="selection-group">
            <div className="group-header">
              <h4>Optional <span className="badge">{formState.optional.length}</span></h4>
            </div>
            <div className="selected-list">
              {formState.optional.length === 0 && <p className="empty-state-sm">None.</p>}
              {formState.optional.map((code) => {
                const c = eligibility.find((x) => x.course_code === code)
                return (
                  <div key={code} className="selected-item">
                    <span><strong>{code}</strong>{c ? ` — ${c.title}` : ''}</span>
                    <button type="button" onClick={() => handleRemove(code, 'optional')} className="remove-btn">&times;</button>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Repeat */}
          <div className="selection-group">
            <div className="group-header">
              <h4>Repeat <span className="badge badge-warning">{formState.repeat.length}</span></h4>
            </div>
            <div className="selected-list">
              {formState.repeat.length === 0 && <p className="empty-state-sm">None.</p>}
              {formState.repeat.map((code) => {
                const c = eligibility.find((x) => x.course_code === code)
                return (
                  <div key={code} className="selected-item">
                    <span><strong>{code}</strong>{c ? ` — ${c.title}` : ''}</span>
                    <button type="button" onClick={() => handleRemove(code, 'repeat')} className="remove-btn">&times;</button>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Advisor Note */}
          <div className="selection-group">
            <div className="group-header">
              <h4>Advisor Note</h4>
            </div>
            <textarea
              rows={4}
              value={formState.note}
              onChange={(e) => onChange({ ...formState, note: e.target.value })}
              placeholder="Add narrative notes for the student…"
              style={{ width: '100%', resize: 'vertical', fontSize: '0.85rem', padding: '0.5rem', borderRadius: '8px', border: '1px solid var(--line)' }}
            />
          </div>

        </div>
      </div>
    </div>
  )
}
