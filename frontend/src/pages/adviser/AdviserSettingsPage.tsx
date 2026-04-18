import { ChangeEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { API_BASE_URL } from '../../lib/api'
import { useDatasetVersions, usePeriods, useSessions, useStudents } from '../../lib/hooks'
import { useMajorContext } from '../../lib/MajorContext'
import { Tooltip } from '../../components/Tooltip'

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

const DATASET_LABELS: Record<string, string> = {
  courses: 'Course Catalog (courses_table.xlsx)',
  progress: 'Student Progress Report',
  email_roster: 'Email Roster',
}

export function AdviserSettingsPage() {
  const queryClient = useQueryClient()
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()
  const [studentQuery, setStudentQuery] = useState('')
  const [bulkStudentIds, setBulkStudentIds] = useState<string[]>([])
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [sessionSearch, setSessionSearch] = useState('')

  // Period management
  const [newSemester, setNewSemester] = useState('Fall')
  const [newYear, setNewYear] = useState(new Date().getFullYear())
  const [newAdvisorName, setNewAdvisorName] = useState('')
  const [showCreatePeriod, setShowCreatePeriod] = useState(false)

  // Data files
  const [uploadType, setUploadType] = useState('courses')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  // Bulk placement upload
  const [placementFile, setPlacementFile] = useState<File | null>(null)
  const [placementUploading, setPlacementUploading] = useState(false)

  const periods = usePeriods(majorCode)
  const activePeriod = periods.data?.find((p) => p.is_active)
  const students = useStudents(majorCode, studentQuery)
  const sessions = useSessions(majorCode, activePeriod?.period_code)
  const versions = useDatasetVersions(majorCode)

  function showMsg(type: 'success' | 'error', text: string) {
    setMessage({ type, text })
  }

  async function runJsonAction(path: string, init?: RequestInit) {
    const response = await authedFetch(path, init)
    const body = await response.text()
    if (!response.ok) { showMsg('error', body || 'Request failed.'); return null }
    try { showMsg('success', JSON.parse(body).message || 'Done.') } catch { showMsg('success', body || 'Done.') }
    return body
  }

  // ── Session actions ──────────────────────────────────────────────────────
  async function handleClearSelections() {
    if (!activePeriod) return
    const res = await authedFetch(`/advising/selection/${majorCode}/${activePeriod.period_code}`, { method: 'DELETE' })
    const body = await res.json().catch(() => null)
    if (!res.ok) { showMsg('error', body?.detail || body?.message || 'Clear failed.'); return }
    showMsg('success', body?.message || 'Selections cleared.')
    queryClient.invalidateQueries({ queryKey: ['sessions', majorCode, activePeriod.period_code] })
    queryClient.invalidateQueries({ queryKey: ['dashboard', majorCode] })
  }

  async function handleRestoreAll() {
    if (!activePeriod) return
    await runJsonAction('/advising/sessions/restore-all', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, period_code: activePeriod.period_code }),
    })
    queryClient.invalidateQueries({ queryKey: ['sessions', majorCode, activePeriod.period_code] })
    queryClient.invalidateQueries({ queryKey: ['dashboard', majorCode] })
  }

  async function handleBulkRestore() {
    if (!activePeriod || !bulkStudentIds.length) return
    await runJsonAction('/advising/sessions/bulk-restore', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, period_code: activePeriod.period_code, student_ids: bulkStudentIds }),
    })
    queryClient.invalidateQueries({ queryKey: ['sessions', majorCode, activePeriod.period_code] })
  }

  async function handleRestoreSession(_sessionId: number, studentId: string) {
    if (!activePeriod) return
    const res = await authedFetch(`/advising/sessions/${majorCode}/${activePeriod.period_code}/${studentId}/restore`, { method: 'POST' })
    if (!res.ok) { showMsg('error', await res.text()); return }
    showMsg('success', 'Session restored.')
    queryClient.invalidateQueries({ queryKey: ['sessions', majorCode, activePeriod.period_code] })
  }

  async function handleDeleteSession(snapshotId: number) {
    if (!confirm('Delete this advising session? This cannot be undone.')) return
    const res = await authedFetch(`/advising/sessions/${majorCode}/snapshot/${snapshotId}`, { method: 'DELETE' })
    if (!res.ok) { showMsg('error', await res.text()); return }
    showMsg('success', 'Session deleted.')
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  // ── Period actions ───────────────────────────────────────────────────────
  async function handleCreatePeriod() {
    const res = await authedFetch('/periods', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ major_code: majorCode, semester: newSemester, year: newYear, advisor_name: newAdvisorName || 'Adviser' }),
    })
    const body = await res.json().catch(() => null)
    if (!res.ok) { showMsg('error', body?.detail || 'Could not create period.'); return }
    showMsg('success', `Period ${body.period_code} created and activated.`)
    setShowCreatePeriod(false)
    setNewAdvisorName('')
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
  }

  async function handleActivatePeriod(periodCode: string) {
    const res = await authedFetch(`/periods/${periodCode}/activate`, { method: 'POST' })
    const body = await res.json().catch(() => null)
    if (!res.ok) { showMsg('error', body?.detail || 'Could not activate period.'); return }
    showMsg('success', `${periodCode} is now the active period.`)
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
  }

  async function handleDeletePeriod(periodCode: string) {
    if (!confirm(`Delete period "${periodCode}"? This will remove all session history for this period. This cannot be undone.`)) return
    const res = await authedFetch(`/periods/${majorCode}/${periodCode}`, { method: 'DELETE' })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      showMsg('error', body?.detail || 'Could not delete period.')
      return
    }
    showMsg('success', 'Period deleted.')
    queryClient.invalidateQueries({ queryKey: ['periods', majorCode] })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  // ── Bulk placement upload ────────────────────────────────────────────────
  async function handlePlacementUpload() {
    if (!placementFile) return
    setPlacementUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', placementFile)
      const res = await authedFetch(`/advising/${majorCode}/placements/upload`, { method: 'POST', body: fd })
      if (!res.ok) { showMsg('error', await res.text()); return }
      const result = await res.json() as { processed: number; errors: string[] }
      const summary = `Placement report applied: ${result.processed} student(s) updated.`
      const errText = result.errors.length ? ` ${result.errors.length} row(s) skipped.` : ''
      showMsg(result.errors.length ? 'error' : 'success', summary + errText)
      setPlacementFile(null)
      queryClient.invalidateQueries({ queryKey: ['student-eligibility', majorCode] })
      queryClient.invalidateQueries({ queryKey: ['dataset-versions', majorCode] })
    } catch (err: unknown) {
      showMsg('error', err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setPlacementUploading(false)
    }
  }

  // ── Data file downloads ──────────────────────────────────────────────────
  async function handleDownloadFile(path: string, filename: string) {
    const res = await authedFetch(path)
    if (!res.ok) { showMsg('error', await res.text()); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename
    document.body.appendChild(a); a.click()
    a.remove(); URL.revokeObjectURL(url)
  }

  // ── Data file upload ─────────────────────────────────────────────────────
  async function handleUpload() {
    if (!uploadFile) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('major_code', majorCode)
      formData.append('dataset_type', uploadType)
      formData.append('file', uploadFile)
      const res = await authedFetch('/datasets/upload', { method: 'POST', body: formData })
      if (!res.ok) { showMsg('error', await res.text()); return }
      showMsg('success', `${DATASET_LABELS[uploadType] ?? uploadType} uploaded successfully.`)
      setUploadFile(null)
      queryClient.invalidateQueries({ queryKey: ['dataset-versions', majorCode] })
    } catch (err: unknown) {
      showMsg('error', err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <section className="settings-container stack" style={{ maxWidth: '1100px', margin: '0 auto' }}>
      {/* Header */}
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Configuration</div>
          <h2>Settings</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Program:</span>
          <select className="select-input" value={majorCode} onChange={(e) => setMajorCode(e.target.value)}>
            {allowedMajors.map((m) => <option key={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* Row 1: Period Management + Data Files */}
      <div className="grid-2 mb-6">
        {/* Period Management */}
        <div className="panel stack">
          <div className="flex-between mb-2">
            <h3 style={{ margin: 0 }}>
              Advising Period{' '}
              <Tooltip text="The active period determines which session data is shown. Create a new one at the start of each semester, or reactivate a past one." />
            </h3>
            <button type="button" className="btn-sm btn-outline" onClick={() => setShowCreatePeriod(v => !v)}>
              {showCreatePeriod ? 'Cancel' : '+ New Period'}
            </button>
          </div>

          <div style={{ padding: '0.6rem 0.9rem', borderRadius: '10px', background: activePeriod ? '#f0fdf4' : '#fef2f2', border: `1px solid ${activePeriod ? '#bbf7d0' : '#fecaca'}`, marginBottom: '0.75rem' }}>
            {activePeriod
              ? <><strong style={{ color: '#15803d' }}>Active:</strong> {activePeriod.semester} {activePeriod.year} &middot; {activePeriod.advisor_name}</>
              : <span style={{ color: '#dc2626' }}>No active period — create one below.</span>}
          </div>

          {showCreatePeriod && (
            <div style={{ padding: '0.9rem', background: '#f8fafc', borderRadius: '10px', border: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '0.75rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 700, display: 'block', marginBottom: '3px', textTransform: 'uppercase' }}>Semester</label>
                  <select className="select-input" value={newSemester} onChange={(e) => setNewSemester(e.target.value)}>
                    <option>Fall</option><option>Spring</option><option>Summer</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 700, display: 'block', marginBottom: '3px', textTransform: 'uppercase' }}>Year</label>
                  <input type="number" className="w-full" value={newYear} onChange={(e) => setNewYear(Number(e.target.value))} />
                </div>
              </div>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 700, display: 'block', marginBottom: '3px', textTransform: 'uppercase' }}>Adviser Name</label>
                <input className="w-full" value={newAdvisorName} onChange={(e) => setNewAdvisorName(e.target.value)} placeholder="e.g. Dr. Zahi Abdul Sater" />
              </div>
              <button type="button" className="btn-primary btn-sm" onClick={handleCreatePeriod}>Create &amp; Activate</button>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', maxHeight: '280px', overflowY: 'auto' }}>
            {periods.data?.length === 0 && (
              <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '1.5rem' }}>No periods yet.</p>
            )}
            {periods.data?.map(p => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.55rem 0.8rem', borderRadius: '8px', background: p.is_active ? '#f0fdf4' : '#fafafa', border: `1px solid ${p.is_active ? '#bbf7d0' : 'var(--line)'}` }}>
                <span style={{ fontSize: '0.875rem', fontWeight: p.is_active ? 700 : 400 }}>
                  {p.semester} {p.year} &middot; {p.advisor_name}
                  {p.is_active && <span style={{ marginLeft: '0.5rem', fontSize: '0.68rem', background: '#15803d', color: 'white', padding: '1px 6px', borderRadius: '4px' }}>ACTIVE</span>}
                </span>
                {!p.is_active && (
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.75rem' }} onClick={() => handleActivatePeriod(p.period_code)}>Activate</button>
                    <button type="button" className="btn-sm btn-outline" style={{ fontSize: '0.75rem', color: '#ef4444', borderColor: '#fca5a5' }} onClick={() => handleDeletePeriod(p.period_code)}>Delete</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Data Files */}
        <div className="panel stack">
          <h3 style={{ margin: 0, marginBottom: '0.4rem' }}>
            Data Files{' '}
            <Tooltip text="Upload the latest course catalog, student progress report, or email roster. Changes take effect immediately for this program." />
          </h3>
          <p className="text-sm text-muted" style={{ margin: '0 0 0.85rem' }}>
            Upload or replace program data files. Previous versions are archived.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', marginBottom: '0.85rem' }}>
            {Object.entries(DATASET_LABELS).map(([type, label]) => {
              const latestVersion = versions.data?.find(v => v.dataset_type === type)
              const isSelected = uploadType === type
              return (
                <label
                  key={type}
                  onClick={() => setUploadType(type)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr',
                    alignItems: 'start',
                    gap: '0.6rem',
                    padding: '0.65rem 0.9rem',
                    borderRadius: '10px',
                    border: `2px solid ${isSelected ? 'var(--accent)' : 'var(--line)'}`,
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(30,111,92,0.05)' : '#fafafa',
                    transition: 'border-color 0.15s, background 0.15s',
                  }}
                >
                  <input
                    type="radio"
                    name="uploadType"
                    value={type}
                    checked={isSelected}
                    onChange={() => setUploadType(type)}
                    style={{ accentColor: 'var(--accent)', marginTop: '3px', cursor: 'pointer' }}
                  />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: isSelected ? 600 : 400, color: 'var(--ink)' }}>{label}</div>
                    {latestVersion ? (
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>
                        Last: <span style={{ fontFamily: 'monospace' }}>{latestVersion.original_filename ?? '—'}</span>
                        {' · '}{new Date(latestVersion.created_at).toLocaleDateString()}
                        {(latestVersion.metadata_json?.uploaded_by as string | undefined) && <> · by {latestVersion.metadata_json.uploaded_by as string}</>}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>No file uploaded yet</div>
                    )}
                    <div style={{ display: 'flex', gap: '6px', marginTop: '2px' }}>
                      <button
                        type="button"
                        className="btn-sm btn-outline"
                        style={{ fontSize: '0.7rem', padding: '1px 8px' }}
                        onClick={(e) => { e.stopPropagation(); handleDownloadFile(`/datasets/templates/${type}`, `${type}_template.xlsx`) }}
                      >
                        ↓ Template
                      </button>
                      {latestVersion && (
                        <button
                          type="button"
                          className="btn-sm btn-outline"
                          style={{ fontSize: '0.7rem', padding: '1px 8px' }}
                          onClick={(e) => { e.stopPropagation(); handleDownloadFile(`/datasets/${majorCode}/${type}/download`, latestVersion.original_filename ?? `${type}.xlsx`) }}
                        >
                          ↓ Current File
                        </button>
                      )}
                    </div>
                  </div>
                </label>
              )
            })}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <label style={{ flex: 1, padding: '0.55rem 0.9rem', background: '#f8fafc', border: '1px dashed var(--line)', borderRadius: '10px', cursor: 'pointer', fontSize: '0.875rem', color: uploadFile ? 'var(--ink)' : 'var(--muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" />
              </svg>
              {uploadFile ? uploadFile.name : 'Choose .xlsx / .csv file…'}
              <input type="file" accept=".xlsx,.xls,.csv" style={{ display: 'none' }} onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
            </label>
            <button type="button" className="btn-primary btn-sm" disabled={!uploadFile || uploading} onClick={handleUpload} style={{ flexShrink: 0 }}>
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
          {uploadFile && (
            <button type="button" style={{ alignSelf: 'flex-start', fontSize: '0.75rem', color: 'var(--muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginTop: '4px' }} onClick={() => setUploadFile(null)}>
              ✕ Clear selection
            </button>
          )}
        </div>
      </div>

      {/* Bulk Placement Upload */}
      <div className="panel stack" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ margin: 0, marginBottom: '0.4rem' }}>
          Bulk Placement Upload{' '}
          <Tooltip text="Upload a CSV or Excel file with one row per student to set intensive course placements for all students at once. The system will automatically exclude lower-level intensive ancestors based on the placement course." />
        </h3>
        <p className="text-sm text-muted" style={{ margin: '0 0 0.85rem' }}>
          Set intensive course placements for all students in one go. Each row maps a student ID to the intensive course they placed into (e.g. ARAB201).
        </p>
        <div style={{ display: 'flex', gap: '6px', marginBottom: '0.85rem' }}>
          <button
            type="button"
            className="btn-sm btn-outline"
            style={{ fontSize: '0.7rem', padding: '1px 8px' }}
            onClick={() => handleDownloadFile('/datasets/templates/placements', 'placements_template.xlsx')}
          >
            ↓ Template
          </button>
          {(() => {
            const v = versions.data?.find(v => v.dataset_type === 'placements')
            return v ? (
              <button
                type="button"
                className="btn-sm btn-outline"
                style={{ fontSize: '0.7rem', padding: '1px 8px' }}
                onClick={() => handleDownloadFile(`/datasets/${majorCode}/placements/download`, v.original_filename ?? 'placements.xlsx')}
              >
                ↓ Current File
              </button>
            ) : null
          })()}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ flex: 1, padding: '0.55rem 0.9rem', background: '#f8fafc', border: '1px dashed var(--line)', borderRadius: '10px', cursor: 'pointer', fontSize: '0.875rem', color: placementFile ? 'var(--ink)' : 'var(--muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" />
            </svg>
            {placementFile ? placementFile.name : 'Choose .xlsx / .csv file…'}
            <input type="file" accept=".xlsx,.xls,.csv" style={{ display: 'none' }} onChange={(e) => setPlacementFile(e.target.files?.[0] || null)} />
          </label>
          <button type="button" className="btn-primary btn-sm" disabled={!placementFile || placementUploading} onClick={handlePlacementUpload} style={{ flexShrink: 0 }}>
            {placementUploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {placementFile && (
          <button type="button" style={{ alignSelf: 'flex-start', fontSize: '0.75rem', color: 'var(--muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginTop: '4px' }} onClick={() => setPlacementFile(null)}>
            ✕ Clear selection
          </button>
        )}
      </div>

      {/* Row 2: Session Management + Session History */}
      <div className="grid-2">
        {/* Session Management */}
        <div className="panel stack">
          <h3 style={{ margin: 0, marginBottom: '0.5rem' }}>Session Management</h3>
          <p className="text-sm text-muted mb-4">
            Active period: <strong>{activePeriod ? `${activePeriod.semester} ${activePeriod.year} · ${activePeriod.advisor_name}` : 'None'}</strong>
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <button type="button" className="btn-secondary" style={{ flex: 1 }} onClick={handleClearSelections} disabled={!activePeriod} title="Remove all saved course selections for all students in the active period">Clear All Selections</button>
            <button type="button" className="btn-secondary" style={{ flex: 1 }} onClick={handleRestoreAll} disabled={!activePeriod} title="Restore everyone's last saved session">Restore All Sessions</button>
          </div>
          <div style={{ borderTop: '1px solid var(--line)', paddingTop: '0.75rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase' }}>
              Bulk Restore — Select Students
            </label>
            <input className="w-full" value={studentQuery} onChange={(e) => setStudentQuery(e.target.value)} placeholder="Filter by name or ID" style={{ marginBottom: '0.5rem' }} />
            <select className="select-input" multiple size={5} value={bulkStudentIds} onChange={(e) => setBulkStudentIds(getSelectedValues(e))}>
              {students.data?.map((s) => <option key={s.student_id} value={s.student_id}>{s.student_name} · {s.student_id}</option>)}
            </select>
            <button type="button" className="btn-primary btn-sm" style={{ marginTop: '0.6rem' }} onClick={handleBulkRestore} disabled={!activePeriod || !bulkStudentIds.length}>
              Restore Selected ({bulkStudentIds.length})
            </button>
          </div>
        </div>

        {/* Session History */}
        <div className="panel stack">
          <div className="flex-between mb-3">
            <h3 style={{ margin: 0 }}>
              Session History{' '}
              <Tooltip text="All saved advising sessions for the active period. Search by student name or ID, then restore any session." />
            </h3>
            <span className="badge badge-info">{sessions.data?.length ?? 0} sessions</span>
          </div>
          <input type="search" className="search-input mb-3" placeholder="Search by student name or ID…" value={sessionSearch} onChange={(e) => setSessionSearch(e.target.value)} />
          {(() => {
            const q = sessionSearch.toLowerCase()
            const filtered = (sessions.data ?? [])
              .filter(s => !q || s.student_name.toLowerCase().includes(q) || s.student_id.toLowerCase().includes(q))
              .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            if (filtered.length === 0) {
              return <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>{sessions.data?.length ? 'No sessions match your search.' : 'No sessions saved for the active period.'}</p>
            }
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '380px', overflowY: 'auto' }}>
                {filtered.map(session => (
                  <div key={session.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.65rem 0.9rem', background: '#fafafa', borderRadius: '10px', border: '1px solid var(--line)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.875rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session.student_name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--muted)', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '2px' }}>
                        <span className="mono">{session.student_id}</span>
                        <span>&middot;</span>
                        <span>{new Date(session.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        {session.summary && typeof session.summary === 'object' && (
                          <><span>&middot;</span><span>{(session.summary as any).advised?.length ?? 0} advised, {(session.summary as any).optional?.length ?? 0} optional</span></>
                        )}
                      </div>
                    </div>
                    <button type="button" style={{ flexShrink: 0, padding: '4px 12px', fontSize: '0.78rem', background: 'transparent', border: '1px solid var(--line)', borderRadius: '8px', color: 'var(--ink)', cursor: 'pointer' }} onClick={() => handleRestoreSession(session.id, session.student_id)}>
                      Restore
                    </button>
                    <button type="button" style={{ flexShrink: 0, padding: '4px 12px', fontSize: '0.78rem', background: 'transparent', border: '1px solid #fca5a5', borderRadius: '8px', color: '#ef4444', cursor: 'pointer' }} onClick={() => handleDeleteSession(session.id)}>
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>
      </div>
    </section>
  )
}
