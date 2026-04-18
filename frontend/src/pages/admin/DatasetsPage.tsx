import { FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { API_BASE_URL } from '../../lib/api'
import { useDatasetVersions, useMajors } from '../../lib/hooks'

const datasetTypes = ['courses', 'progress', 'advising_selections', 'email_roster']
const TEMPLATED_TYPES = new Set(['courses', 'progress', 'email_roster'])

const TYPE_LABELS: Record<string, string> = {
  courses: 'Course Catalog',
  progress: 'Progress Report',
  advising_selections: 'Advising Selections',
  email_roster: 'Email Roster',
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

async function downloadBlob(path: string, filename: string) {
  const r = await authedFetch(path)
  if (!r.ok) return
  const blob = await r.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove()
  window.URL.revokeObjectURL(url)
}

export function DatasetsPage() {
  const queryClient = useQueryClient()
  const majors = useMajors()
  const [majorCode, setMajorCode] = useState('PBHL')
  const [datasetType, setDatasetType] = useState('courses')
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const versions = useDatasetVersions(majorCode)

  async function handleUpload(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    try {
      const formData = new FormData()
      formData.append('major_code', majorCode)
      formData.append('dataset_type', datasetType)
      formData.append('file', file)
      const response = await authedFetch('/datasets/upload', { method: 'POST', body: formData })
      if (!response.ok) {
        setMessage({ type: 'error', text: await response.text() })
        return
      }
      setMessage({ type: 'success', text: 'Dataset uploaded successfully.' })
      setFile(null)
      queryClient.invalidateQueries({ queryKey: ['dataset-versions', majorCode] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed.' })
    }
  }

  async function handleActivateVersion(versionId: number) {
    const r = await authedFetch(`/datasets/${versionId}/activate`, { method: 'POST' })
    if (!r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Version set as active.' })
    queryClient.invalidateQueries({ queryKey: ['dataset-versions', majorCode] })
  }

  async function handleDeleteVersion(versionId: number) {
    const r = await authedFetch(`/datasets/${versionId}`, { method: 'DELETE' })
    setDeletingId(null)
    if (r.status !== 204 && !r.ok) { setMessage({ type: 'error', text: await r.text() }); return }
    setMessage({ type: 'success', text: 'Version deleted.' })
    queryClient.invalidateQueries({ queryKey: ['dataset-versions', majorCode] })
  }

  return (
    <section className="stack" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="page-header flex-between mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Datasets</h2>
        </div>
        <label className="inline-select">
          <span className="text-muted">Program:</span>
          <select className="select-input" value={majorCode} onChange={(e) => setMajorCode(e.target.value)}>
            {majors.data?.map((m) => <option key={m.code}>{m.code}</option>)}
          </select>
        </label>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* Upload form */}
      <form className="panel stack mb-6" onSubmit={handleUpload}>
        <h3 style={{ margin: 0, marginBottom: '0.75rem' }}>Upload New Version</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Dataset Type</label>
            <select className="select-input" value={datasetType} onChange={(e) => setDatasetType(e.target.value)}>
              {datasetTypes.map((t) => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>File</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', background: '#f8fafc', border: '1px dashed var(--line)', borderRadius: '8px', cursor: 'pointer', fontSize: '0.875rem', color: file ? 'var(--ink)' : 'var(--muted)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" x2="12" y1="3" y2="15" />
              </svg>
              {file ? file.name : 'Choose file…'}
              <input type="file" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </label>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button type="submit" className="btn-primary btn-sm" disabled={!file}>Upload Dataset</button>
          {file && (
            <button type="button" className="btn-sm btn-outline" onClick={() => setFile(null)}>Clear</button>
          )}
          {TEMPLATED_TYPES.has(datasetType) && (
            <button type="button" className="btn-sm btn-outline" onClick={() => downloadBlob(`/datasets/templates/${datasetType}`, `${datasetType}_template.xlsx`)}>↓ Template</button>
          )}
        </div>
      </form>

      {/* Version history */}
      <div className="panel">
        <h3 style={{ margin: '0 0 1rem' }}>Version History</h3>
        {versions.isLoading ? (
          <p className="text-muted text-sm">Loading…</p>
        ) : versions.data?.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No versions uploaded yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Label</th>
                  <th>Filename</th>
                  <th>Uploaded By</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {versions.data?.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <span style={{ fontSize: '0.75rem', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                        {TYPE_LABELS[v.dataset_type] ?? v.dataset_type}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.875rem' }}>{v.version_label}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'monospace' }}>{v.original_filename ?? '—'}</td>
                    <td style={{ fontSize: '0.875rem' }}>{(v.metadata_json?.uploaded_by as string | undefined) ?? '—'}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{new Date(v.created_at).toLocaleString()}</td>
                    <td>
                      {v.is_active
                        ? <span style={{ fontSize: '0.7rem', background: '#dcfce7', color: '#15803d', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>Active</span>
                        : <span style={{ fontSize: '0.7rem', color: 'var(--muted)', padding: '2px 8px' }}>—</span>
                      }
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                        {v.original_filename && (
                          <button type="button" className="btn-sm btn-outline" title="Download file" onClick={() => downloadBlob(`/datasets/${majorCode}/${v.dataset_type}/download`, v.original_filename ?? 'file')}>
                            ↓
                          </button>
                        )}
                        {!v.is_active && (
                          <button type="button" className="btn-sm btn-outline" onClick={() => handleActivateVersion(v.id)}>Set Active</button>
                        )}
                        {!v.is_active && (
                          deletingId === v.id ? (
                            <>
                              <button type="button" className="btn-sm" style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', padding: '4px 8px', fontSize: '0.75rem', cursor: 'pointer' }} onClick={() => handleDeleteVersion(v.id)}>Del</button>
                              <button type="button" className="btn-sm btn-outline" onClick={() => setDeletingId(null)}>✕</button>
                            </>
                          ) : (
                            <button type="button" className="btn-sm btn-outline" style={{ color: '#ef4444', borderColor: '#fca5a5' }} onClick={() => setDeletingId(v.id)}>Delete</button>
                          )
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
