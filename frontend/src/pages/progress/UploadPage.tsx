import { useState, useRef } from 'react'
import { useProgressStatus, useDatasetVersions } from '../../lib/hooks'
import { uploadProgressReport, previewProgressReport, uploadCourseConfig, uploadElectiveAssignments, API_BASE_URL } from '../../lib/api'
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
  const [eaLoading, setEaLoading] = useState(false)
  const [prMsg, setPrMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [ccMsg, setCcMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [eaMsg, setEaMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [prPreview, setPrPreview] = useState<{ new_students: number; removed_students: number; grade_changes: number; total_students: number; _file: File } | null>(null)

  async function handleProgressReport(file: File) {
    setPrMsg(null)
    setPrLoading(true)
    try {
      const preview = await previewProgressReport(majorCode, file)
      setPrPreview({ ...preview, _file: file })
    } catch (err: unknown) {
      setPrMsg({ type: 'error', text: err instanceof Error ? err.message : 'Preview failed.' })
    } finally {
      setPrLoading(false)
    }
  }

  async function confirmProgressUpload() {
    if (!prPreview) return
    const file = prPreview._file
    setPrPreview(null)
    setPrLoading(true)
    try {
      const result = await uploadProgressReport(majorCode, file)
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

  async function handleElectiveAssignments(file: File) {
    setEaMsg(null)
    setEaLoading(true)
    try {
      const result = await uploadElectiveAssignments(majorCode, file)
      const summary = `Done — ${result.upserted} upserted, ${result.skipped} skipped.`
      const detail = result.errors.length > 0 ? `\n\nRow errors:\n${result.errors.slice(0, 10).join('\n')}${result.errors.length > 10 ? `\n…and ${result.errors.length - 10} more` : ''}` : ''
      setEaMsg({ type: result.skipped > 0 && result.upserted === 0 ? 'error' : 'success', text: summary + detail })
    } catch (err: unknown) {
      setEaMsg({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed.' })
    } finally {
      setEaLoading(false)
    }
  }

  const s = status.data

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

      {/* Elective Assignments */}
      <div className="panel stack mt-4">
        <div className="panel-header mb-3">
          <h3>Bulk Elective Assignments</h3>
          <p className="text-muted text-sm">
            Upload an Excel file to assign or update elective courses for many students at once.
            Required columns: <strong>Student ID</strong> (or <strong>ID</strong>), <strong>Assignment Type</strong> (e.g.&nbsp;SCE), <strong>Course Code</strong>.
            One row per assignment. Existing assignments for those students are overwritten.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate('/progress/templates/elective-assignments', 'elective_assignments_template.xlsx')}>↓ Template</button>
            {activeVersions['elective_assignments'] && (
              <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.72rem', padding: '1px 8px', width: 'fit-content' }} onClick={() => downloadTemplate(`/datasets/${majorCode}/elective_assignments/download`, activeVersions['elective_assignments'].original_filename || 'elective_assignments.xlsx')}>↓ Current File</button>
            )}
          </div>
        </div>
        <UploadZone
          label="Drop elective assignments Excel here or click to browse"
          hint="Accepted: .xlsx, .xls"
          onUpload={handleElectiveAssignments}
          loading={eaLoading}
          accept=".xlsx,.xls"
        />
        {eaMsg && (
          <div className={`alert alert-${eaMsg.type} mt-3`} style={{ whiteSpace: 'pre-wrap' }}>{eaMsg.text}</div>
        )}
      </div>

      {/* Upload diff preview confirmation modal */}
      {prPreview && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div className="panel stack" style={{ maxWidth: '440px', width: '90%' }}>
            <h3 style={{ margin: '0 0 0.4rem' }}>Confirm Upload</h3>
            <p className="text-muted text-sm" style={{ margin: '0 0 1.25rem' }}>Review what this upload will change before committing:</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '1.25rem' }}>
              <div style={{ textAlign: 'center', padding: '12px', background: '#f0fdf4', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#166534' }}>{prPreview.new_students}</div>
                <div style={{ fontSize: '0.72rem', color: '#166534', textTransform: 'uppercase', fontWeight: 600 }}>New Students</div>
              </div>
              <div style={{ textAlign: 'center', padding: '12px', background: prPreview.removed_students > 0 ? '#fef2f2' : '#f8fafc', borderRadius: '8px', border: `1px solid ${prPreview.removed_students > 0 ? '#fecaca' : '#e2e8f0'}` }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: prPreview.removed_students > 0 ? '#991b1b' : '#64748b' }}>{prPreview.removed_students}</div>
                <div style={{ fontSize: '0.72rem', color: prPreview.removed_students > 0 ? '#991b1b' : '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Removed Students</div>
              </div>
              <div style={{ textAlign: 'center', padding: '12px', background: '#fffbeb', borderRadius: '8px', border: '1px solid #fde68a' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#92400e' }}>{prPreview.grade_changes}</div>
                <div style={{ fontSize: '0.72rem', color: '#92400e', textTransform: 'uppercase', fontWeight: 600 }}>Grade Changes</div>
              </div>
              <div style={{ textAlign: 'center', padding: '12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{prPreview.total_students}</div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Students</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button type="button" className="btn-outline btn-sm" onClick={() => setPrPreview(null)}>Cancel</button>
              <button type="button" className="btn-primary btn-sm" onClick={confirmProgressUpload}>Confirm Upload</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
