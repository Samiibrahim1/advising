import { StudentEligibility } from '../../lib/api'


interface Props {
    eligibility: StudentEligibility['eligibility']
    intensiveCourses: StudentEligibility['eligibility']
}

export function EligibilityTables({ eligibility, intensiveCourses }: Props) {
    const requiredCourses = eligibility.filter(c => c.course_type === 'Required')
    return (
        <div className="eligibility-tables-container stack">
            <div className="panel stack">
                <div className="table-header">
                    <h3>Required Courses</h3>
                    <span className="badge badge-info">{requiredCourses.length}</span>
                </div>

                {requiredCourses.length === 0 ? (
                    <p className="empty-state">No required courses to display.</p>
                ) : (
                    <div className="scroll-table styled-table-wrapper">
                        <table className="styled-table">
                            <thead>
                                <tr>
                                    <th>Code</th>
                                    <th>Title</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                    <th>Justification</th>
                                </tr>
                            </thead>
                            <tbody>
                                {requiredCourses.map((course: { course_code: string; title: string; eligibility_status: string; justification: string; action?: string }) => (
                                    <tr key={course.course_code} className={course.eligibility_status === 'Eligible' ? 'row-eligible' : ''}>
                                        <td className="mono font-semibold">{course.course_code}</td>
                                        <td>{course.title}</td>
                                        <td>
                                            <span className={`status-pill status-${course.eligibility_status.toLowerCase().replace(/\s+/g, '-')}`}>
                                                {course.eligibility_status}
                                            </span>
                                        </td>
                                        <td>{course.action || '—'}</td>
                                        <td><span className="text-muted">{course.justification || '—'}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            <div className="panel stack">
                <div className="table-header">
                    <h3>Intensive Courses</h3>
                    <span className="badge badge-info">{intensiveCourses.length}</span>
                </div>

                {intensiveCourses.length === 0 ? (
                    <p className="empty-state">No intensive courses to display.</p>
                ) : (
                    <div className="scroll-table styled-table-wrapper">
                        <table className="styled-table">
                            <thead>
                                <tr>
                                    <th>Code</th>
                                    <th>Title</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                    <th>Justification</th>
                                </tr>
                            </thead>
                            <tbody>
                                {intensiveCourses.map((course: { course_code: string; title: string; eligibility_status: string; justification: string; action?: string }) => (
                                    <tr key={course.course_code} className={course.eligibility_status === 'Eligible' ? 'row-eligible' : ''}>
                                        <td className="mono font-semibold">{course.course_code}</td>
                                        <td>{course.title}</td>
                                        <td>
                                            <span className={`status-pill status-${course.eligibility_status.toLowerCase().replace(/\s+/g, '-')}`}>
                                                {course.eligibility_status}
                                            </span>
                                        </td>
                                        <td>{course.action || '—'}</td>
                                        <td><span className="text-muted">{course.justification || '—'}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    )
}
