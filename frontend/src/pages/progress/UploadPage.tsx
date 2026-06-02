import { useState, useRef } from 'react'
import { useProgressStatus, useDatasetVersions } from '../../lib/hooks'
import { uploadProgressReport, previewProgressReport, uploadCourseConfig, API_BASE_URL, type ProgressUploadPreview } from '../../lib/api'
import { useMajorContext } from '../../lib/MajorContext'
import { useQueryClient } from '@tanstack/react-query'

async function downloadTemplate(path: string, filename: string) {
  const token = window.localStorage.getItem('advising_v2_token')
  const res = await fetch(`${API_BASE_URL}/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!res.ok) return
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click()
  a.remove(); URL.revokeObjectURL(url)
}

function UploadZone({
  label,
  hint,
  onUpload,
  loading,
  accept,
}: {
  label: string
  hint: string
  onUpload: (file: File) => void
  loading: boolean
  accept: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  function handleFile(file: File | undefined) {
    if (file) onUpload(file)
  }

  return (
    <div
      className={`upload-zone ${dragOver ? 'drag-over' : ''} ${loading ? 'uploading' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') inputRef.current?.click() }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <div className="upload-zone-icon">
        {loading ? (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        ) : (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        )}
      </div>
      <div className="upload-zone-label">{loading ? 'Uploading…' : label}</div>
      <div className="upload-zone-hint">{hint}</div>
    </div>
  )
}

function FilterOption({
  checked,
  label,
  detail,
  onChange,
}: {
  checked: boolean
  label: string
  detail: string
  onChange: () => void
}) {
  return (
    <label className={`upload-filter-option ${checked ? 'is-selected' : ''}`}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="upload-filter-option-main">
        <span className="upload-filter-option-label">{label}</span>
        <span className="upload-filter-option-detail">{detail}</span>
      </span>
    </label>
  )
}

function UploadMetric({ label, value, tone = 'neutral' }: { label: string; value: number; tone?: 'good' | 'warn' | 'danger' | 'neutral' }) {
  return (
    <div className={`upload-review-metric upload-review-metric--${tone}`}>
      <div className="upload-review-metric-value">{value}</div>
      <div className="upload-review-metric-label">{label}</div>
    </div>
  )
}

export function UploadPage() {
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const queryClient = useQueryClient()
  const status = useProgressStatus(majorCode)
  const versions = useDatasetVersions(majorCode)

  const activeVersions: Record<string, { original_filename: string | null }> = {}
  for (const v of versions.data ?? []) {
    if (v.is_active) activeVersions[v.dataset_type] = v
  }

  const [prLoading, setPrLoading] = useState(false)
  const [ccLoading, setCcLoading] = useState(false)
  const [prMsg, setPrMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [ccMsg, setCcMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [prPreview, setPrPreview] = useState<(ProgressUploadPreview & { _file: File }) | null>(null)
  const [prPreviewRefreshing, setPrPreviewRefreshing] = useState(false)
  const [selectedSourceMajors, setSelectedSourceMajors] = useState<string[]>([])
  const [selectedCohortYears, setSelectedCohortYears] = useState<string[]>([])

  async function handleProgressReport(file: File) {
    setPrMsg(null)
    setPrLoading(true)
    try {
      const preview = await previewProgressReport(majorCode, file)
      setPrPreview({ ...preview, _file: file })
      setSelectedSourceMajors(preview.default_source_majors ?? [])
      setSelectedCohortYears(preview.default_cohort_years ?? [])
    } catch (err: unknown) {
      setPrMsg({ type: 'error', text: err instanceof Error ? err.message : 'Preview failed.' })
    } finally {
      setPrLoading(false)
    }
  }

  async function refreshProgressPreview(file: File, sourceMajors: string[], cohortYears: string[]) {
    setPrPreviewRefreshing(true)
    try {
      const preview = await previewProgressReport(majorCode, file, sourceMajors, cohortYears)
      setPrPreview({ ...preview, _file: file })
    } catch (err: unknown) {
      setPrMsg({ type: 'error', text: err instanceof Error ? err.message : 'Preview failed.' })
    } finally {
      setPrPreviewRefreshing(false)
    }
  }

  async function confirmProgressUpload() {
    if (!prPreview) return
    const file = prPreview._file
    const sourceMajors = prPreview.requires_major_selection ? selectedSourceMajors : undefined
    if (prPreview.requires_major_selection && !sourceMajors?.length) {
      setPrMsg({ type: 'error', text: 'Select at least one source major before uploading.' })
      return
    }
    setPrPreview(null)
    setPrLoading(true)
    try {
      const result = await uploadProgressReport(majorCode, file, sourceMajors, selectedCohortYears)
      setPrMsg({ type: 'success', text: `Uploaded successfully — ${result.student_count} students, ${result.row_count} rows.` })
      queryClient.invalidateQueries({ queryKey: ['progress-status', majorCode] })
    } catch (err: unknown) {
      setPrMsg({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed.' })
    } finally {
      setPrLoading(false)
    }
  }

  async function handleCourseConfig(file: File) {
    setCcMsg(null)
    setCcLoading(true)
    try {
      const result = await uploadCourseConfig(majorCode, file)
      setCcMsg({ type: 'success', text: `Uploaded successfully — ${result.required_count} required, ${result.intensive_count} intensive courses.` })
      queryClient.invalidateQueries({ queryKey: ['progress-status', majorCode] })
    } catch (err: unknown) {
      setCcMsg({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed.' })
    } finally {
      setCcLoading(false)
    }
  }

  const s = status.data
  const previewStudentTotal = prPreview?.total_students ?? 0
  const previewRowTotal = prPreview?.total_rows ?? 0
  const canConfirmProgressUpload = (!prPreview?.requires_major_selection || selectedSourceMajors.length > 0) && !prPreviewRefreshing

  function toggleSourceMajor(major: string) {
    if (!prPreview) return
    const next = selectedSourceMajors.includes(major)
      ? selectedSourceMajors.filter((item) => item !== major)
      : [...selectedSourceMajors, major]
    setSelectedSourceMajors(next)
    void refreshProgressPreview(prPreview._file, next, selectedCohortYears)
  }

  function toggleCohortYear(year: string) {
    if (!prPreview) return
    const next = selectedCohortYears.includes(year)
      ? selectedCohortYears.filter((item) => item !== year)
      : [...selectedCohortYears, year]
    setSelectedCohortYears(next)
    void refreshProgressPreview(prPreview._file, selectedSourceMajors, next)
  }

  function setAllSourceMajors() {
    if (!prPreview) return
    const next = prPreview.major_options.map((option) => option.major)
    setSelectedSourceMajors(next)
    void refreshProgressPreview(prPreview._file, next, selectedCohortYears)
  }

  function clearSourceMajors() {
    if (!prPreview) return
    setSelectedSourceMajors([])
    void refreshProgressPreview(prPreview._file, [], selectedCohortYears)
  }

  function setAllCohortYears() {
    if (!prPreview) return
    const next = prPreview.cohort_options.map((option) => option.year)
    setSelectedCohortYears(next)
    void refreshProgressPreview(prPreview._file, selectedSourceMajors, next)
  }

  function clearCohortYears() {
    if (!prPreview) return
    setSelectedCohortYears([])
    void refreshProgressPreview(prPreview._file, selectedSourceMajors, [])
  }

  function closeProgressPreview() {
    setPrPreview(null)
    setSelectedSourceMajors([])
    setSelectedCohortYears([])
  }

  return (
    <section className="stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Academic Progress</div>
          <h2>Upload Data</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Major:</span>
          <select className="select-input" value={majorCode} onChange={(e) => setMajorCode(e.target.value)}>
            {allowedMajors.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {/* Status banners */}
      {s && (
        <div className="grid-2 mb-6">
          <div className={`status-badge-card ${s.progress_report.has_report ? 'status-ok' : 'status-missing'}`}>
            <div className="status-badge-label">Progress Report</div>
            {s.progress_report.has_report ? (
              <div className="status-badge-value">{s.progress_report.student_count} students loaded</div>
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
        {/* Progress Report */}
        <div className="panel stack">
          <div className="panel-header mb-3">
            <h3>Progress Report</h3>
            <p className="text-muted text-sm">
              Long format (ID, NAME, Course, Grade, Year, Semester) or wide format (COURSE_* columns).
              Excel (.xlsx) or CSV.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate('/progress/templates/progress-report', 'progress_report_template.xlsx')}>↓ Template</button>
              {activeVersions['progress_report'] && (
                <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate(`/datasets/${majorCode}/progress_report/download`, activeVersions['progress_report'].original_filename || 'progress_report.xlsx')}>↓ Current File</button>
              )}
            </div>
          </div>
          <UploadZone
            label="Drop progress report here or click to browse"
            hint="Accepted: .xlsx, .xls, .csv"
            onUpload={handleProgressReport}
            loading={prLoading}
            accept=".xlsx,.xls,.csv"
          />
          {prMsg && (
            <div className={`alert alert-${prMsg.type} mt-3`}>{prMsg.text}</div>
          )}
        </div>

        {/* Course Config */}
        <div className="panel stack">
          <div className="panel-header mb-3">
            <h3>Course Configuration</h3>
            <p className="text-muted text-sm">
              Required columns: <strong>Course, Type, Credits, PassingGrades</strong>.
              Optional: FromSemester, FromYear, ToSemester, ToYear. Excel or CSV.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate('/progress/templates/course-config', 'course_config_template.xlsx')}>↓ Template</button>
              {activeVersions['course_config'] && (
                <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate(`/datasets/${majorCode}/course_config/download`, activeVersions['course_config'].original_filename || 'course_config.xlsx')}>↓ Current File</button>
              )}
            </div>
          </div>
          <UploadZone
            label="Drop course config here or click to browse"
            hint="Accepted: .xlsx, .xls, .csv"
            onUpload={handleCourseConfig}
            loading={ccLoading}
            accept=".xlsx,.xls,.csv"
          />
          {ccMsg && (
            <div className={`alert alert-${ccMsg.type} mt-3`}>{ccMsg.text}</div>
          )}
          <div className="text-muted text-sm mt-2">
            <strong>Type values:</strong> <code>required</code> or <code>intensive</code><br />
            <strong>PassingGrades:</strong> comma-separated grades, e.g. <code>A+,A,A-,B+,B,B-,C+,C</code>
          </div>
        </div>
      </div>

      {/* Upload diff preview confirmation modal */}
      {prPreview && (
        <div className="upload-review-overlay" role="presentation">
          <div className="upload-review-dialog" role="dialog" aria-modal="true" aria-labelledby="upload-review-title">
            <div className="upload-review-header">
              <div>
                <div className="eyebrow text-muted">Progress Report Upload</div>
                <h3 id="upload-review-title">Review filters and impact</h3>
              </div>
              <button type="button" className="upload-review-close" onClick={closeProgressPreview} aria-label="Close upload review">x</button>
            </div>

            <div className="upload-review-body">
              <div className="upload-review-filters">
                {prPreview.requires_major_selection && (
                  <section className="upload-filter-section">
                    <div className="upload-filter-section-header">
                      <div>
                        <h4>Source major</h4>
                        <p>Choose which MAJOR values belong to this app major.</p>
                      </div>
                      <div className="upload-filter-actions">
                        <button type="button" className="btn-outline btn-sm" onClick={setAllSourceMajors}>All</button>
                        <button type="button" className="btn-outline btn-sm" onClick={clearSourceMajors}>Clear</button>
                      </div>
                    </div>
                    <div className="upload-filter-summary">
                      {selectedSourceMajors.length} of {prPreview.major_options.length} selected
                    </div>
                    <div className="upload-filter-list">
                      {prPreview.major_options.map((option) => (
                        <FilterOption
                          key={option.major}
                          checked={selectedSourceMajors.includes(option.major)}
                          label={option.major}
                          detail={`${option.student_count} students · ${option.row_count} rows`}
                          onChange={() => toggleSourceMajor(option.major)}
                        />
                      ))}
                    </div>
                  </section>
                )}

                {prPreview.cohort_options.length > 0 && (
                  <section className="upload-filter-section">
                    <div className="upload-filter-section-header">
                      <div>
                        <h4>Admission year</h4>
                        <p>Use the first 4 digits of the student ID to isolate a degree-plan cohort.</p>
                      </div>
                      <div className="upload-filter-actions">
                        <button type="button" className="btn-outline btn-sm" onClick={setAllCohortYears}>All</button>
                        <button type="button" className="btn-outline btn-sm" onClick={clearCohortYears}>Clear</button>
                      </div>
                    </div>
                    <div className="upload-filter-summary">
                      {selectedCohortYears.length > 0
                        ? `${selectedCohortYears.length} of ${prPreview.cohort_options.length} selected`
                        : 'No year filter; all detected years will be included'}
                    </div>
                    <div className="upload-filter-list upload-filter-list--years">
                      {prPreview.cohort_options.map((option) => (
                        <FilterOption
                          key={option.year}
                          checked={selectedCohortYears.includes(option.year)}
                          label={option.year}
                          detail={`${option.student_count} students · ${option.row_count} rows`}
                          onChange={() => toggleCohortYear(option.year)}
                        />
                      ))}
                    </div>
                  </section>
                )}
              </div>

              <aside className="upload-review-impact">
                <div className="upload-review-impact-header">
                  <h4>Upload impact</h4>
                  {prPreviewRefreshing ? <span>Updating</span> : <span>Ready</span>}
                </div>
                <div className="upload-review-metrics">
                  <UploadMetric label="Students saved" value={previewStudentTotal} />
                  <UploadMetric label="Rows saved" value={previewRowTotal} />
                  <UploadMetric label="New students" value={prPreview.new_students} tone="good" />
                  <UploadMetric label="Removed students" value={prPreview.removed_students} tone={prPreview.removed_students > 0 ? 'danger' : 'neutral'} />
                  <UploadMetric label="Grade changes" value={prPreview.grade_changes} tone="warn" />
                </div>
                {prPreview.requires_major_selection && selectedSourceMajors.length === 0 ? (
                  <div className="upload-review-warning">Select at least one source major before confirming.</div>
                ) : null}
              </aside>
            </div>

            <div className="upload-review-footer">
              <button type="button" className="btn-outline btn-sm" onClick={closeProgressPreview}>Cancel</button>
              <button type="button" className="btn-primary btn-sm" onClick={confirmProgressUpload} disabled={!canConfirmProgressUpload}>Confirm Upload</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
