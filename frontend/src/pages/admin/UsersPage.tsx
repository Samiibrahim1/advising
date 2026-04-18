import { FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { createUser, updateUser, deleteUser, toggleUserActive, type UserRecord } from '../../lib/api'
import { useMajors, useUsers } from '../../lib/hooks'

const LABEL: React.CSSProperties = { display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase' }

function MajorCheckboxes({ majors, selected, onChange }: {
  majors: { code: string; name: string }[]
  selected: string[]
  onChange: (codes: string[]) => void
}) {
  function toggle(code: string) {
    onChange(selected.includes(code) ? selected.filter(c => c !== code) : [...selected, code])
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '4px' }}>
      {majors.map(m => (
        <label key={m.code} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.82rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={selected.includes(m.code)} onChange={() => toggle(m.code)} />
          {m.code}
        </label>
      ))}
    </div>
  )
}

export function UsersPage() {
  const queryClient = useQueryClient()
  const majors = useMajors()
  const users = useUsers()

  // ── Create form ───────────────────────────────────────────────
  const [payload, setPayload] = useState({ email: '', full_name: '', password: '', role: 'adviser', major_codes: [] as string[] })
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // ── Edit form ─────────────────────────────────────────────────
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null)
  const [editPayload, setEditPayload] = useState({ full_name: '', role: '', major_codes: [] as string[], new_password: '' })

  // ── Delete confirm ────────────────────────────────────────────
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  function startEdit(u: UserRecord) {
    setEditingUser(u)
    setEditPayload({ full_name: u.full_name, role: u.role, major_codes: u.major_codes ?? [], new_password: '' })
  }

  function cancelEdit() {
    setEditingUser(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await createUser(payload)
      setMessage({ type: 'success', text: `User ${payload.full_name} created.` })
      setPayload({ email: '', full_name: '', password: '', role: 'adviser', major_codes: [] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Creation failed.' })
    }
  }

  async function handleSaveEdit() {
    if (!editingUser) return
    try {
      await updateUser(editingUser.id, {
        full_name: editPayload.full_name,
        role: editPayload.role,
        major_codes: editPayload.major_codes,
        ...(editPayload.new_password.trim() ? { new_password: editPayload.new_password } : {}),
      })
      setMessage({ type: 'success', text: `${editPayload.full_name} updated.` })
      setEditingUser(null)
      queryClient.invalidateQueries({ queryKey: ['users'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Update failed.' })
    }
  }

  async function handleToggle(userId: number, isActive: boolean) {
    const action = isActive ? 'deactivated' : 'activated'
    try {
      await toggleUserActive(userId, isActive)
      setMessage({ type: 'success', text: `User ${action}.` })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Toggle failed.' })
    }
  }

  async function handleDelete(userId: number) {
    try {
      await deleteUser(userId)
      setConfirmDeleteId(null)
      setMessage({ type: 'success', text: 'User deleted.' })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Delete failed.' })
    }
  }

  const majorList = majors.data ?? []

  return (
    <section className="stack" style={{ maxWidth: '960px', margin: '0 auto' }}>
      <div className="page-header mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Users &amp; Access</h2>
        </div>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* ── Edit panel ──────────────────────────────────────────── */}
      {editingUser && (
        <div className="panel stack mb-5" style={{ border: '2px solid var(--primary, #3b82f6)' }}>
          <h3 style={{ margin: 0, marginBottom: '0.75rem' }}>Editing: {editingUser.full_name}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={LABEL}>Full Name</label>
              <input value={editPayload.full_name} onChange={e => setEditPayload({ ...editPayload, full_name: e.target.value })} />
            </div>
            <div>
              <label style={LABEL}>Role</label>
              <select className="select-input" value={editPayload.role} onChange={e => setEditPayload({ ...editPayload, role: e.target.value })}>
                <option value="admin">Admin</option>
                <option value="adviser">Adviser</option>
              </select>
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={LABEL}>New Password (leave blank to keep current)</label>
              <input type="password" placeholder="New password…" value={editPayload.new_password} onChange={e => setEditPayload({ ...editPayload, new_password: e.target.value })} />
            </div>
          </div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={LABEL}>Major Access</label>
            <MajorCheckboxes majors={majorList} selected={editPayload.major_codes} onChange={codes => setEditPayload({ ...editPayload, major_codes: codes })} />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveEdit}>Save Changes</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={cancelEdit}>Cancel</button>
          </div>
        </div>
      )}

      {/* ── Create form ─────────────────────────────────────────── */}
      <form className="panel stack mb-6" onSubmit={handleSubmit}>
        <h3 style={{ margin: 0, marginBottom: '0.75rem' }}>Create New User</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={LABEL}>Full Name</label>
            <input required value={payload.full_name} onChange={e => setPayload({ ...payload, full_name: e.target.value })} placeholder="Dr. Jane Smith" />
          </div>
          <div>
            <label style={LABEL}>Email</label>
            <input required type="email" value={payload.email} onChange={e => setPayload({ ...payload, email: e.target.value })} placeholder="jsmith@example.com" />
          </div>
          <div>
            <label style={LABEL}>Password</label>
            <input required type="password" value={payload.password} onChange={e => setPayload({ ...payload, password: e.target.value })} placeholder="Temporary password" />
          </div>
          <div>
            <label style={LABEL}>Role</label>
            <select className="select-input" value={payload.role} onChange={e => setPayload({ ...payload, role: e.target.value })}>
              <option value="admin">Admin</option>
              <option value="adviser">Adviser</option>
            </select>
          </div>
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={LABEL}>Major Access</label>
          <MajorCheckboxes majors={majorList} selected={payload.major_codes} onChange={codes => setPayload({ ...payload, major_codes: codes })} />
        </div>
        <button type="submit" className="btn-primary btn-sm" style={{ alignSelf: 'flex-start' }}>Create User</button>
      </form>

      {/* ── Users table ───────────────────────────────────────────── */}
      <div className="panel">
        <h3 style={{ margin: '0 0 1rem' }}>All Users</h3>
        {users.data?.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No users yet.</p>
        ) : (
          <table className="premium-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Majors</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.data?.map(u => (
                <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.55 }}>
                  <td style={{ fontWeight: 600, fontSize: '0.875rem' }}>{u.full_name}</td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--muted)', fontFamily: 'monospace' }}>{u.email}</td>
                  <td>
                    <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', fontWeight: 600, background: u.role === 'admin' ? '#fdf4ff' : '#eff6ff', color: u.role === 'admin' ? '#7e22ce' : '#1d4ed8' }}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                    {u.major_codes?.length ? u.major_codes.join(', ') : <span style={{ color: '#94a3b8' }}>—</span>}
                  </td>
                  <td>
                    <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', fontWeight: 600, background: u.is_active ? '#f0fdf4' : '#f1f5f9', color: u.is_active ? '#15803d' : '#94a3b8' }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                      <button
                        type="button"
                        className="btn-sm btn-outline"
                        style={{ fontSize: '0.72rem' }}
                        onClick={() => { setConfirmDeleteId(null); startEdit(u) }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-sm btn-outline"
                        style={{ fontSize: '0.72rem', color: u.is_active ? '#dc2626' : '#15803d', borderColor: u.is_active ? '#fecaca' : '#bbf7d0' }}
                        onClick={() => handleToggle(u.id, u.is_active)}
                      >
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                      {confirmDeleteId === u.id ? (
                        <>
                          <button
                            type="button"
                            className="btn-sm"
                            style={{ fontSize: '0.72rem', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', padding: '3px 8px', cursor: 'pointer' }}
                            onClick={() => handleDelete(u.id)}
                          >
                            Confirm
                          </button>
                          <button
                            type="button"
                            className="btn-sm btn-outline"
                            style={{ fontSize: '0.72rem' }}
                            onClick={() => setConfirmDeleteId(null)}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="btn-sm btn-outline"
                          style={{ fontSize: '0.72rem', color: '#dc2626', borderColor: '#fecaca' }}
                          onClick={() => { setEditingUser(null); setConfirmDeleteId(u.id) }}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
