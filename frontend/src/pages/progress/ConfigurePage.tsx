import { useState, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMajorContext } from '../../lib/MajorContext'
import { useProgressEquivalents, useProgressAssignmentTypes, useDatasetVersions } from '../../lib/hooks'
import {
  setProgressEquivalents,
  createProgressAssignmentType,
  deleteProgressAssignmentType,
  uploadElectiveAssignments,
  API_BASE_URL,
  type EquivalentCourse,
} from '../../lib/api'

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

// ─── Equivalents panel ───────────────────────────────────────────

function EquivalentsPanel({ majorCode }: { majorCode: string }) {
  const qc = useQueryClient()
  const equivQuery = useProgressEquivalents(majorCode)
  const [rows, setRows] = useState<{ alias_code: string; canonical_code: string }[]>([])
  const [initialised, setInitialised] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Seed local state once data arrives
  useEffect(() => {
    if (!initialised && equivQuery.data) {
      setRows(equivQuery.data.map((e) => ({ alias_code: e.alias_code, canonical_code: e.canonical_code })))
      setInitialised(true)
    }
  }, [equivQuery.data, initialised])

  function addRow() {
    setRows((prev) => [...prev, { alias_code: '', canonical_code: '' }])
  }

  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i))
  }

  function updateRow(i: number, field: 'alias_code' | 'canonical_code', value: string) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)))
  }

  async function handleSave() {
    setSaving(true)
    setMsg(null)
    try {
      const saved = await setProgressEquivalents(majorCode, rows.filter((r) => r.alias_code && r.canonical_code))
      setRows(saved.map((e) => ({ alias_code: e.alias_code, canonical_code: e.canonical_code })))
      setMsg({ type: 'success', text: 'Equivalents saved.' })
      qc.invalidateQueries({ queryKey: ['progress-equivalents', majorCode] })
    } catch (err: unknown) {
      setMsg({ type: 'error', text: err instanceof Error ? err.message : 'Save failed.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel stack">
      <div className="panel-header mb-3">
        <h3>Course Equivalents</h3>
        <p className="text-muted text-sm">
          Map alternative course codes (aliases) to canonical codes used in the configuration.
          During report processing, all aliases are automatically replaced by their canonical code.
        </p>
      </div>

      {equivQuery.isLoading ? (
        <div className="text-muted text-sm">Loading…</div>
      ) : (
        <>
          <div className="premium-table-wrapper">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Alias Code</th>
                  <th>Canonical Code</th>
                  <th style={{ width: 48 }} />
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr><td colSpan={3} className="text-muted text-center">No equivalents defined.</td></tr>
                ) : (
                  rows.map((row, i) => (
                    <tr key={i}>
                      <td>
                        <input
                          className="input-inline"
                          value={row.alias_code}
                          placeholder="e.g. CHEM100"
                          onChange={(e) => updateRow(i, 'alias_code', e.target.value.toUpperCase())}
                        />
                      </td>
                      <td>
                        <input
                          className="input-inline"
                          value={row.canonical_code}
                          placeholder="e.g. CHEM201"
                          onChange={(e) => updateRow(i, 'canonical_code', e.target.value.toUpperCase())}
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-icon text-danger"
                          onClick={() => removeRow(i)}
                          title="Remove row"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex-between mt-3">
            <button type="button" className="btn btn-secondary" onClick={addRow}>+ Add Row</button>
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save Equivalents'}
            </button>
          </div>
          {msg && <div className={`alert alert-${msg.type} mt-2`}>{msg.text}</div>}
        </>
      )}
    </div>
  )
}

// ─── Assignment types panel ──────────────────────────────────────

function AssignmentTypesPanel({ majorCode }: { majorCode: string }) {
  const qc = useQueryClient()
  const typesQuery = useProgressAssignmentTypes(majorCode)
  const [newLabel, setNewLabel] = useState('')
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  async function handleCreate() {
    if (!newLabel.trim()) return
    setCreating(true)
    setMsg(null)
    try {
      await createProgressAssignmentType(majorCode, newLabel.trim())
      setNewLabel('')
      qc.invalidateQueries({ queryKey: ['progress-assignment-types', majorCode] })
      setMsg({ type: 'success', text: `'${newLabel.trim()}' created.` })
    } catch (err: unknown) {
      setMsg({ type: 'error', text: err instanceof Error ? err.message : 'Create failed.' })
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number, label: string) {
    if (!window.confirm(`Delete assignment type '${label}'? This will fail if any students are still assigned.`)) return
    setDeletingId(id)
    setMsg(null)
    try {
      await deleteProgressAssignmentType(majorCode, id)
      qc.invalidateQueries({ queryKey: ['progress-assignment-types', majorCode] })
      setMsg({ type: 'success', text: `'${label}' deleted.` })
    } catch (err: unknown) {
      setMsg({ type: 'error', text: err instanceof Error ? err.message : 'Delete failed.' })
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="panel stack">
      <div className="panel-header mb-3">
        <h3>Assignment Type Labels</h3>
        <p className="text-muted text-sm">
          Define named labels (e.g. S.C.E, F.E.C) that can be assigned to individual students'
          course slots. Assignments replace the course code in the report pivot.
        </p>
      </div>

      {typesQuery.isLoading ? (
        <div className="text-muted text-sm">Loading…</div>
      ) : (
        <>
          <div className="premium-table-wrapper">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Sort Order</th>
                  <th style={{ width: 48 }} />
                </tr>
              </thead>
              <tbody>
                {(!typesQuery.data || typesQuery.data.length === 0) ? (
                  <tr><td colSpan={3} className="text-muted text-center">No assignment types defined.</td></tr>
                ) : (
                  typesQuery.data.map((at) => (
                    <tr key={at.id}>
                      <td className="font-semibold">{at.label}</td>
                      <td>{at.sort_order}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-icon text-danger"
                          onClick={() => handleDelete(at.id, at.label)}
                          disabled={deletingId === at.id}
                          title="Delete"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /></svg>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex-row gap-2 mt-3">
            <input
              className="text-input flex-1"
              placeholder="New label, e.g. S.C.E"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
            />
            <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={creating || !newLabel.trim()}>
              {creating ? 'Adding…' : '+ Add'}
            </button>
          </div>
          {msg && <div className={`alert alert-${msg.type} mt-2`}>{msg.text}</div>}
        </>
      )}
    </div>
  )
}

// ─── Bulk elective assignments panel ───────────────────────────

function BulkElectivePanel({ majorCode }: { majorCode: string }) {
  const versions = useDatasetVersions(majorCode)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const activeVersions: Record<string, { original_filename: string | null }> = {}
  for (const v of versions.data ?? []) {
    if (v.is_active) activeVersions[v.dataset_type] = v
  }

  async function handleFile(file: File | undefined) {
    if (!file) return
    setMsg(null)
    setLoading(true)
    try {
      const result = await uploadElectiveAssignments(majorCode, file)
      const summary = `Done — ${result.upserted} upserted, ${result.skipped} skipped.`
      const detail = result.errors.length > 0
        ? `\n\nRow errors:\n${result.errors.slice(0, 10).join('\n')}${result.errors.length > 10 ? `\n…and ${result.errors.length - 10} more` : ''}`
        : ''
      setMsg({ type: result.skipped > 0 && result.upserted === 0 ? 'error' : 'success', text: summary + detail })
    } catch (err: unknown) {
      setMsg({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed.' })
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="panel stack">
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
        >
          {loading ? 'Uploading…' : 'Choose File & Upload'}
        </button>
        <span className="text-muted text-sm">Accepted: .xlsx, .xls</span>
      </div>
      {msg && <div className={`alert alert-${msg.type} mt-2`} style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────

export function ConfigurePage() {
  const { majorCode, setMajorCode, allowedMajors } = useMajorContext()

  return (
    <section className="stack">
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Academic Progress</div>
          <h2>Configure</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Major:</span>
          <select className="select-input" value={majorCode} onChange={(e) => setMajorCode(e.target.value)}>
            {allowedMajors.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {majorCode ? (
        <>
          <div className="grid-2">
            <EquivalentsPanel majorCode={majorCode} />
            <AssignmentTypesPanel majorCode={majorCode} />
          </div>
          <BulkElectivePanel majorCode={majorCode} />
        </>
      ) : (
        <div className="empty-state">Select a major to configure.</div>
      )}
    </section>
  )
}
