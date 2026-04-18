import { StudentEligibility } from '../../lib/api'

interface Props {
    student: {
        bypasses: Record<string, { note: string; advisor: string }>
    }
    eligibility: StudentEligibility['eligibility']
    bypassCourse: string
    setBypassCourse: (val: string) => void
    bypassNote: string
    setBypassNote: (val: string) => void
    onBypassSave: () => void
    onBypassDelete: (courseCode: string) => void
}

export function ExceptionManagement({
    student,
    eligibility,
    bypassCourse,
    setBypassCourse,
    bypassNote,
    setBypassNote,
    onBypassSave,
    onBypassDelete,
}: Props) {

    return (
        <div className="exception-management-container" style={{ maxWidth: '600px' }}>

            {/* Bypasses */}
            <div className="panel stack">
                <div className="panel-header">
                    <h3>Requisite Bypasses</h3>
                    <p className="text-muted text-sm">Allow student to register for a course without meeting prerequisites</p>
                </div>

                <div className="form-grid">
                    <div className="form-group">
                        <label htmlFor="bypass-course">Course</label>
                        <select
                            id="bypass-course"
                            value={bypassCourse}
                            onChange={(e) => setBypassCourse(e.target.value)}
                            className="select-input"
                        >
                            <option value="">Select a course</option>
                            {eligibility.map((course) => (
                                <option key={course.course_code} value={course.course_code}>
                                    {course.course_code} - {course.title}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="form-group">
                        <label htmlFor="bypass-note">Note</label>
                        <textarea
                            id="bypass-note"
                            rows={2}
                            value={bypassNote}
                            onChange={(e) => setBypassNote(e.target.value)}
                            placeholder="Why is this bypass granted?"
                            className="text-input"
                        />
                    </div>
                    <button
                        type="button"
                        className="btn-primary"
                        onClick={onBypassSave}
                        disabled={!bypassCourse}
                    >
                        Save Bypass
                    </button>
                </div>

                <div className="divider" />

                <div className="bypass-list">
                    <h4 className="list-title">Active Bypasses</h4>
                    {Object.entries(student.bypasses).length === 0 ? (
                        <p className="empty-state-sm">No active bypasses.</p>
                    ) : (
                        <div className="mini-list">
                            {Object.entries(student.bypasses).map(([courseCode, info]) => (
                                <div key={courseCode} className="mini-item card-sm">
                                    <div className="item-content">
                                        <strong>{courseCode}</strong>
                                        <p className="note-text">{info.note}</p>
                                        {info.advisor && <span className="advisor-tag">by {info.advisor}</span>}
                                    </div>
                                    <button type="button" className="btn-icon btn-danger" onClick={() => onBypassDelete(courseCode)} title="Remove bypass">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

        </div>
    )
}
