import { useMemo, useState } from 'react'
import { API_BASE_URL, EligibilityCourse, StudentEligibility, TemplatePreview } from '../../lib/api'

interface Props {
  student: StudentEligibility
  eligibility: EligibilityCourse[]
  activePeriod?: { semester: string; year: number }
  majorCode: string
  templateKey: string
  templates: { id: number; template_key: string; display_name: string }[]
  onTemplateChange: (key: string) => void
  onEmail: () => void
  emailSending?: boolean
  onRecommend: () => void
  onDownloadReport: () => void
}

export function StudentProfileHeader({
  student,
  eligibility,
  activePeriod,
  majorCode,
  templateKey,
  templates,
  onTemplateChange,
  onEmail,
  emailSending,
  onRecommend,
  onDownloadReport,
}: Props) {
  const [showPreview, setShowPreview] = useState(false)
  const [preview, setPreview] = useState<TemplatePreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const completedCount = useMemo(() => eligibility.filter((c) => c.completed).length, [eligibility])
  const registeredCount = useMemo(() => eligibility.filter((c) => c.registered).length, [eligibility])
  const eligibleCount = useMemo(() => eligibility.filter((c) => !c.completed && !c.registered && (c.eligibility_status === 'Eligible' || c.eligibility_status === 'Eligible (Bypass)')).length, [eligibility])

  async function loadPreview() {
    if (showPreview) { setShowPreview(false); return }
    setPreviewLoading(true)
    try {
      const token = window.localStorage.getItem('advising_v2_token')
      const resp = await fetch(
        `${API_BASE_URL}/api/templates/preview?major_code=${encodeURIComponent(majorCode)}&student_id=${encodeURIComponent(student.student_id)}&template_key=${encodeURIComponent(templateKey)}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      )
      if (resp.ok) { setPreview(await resp.json()); setShowPreview(true) }
    } catch { /* ignore */ }
    setPreviewLoading(false)
  }

  return (
    <div className="student-profile-header">
      {/* Single flat row: identity | stats | actions */}
      <div className="profile-flat-row">
        {/* Identity */}
        <div className="profile-identity">
          <h3>{student.student_name}</h3>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.82rem' }}>
            <span className="mono">{student.student_id}</span>
          </p>
        </div>

        {/* Stats */}
        <div className="profile-stats-inline">
          <span className="profile-stat">
            <span className="eyebrow">Standing</span>
            <strong>{student.standing}</strong>
          </span>
          <span className="profile-stat">
            <span className="eyebrow">Remaining</span>
            <strong>{student.credits_remaining} cr</strong>
          </span>
          <span className="profile-stat">
            <span className="eyebrow">Period</span>
            <strong>{activePeriod ? `${activePeriod.semester} ${activePeriod.year}` : '—'}</strong>
          </span>
          <span className="profile-stat">
            <span className="eyebrow">Completed</span>
            <strong>{completedCount}</strong>
          </span>
          <span className="profile-stat">
            <span className="eyebrow">Registered</span>
            <strong>{registeredCount}</strong>
          </span>
          <span className="profile-stat">
            <span className="eyebrow">Eligible</span>
            <strong>{eligibleCount}</strong>
          </span>
        </div>

        {/* All action buttons */}
        <div className="profile-actions-row">
          <button type="button" className="btn-secondary" onClick={onRecommend} title="Auto-fill recommended courses">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /></svg>
            Recommend
          </button>
          <button type="button" className="btn-secondary" onClick={onDownloadReport} title="Download advising report">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" /></svg>
            Download
          </button>

          <div className="profile-divider" />

          <select value={templateKey} onChange={(e) => onTemplateChange(e.target.value)} className="select-sm" title="Email template">
            {templates.map((t) => <option key={t.id} value={t.template_key}>{t.display_name}</option>)}
          </select>
          <button type="button" className="btn-outline btn-sm" onClick={loadPreview} disabled={previewLoading} title="Preview email">
            {previewLoading ? '…' : showPreview ? 'Hide' : '👁 Preview'}
          </button>
          <button type="button" className="btn-primary" onClick={onEmail} disabled={emailSending}>
            {emailSending ? 'Sending…' : 'Email Student'}
          </button>
        </div>
      </div>

      {/* Email Preview — collapses below */}
      {showPreview && preview && (
        <div style={{ marginTop: '12px', padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.05em', marginBottom: '6px' }}>Email Preview</div>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#1e293b', marginBottom: '8px' }}>Subject: {preview.subject}</div>
          <div
            style={{ fontSize: '12px', color: '#475569', background: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '12px', maxHeight: '200px', overflow: 'auto', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}
            dangerouslySetInnerHTML={{ __html: preview.preview_body }}
          />
        </div>
      )}
    </div>
  )
}
