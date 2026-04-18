import { FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { apiFetch, AppTemplate } from '../../lib/api'
import { useTemplates } from '../../lib/hooks'

const BLANK_PAYLOAD = {
  major_code: 'PBHL',
  template_key: 'default',
  display_name: 'Standard Advising',
  description: '',
  subject_template: 'Academic Advising – {major} {semester} {year}',
  body_template: 'Dear {student_name},\n\nPlease find your advising recommendations below.\n\n{advised_courses}\n\n{optional_courses}\n\nBest regards,\n{advisor_name}',
  include_summary: true,
}

const VARIABLES = [
  { tag: '{student_name}', note: 'Student full name' },
  { tag: '{major}', note: 'Major code (e.g. PBHL)' },
  { tag: '{semester}', note: 'Semester label' },
  { tag: '{year}', note: 'Academic year' },
  { tag: '{advisor_name}', note: 'Adviser name' },
  { tag: '{advised_courses}', note: 'Formatted advised courses list' },
  { tag: '{optional_courses}', note: 'Optional/elective courses list' },
]

export function TemplatesPage() {
  const queryClient = useQueryClient()
  const templates = useTemplates()
  const [payload, setPayload] = useState(BLANK_PAYLOAD)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  function loadTemplate(template: AppTemplate) {
    setPayload({
      major_code: '',           // templates are global; major scoping done via template_key
      template_key: template.template_key,
      display_name: template.display_name,
      description: template.description ?? '',
      subject_template: template.subject_template,
      body_template: template.body_template,
      include_summary: template.include_summary,
    })
    setEditingId(template.id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function handleReset() {
    setPayload(BLANK_PAYLOAD)
    setEditingId(null)
    setMessage(null)
  }

  function insertVariable(tag: string) {
    setPayload(prev => ({ ...prev, body_template: prev.body_template + tag }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await apiFetch<AppTemplate>('/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      setMessage({ type: 'success', text: editingId ? 'Template updated.' : 'Template created.' })
      setEditingId(null)
      queryClient.invalidateQueries({ queryKey: ['templates'] })
    } catch (err: unknown) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Save failed.' })
    }
  }

  return (
    <section className="stack" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="page-header mb-4">
        <div>
          <div className="eyebrow text-muted">Admin Panel</div>
          <h2>Email Templates</h2>
        </div>
      </div>

      {message && (
        <div className={`alert mb-4 ${message.type === 'error' ? 'alert-error' : 'alert-success'}`}>
          {message.text}
          <button type="button" className="close-btn" onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      {/* Edit / Create form */}
      <form className="panel stack mb-6" onSubmit={handleSubmit}>
        <div className="flex-between mb-3">
          <h3 style={{ margin: 0 }}>{editingId ? 'Edit Template' : 'New Template'}</h3>
          {editingId && (
            <button type="button" className="btn-sm btn-outline" onClick={handleReset}>
              + New Template
            </button>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Template Key</label>
            <input value={payload.template_key} onChange={(e) => setPayload({ ...payload, template_key: e.target.value })} placeholder="e.g. default" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Display Name</label>
            <input value={payload.display_name} onChange={(e) => setPayload({ ...payload, display_name: e.target.value })} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</label>
            <input value={payload.description} onChange={(e) => setPayload({ ...payload, description: e.target.value })} placeholder="Optional" />
          </div>
        </div>

        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Subject Line</label>
          <input className="w-full" value={payload.subject_template} onChange={(e) => setPayload({ ...payload, subject_template: e.target.value })} />
        </div>

        {/* Body + variable hints side-by-side */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', gap: '0.75rem', alignItems: 'start' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Body Template</label>
            <textarea
              rows={12}
              className="w-full"
              style={{ fontFamily: 'monospace', fontSize: '0.85rem', resize: 'vertical' }}
              value={payload.body_template}
              onChange={(e) => setPayload({ ...payload, body_template: e.target.value })}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Variables</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {VARIABLES.map(({ tag, note }) => (
                <button
                  key={tag}
                  type="button"
                  title={`Insert ${tag} — ${note}`}
                  onClick={() => insertVariable(tag)}
                  style={{
                    textAlign: 'left', padding: '0.4rem 0.6rem', borderRadius: '6px',
                    background: '#f8fafc', border: '1px solid var(--line)',
                    cursor: 'pointer', fontSize: '0.75rem', color: 'var(--ink)',
                    fontFamily: 'monospace', lineHeight: 1.3,
                  }}
                >
                  <span style={{ display: 'block', fontWeight: 700, color: 'var(--accent)' }}>{tag}</span>
                  <span style={{ color: 'var(--muted)', fontFamily: 'sans-serif', fontSize: '0.7rem' }}>{note}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', marginTop: '0.5rem' }}>
          <input type="checkbox" checked={payload.include_summary} onChange={(e) => setPayload({ ...payload, include_summary: e.target.checked })} style={{ accentColor: 'var(--accent)' }} />
          Include course summary block in email
        </label>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
          <button type="submit" className="btn-primary btn-sm">
            {editingId ? 'Update Template' : 'Create Template'}
          </button>
          {editingId && (
            <button type="button" className="btn-sm btn-outline" onClick={handleReset}>Discard</button>
          )}
        </div>
      </form>

      {/* Templates table */}
      <div className="panel">
        <h3 style={{ margin: '0 0 1rem' }}>All Templates</h3>
        {templates.data?.length === 0 ? (
          <p className="text-muted text-sm" style={{ textAlign: 'center', padding: '2rem' }}>No templates yet.</p>
        ) : (
          <table className="premium-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Display Name</th>
                <th>Subject</th>
                <th>Scope</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {templates.data?.map((t) => (
                <tr
                  key={t.id}
                  style={{ cursor: 'pointer', background: editingId === t.id ? 'rgba(30,111,92,0.04)' : undefined }}
                  onClick={() => loadTemplate(t)}
                  title="Click to edit this template"
                >
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', fontWeight: 600 }}>{t.template_key}</td>
                  <td style={{ fontSize: '0.875rem' }}>{t.display_name}</td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--muted)', maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.subject_template}</td>
                  <td>
                    <span style={{ fontSize: '0.7rem', background: t.major_id ? '#eff6ff' : '#f1f5f9', color: t.major_id ? '#1d4ed8' : '#475569', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      {t.major_id ? 'Major-specific' : 'Global'}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    {editingId === t.id
                      ? <span style={{ fontSize: '0.7rem', color: 'var(--accent)', fontWeight: 700 }}>Editing</span>
                      : <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Edit →</span>
                    }
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
