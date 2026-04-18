import { FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { createMajor, updateMajor, revealSmtpPassword, deleteMajor, Major } from '../../lib/api'
import { useMajors } from '../../lib/hooks'

export function MajorsPage() {
  const queryClient = useQueryClient()
  const majors = useMajors()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Edit modal state
  const [editing, setEditing] = useState<Major | null>(null)
  const [editName, setEditName] = useState('')
  const [editSmtpEmail, setEditSmtpEmail] = useState('')
  const [editSmtpPassword, setEditSmtpPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleDelete(majorCode: string) {
    if (!confirm(`Delete major "${majorCode}" and ALL its data (datasets, periods, selections, snapshots)? This cannot be undone.`)) return
    setDeleting(majorCode)
    try {
      await deleteMajor(majorCode)
      setMessage({ type: 'success', text: `Major ${majorCode} deleted.` })
      queryClient.invalidateQueries({ queryKey: ['majors'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to delete major.' })
    } finally { setDeleting(null) }
  }

  function openEdit(m: Major) {
    setEditing(m)
    setEditName(m.name)
    setEditSmtpEmail(m.smtp_email || '')
    setEditSmtpPassword('')
    setShowPassword(false)
  }

  async function handleRevealPassword() {
    if (!editing) return
    try {
      const res = await revealSmtpPassword(editing.code)
      setEditSmtpPassword(res.smtp_password)
      setShowPassword(true)
    } catch {
      setMessage({ type: 'error', text: 'Failed to reveal SMTP password.' })
    }
  }

  async function handleEditSave(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    setSaving(true)
    try {
      const payload: Record<string, string> = {}
      if (editName.trim() !== editing.name) payload.name = editName.trim()
      if (editSmtpEmail.trim() !== (editing.smtp_email || '')) payload.smtp_email = editSmtpEmail.trim()
      if (editSmtpPassword) payload.smtp_password = editSmtpPassword
      if (Object.keys(payload).length === 0) { setEditing(null); setSaving(false); return }
      await updateMajor(editing.code, payload)
      setMessage({ type: 'success', text: `Major ${editing.code} updated.` })
      queryClient.invalidateQueries({ queryKey: ['majors'] })
      setEditing(null)
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update major.' })
    } finally { setSaving(false) }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      const m = await createMajor({ code: code.trim().toUpperCase(), name: name.trim() })
      setMessage({ type: 'success', text: `Major ${m.code} — ${m.name} created.` })
      setCode('')
      setName('')
      queryClient.invalidateQueries({ queryKey: ['majors'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to create major.' })
    }
  }

  return (
    <section className="stack" style={{ maxWidth: '700px', margin: '0 auto' }}>
      <div className="page-header mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Majors</h2>
        </div>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      <form className="panel stack mb-6" onSubmit={handleSubmit}>
        <h3 style={{ margin: 0, marginBottom: '0.75rem' }}>Create New Major</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }}>
              Code
            </label>
            <input
              required
              value={code}
              onChange={e => setCode(e.target.value)}
              placeholder="e.g. PBHL"
              style={{ textTransform: 'uppercase' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }}>
              Full Name
            </label>
            <input
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Public Health"
            />
          </div>
        </div>
        <button type="submit" className="btn-primary btn-sm" style={{ alignSelf: 'flex-start' }}>
          Create Major
        </button>
      </form>

      <div className="panel">
        <h3 style={{ margin: '0 0 1rem' }}>All Majors</h3>
        {!majors.data || majors.data.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No majors yet.</p>
        ) : (
          <table className="premium-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>SMTP</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {majors.data.map(m => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 700, fontFamily: 'monospace', fontSize: '0.85rem' }}>{m.code}</td>
                  <td style={{ fontSize: '0.875rem' }}>{m.name}</td>
                  <td>
                    <span style={{
                      fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', fontWeight: 600,
                      background: m.smtp_configured ? '#f0fdf4' : '#fef2f2',
                      color: m.smtp_configured ? '#15803d' : '#dc2626',
                    }}>
                      {m.smtp_configured ? m.smtp_email : 'Not Set'}
                    </span>
                  </td>
                  <td>
                    <span style={{
                      fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', fontWeight: 600,
                      background: m.is_active ? '#f0fdf4' : '#f1f5f9',
                      color: m.is_active ? '#15803d' : '#94a3b8',
                    }}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button className="btn-sm" style={{ fontSize: '0.75rem', padding: '2px 10px' }} onClick={() => openEdit(m)}>Edit</button>
                      <button
                        className="btn-sm"
                        style={{ fontSize: '0.75rem', padding: '2px 10px', color: '#dc2626', borderColor: '#fca5a5' }}
                        disabled={deleting === m.code}
                        onClick={() => handleDelete(m.code)}
                      >
                        {deleting === m.code ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Edit Modal */}
      {editing && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
             onClick={() => setEditing(null)}>
          <form className="panel stack" style={{ width: '440px', maxHeight: '90vh', overflow: 'auto' }}
                onClick={e => e.stopPropagation()} onSubmit={handleEditSave}>
            <h3 style={{ margin: 0 }}>Edit Major — {editing.code}</h3>

            <div>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }}>Name</label>
              <input value={editName} onChange={e => setEditName(e.target.value)} required />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', marginTop: '0.25rem' }}>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>SMTP Settings (Microsoft 365)</h4>
              <div>
                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }}>Sender Email</label>
                <input type="email" value={editSmtpEmail} onChange={e => setEditSmtpEmail(e.target.value)} placeholder="e.g. cph@pu.edu.lb" />
              </div>
              <div style={{ marginTop: '0.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }}>SMTP Password</label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={editSmtpPassword}
                    onChange={e => setEditSmtpPassword(e.target.value)}
                    placeholder={editing.smtp_configured ? '••••••••  (unchanged if empty)' : 'Not set'}
                    style={{ flex: 1 }}
                  />
                  {editing.smtp_configured && !editSmtpPassword && (
                    <button type="button" className="btn-sm" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }} onClick={handleRevealPassword}>
                      Reveal
                    </button>
                  )}
                  {editSmtpPassword && (
                    <button type="button" className="btn-sm" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }} onClick={() => setShowPassword(!showPassword)}>
                      {showPassword ? 'Hide' : 'Show'}
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
              <button type="button" className="btn-sm" onClick={() => setEditing(null)}>Cancel</button>
              <button type="submit" className="btn-primary btn-sm" disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}
