const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const API_BASE_URL = rawBase.startsWith('http') ? rawBase : `https://${rawBase}`

export type CurrentUser = {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'adviser'
  major_codes: string[]
}

export type Major = {
  id: number
  code: string
  name: string
  is_active: boolean
  smtp_email: string | null
  smtp_configured: boolean
}

export type DashboardMetrics = {
  total_students: number
  advised_students: number
  not_advised_students: number
  progress_percent: number
  graduating_soon_unadvised: { student_id: string; student_name: string }[]
  recent_activity: { student_name: string; created_at: string }[]
  credit_distribution: { label: string; count: number }[]
}

export type CourseOfferingRecommendation = {
  course: string
  priority_score: number
  currently_eligible: number
  graduating_students: number
  bottleneck_score: number
  cascading_eligible: number
  reason: string
}

export type StudentSearchItem = {
  student_id: string
  student_name: string
  standing: string
  total_credits: number
  remaining_credits: number
}

export type CourseCatalogItem = {
  course_code: string
  title: string
  course_type: string
  credits: number
  offered: boolean
}

export type SelectionPayload = {
  advised: string[]
  optional: string[]
  repeat: string[]
  note: string
}

export type EligibilityCourse = {
  course_code: string
  title: string
  course_type: string
  credits: number
  suggested_semester: string
  requisites: string
  eligibility_status: string
  justification: string
  offered: boolean
  completed: boolean
  registered: boolean
  action: string
}

export type StudentEligibility = {
  student_id: string
  student_name: string
  standing: string
  credits_completed: number
  credits_registered: number
  credits_remaining: number
  advised_credits: number
  optional_credits: number
  repeat_credits: number
  eligibility: EligibilityCourse[]
  selection: SelectionPayload
  bypasses: Record<string, { note: string; advisor: string }>
  hidden_courses: string[]
  excluded_courses: string[]
}

export type DatasetVersion = {
  id: number
  major_id: number
  dataset_type: string
  version_label: string
  original_filename: string | null
  is_active: boolean
  metadata_json: Record<string, unknown>
  created_at: string
}

export type Period = {
  id: number
  major_id: number
  period_code: string
  semester: string
  year: number
  advisor_name: string
  is_active: boolean
}

export type AppTemplate = {
  id: number
  major_id: number | null
  template_key: string
  display_name: string
  description: string
  subject_template: string
  body_template: string
  include_summary: boolean
}

export type SessionSummary = {
  id: number
  title: string
  student_id: string
  student_name: string
  period_code: string | null
  created_at: string
  summary: Record<string, unknown>
}

export type ExclusionSummary = {
  student_id: string
  student_name: string
  course_codes: string[]
}

export type TemplatePreview = {
  template_key: string
  subject: string
  preview_body: string
  variables: Record<string, string | null>
}

export type UserRecord = {
  id: number
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
  major_codes: string[]
}

export type BackupRun = {
  id: number
  status: string
  storage_key: string | null
  manifest: Record<string, unknown>
  notes: string | null
  created_at: string
}

export type AuditEventRecord = {
  id: number
  actor_user_id: number | null
  actor_name: string | null
  event_type: string
  entity_type: string
  entity_id: string
  payload: Record<string, unknown>
  created_at: string
}

export type AllStudentsRow = {
  student_id: string
  student_name: string
  standing: string
  total_credits: number
  remaining_credits: number
  advising_status: string
  courses: Record<string, string>
}

export type AllStudentsCourseMeta = {
  course_code: string
  title: string
  course_type: string
  credits: number
  requisites: string
  suggested_semester: string
}

export type AllStudentsInsightsResponse = {
  rows: AllStudentsRow[]
  required_courses: string[]
  intensive_courses: string[]
  course_metadata: Record<string, AllStudentsCourseMeta>
  simulation_options: string[]
  semester_options: string[]
  legend: { code: string; label: string }[]
  remaining_range: { min: number; max: number }
  simulated_courses: string[]
}

export type IndividualStudentInsight = {
  student_id: string
  student_name: string
  selected_courses: string[]
  statuses: Record<string, string>
  advised: string[]
  optional: string[]
  repeat: string[]
  note: string
}

export type QAARow = {
  course_code: string
  course_name: string
  eligibility: number
  advised: number
  optional: number
  not_advised: number
  skipped_advising: number
  attended_graduating: number
  skipped_graduating: number
}

export type ScheduleConflictRow = {
  group_name: string
  student_count: number
  course_count: number
  courses: string[]
  student_ids: string[]
  students_processed: number
}

export type DegreePlanCourse = {
  code: string
  title: string
  credits: number
  semester: string
  year: string
  status: string
}

export type DegreePlanSemester = {
  semester_key: string
  total_credits: number
  courses: DegreePlanCourse[]
}

export type DegreePlanYear = {
  year_name: string
  semesters: DegreePlanSemester[]
}

export type DegreePlanResponse = {
  student: {
    student_id: string
    student_name: string
    standing: string
    remaining_credits: number
  } | null
  legend: { status: string; label: string; icon: string }[]
  years: DegreePlanYear[]
}

export type PlannerSelectionState = {
  selected_courses: string[]
  graduation_threshold: number
  min_eligible_students: number
  total_eligible: number
  total_graduating: number
  saved_at: string | null
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = window.localStorage.getItem('advising_v2_token')
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  return (await response.blob()) as T
}

export async function login(email: string, password: string) {
  return apiFetch<{ access_token: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

// ─────────────────────────────────────────────────────────────────
// Academic Progress types
// ─────────────────────────────────────────────────────────────────

export type ProgressReportStatus = {
  has_report: boolean
  student_count: number
  uploaded_at: string | null
}

export type CourseConfigStatus = {
  has_config: boolean
  required_count: number
  intensive_count: number
}

export type ProgressDataStatus = {
  progress_report: ProgressReportStatus
  course_config: CourseConfigStatus
}

export type EquivalentCourse = {
  id: number
  alias_code: string
  canonical_code: string
}

export type AssignmentType = {
  id: number
  label: string
  sort_order: number
}

export type ProgressAssignment = {
  id: number
  student_id: string
  assignment_type: string
  course_code: string
}

export type StudentProgressRow = {
  student_id: string
  name: string
  courses: Record<string, string>
  completed_credits: number
  registered_credits: number
  remaining_credits: number
  total_credits: number
  gpa: number | null
}

export type ProgressReportResponse = {
  required: StudentProgressRow[]
  intensive: StudentProgressRow[]
  extra_courses: string[]
  total_students: number
  page: number
  page_size: number
}

// ─────────────────────────────────────────────────────────────────
// Academic Progress fetchers
// ─────────────────────────────────────────────────────────────────

export function progressStatus(majorCode: string) {
  return apiFetch<ProgressDataStatus>(`/progress/${majorCode}/status`)
}

export function progressEquivalents(majorCode: string) {
  return apiFetch<EquivalentCourse[]>(`/progress/${majorCode}/equivalents`)
}

export function setProgressEquivalents(majorCode: string, pairs: { alias_code: string; canonical_code: string }[]) {
  return apiFetch<EquivalentCourse[]>(`/progress/${majorCode}/equivalents`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pairs),
  })
}

export function progressAssignmentTypes(majorCode: string) {
  return apiFetch<AssignmentType[]>(`/progress/${majorCode}/assignment-types`)
}

export function createProgressAssignmentType(majorCode: string, label: string, sort_order?: number) {
  return apiFetch<AssignmentType>(`/progress/${majorCode}/assignment-types`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, sort_order: sort_order ?? 0 }),
  })
}

export function deleteProgressAssignmentType(majorCode: string, typeId: number) {
  return apiFetch<{ message: string }>(`/progress/${majorCode}/assignment-types/${typeId}`, {
    method: 'DELETE',
  })
}

export function progressAssignments(majorCode: string, studentId?: string) {
  const qs = studentId ? `?student_id=${encodeURIComponent(studentId)}` : ''
  return apiFetch<ProgressAssignment[]>(`/progress/${majorCode}/assignments${qs}`)
}

export function saveProgressAssignment(majorCode: string, payload: { student_id: string; assignment_type: string; course_code: string }) {
  return apiFetch<ProgressAssignment>(`/progress/${majorCode}/assignments`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteProgressAssignment(majorCode: string, studentId: string, assignmentType: string) {
  return apiFetch<{ message: string }>(
    `/progress/${majorCode}/assignments/one?student_id=${encodeURIComponent(studentId)}&assignment_type=${encodeURIComponent(assignmentType)}`,
    { method: 'DELETE' },
  )
}

export function resetProgressAssignments(majorCode: string) {
  return apiFetch<{ message: string }>(`/progress/${majorCode}/assignments`, { method: 'DELETE' })
}

// ─── Exemptions (e.g. ARAB201) ────────────────────────────────────
export type Exemption = { id: number; student_id: string; course_code: string }

export function fetchExemptions(majorCode: string, studentId?: string) {
  const qs = studentId ? `?student_id=${encodeURIComponent(studentId)}` : ''
  return apiFetch<Exemption[]>(`/progress/${majorCode}/exemptions${qs}`)
}

export function addExemption(majorCode: string, studentId: string, courseCode: string) {
  return apiFetch<Exemption>(`/progress/${majorCode}/exemptions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: studentId, course_code: courseCode }),
  })
}

export function deleteExemption(majorCode: string, studentId: string, courseCode: string) {
  return apiFetch<{ message: string }>(`/progress/${majorCode}/exemptions`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: studentId, course_code: courseCode }),
  })
}

export function getProgressReport(majorCode: string, params: { showAllGrades?: boolean; page?: number; pageSize?: number; search?: string }) {
  const qs = new URLSearchParams()
  if (params.showAllGrades) qs.set('show_all_grades', 'true')
  if (params.page) qs.set('page', String(params.page))
  if (params.pageSize) qs.set('page_size', String(params.pageSize))
  if (params.search) qs.set('search', params.search)
  return apiFetch<ProgressReportResponse>(`/progress/${majorCode}/report?${qs}`)
}

export function progressExportPath(majorCode: string, showAllGrades = false, collapseMode = false) {
  const params = new URLSearchParams()
  if (showAllGrades) params.set('show_all_grades', 'true')
  if (collapseMode) params.set('collapse_mode', 'true')
  const qs = params.size ? `?${params.toString()}` : ''
  return `/progress/${majorCode}/report/export${qs}`
}

export function pushProgressToAdvising(majorCode: string) {
  return apiFetch<{ message: string; version_id: number; student_count: number }>(
    `/progress/${majorCode}/push-to-advising`,
    { method: 'POST' },
  )
}

export function createPeriod(payload: { major_code: string; semester: string; year: number; advisor_name: string }) {
  return apiFetch<{ period_code: string; semester: string; year: number }>('/periods', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function uploadProgressReport(majorCode: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch<{ student_count: number; row_count: number }>(`/progress/${majorCode}/upload/progress-report`, {
    method: 'POST',
    body: fd,
  })
}

export async function previewProgressReport(majorCode: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch<{ new_students: number; removed_students: number; grade_changes: number; total_students: number }>(
    `/progress/${majorCode}/upload/progress-report/preview`,
    { method: 'POST', body: fd },
  )
}

export async function uploadCourseConfig(majorCode: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch<{ required_count: number; intensive_count: number }>(`/progress/${majorCode}/upload/course-config`, {
    method: 'POST',
    body: fd,
  })
}

export async function uploadElectiveAssignments(majorCode: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch<{ upserted: number; skipped: number; errors: string[] }>(
    `/progress/${majorCode}/upload/elective-assignments`,
    { method: 'POST', body: fd },
  )
}

export function createUser(payload: { email: string; full_name: string; password: string; role: string; major_codes: string[] }) {
  return apiFetch<UserRecord>('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateUser(userId: number, payload: { full_name?: string; role?: string; major_codes?: string[]; new_password?: string }) {
  return apiFetch<UserRecord>(`/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteUser(userId: number) {
  return apiFetch<{ deleted: boolean }>(`/users/${userId}`, { method: 'DELETE' })
}

export function toggleUserActive(userId: number, isActive: boolean) {
  const action = isActive ? 'deactivate' : 'activate'
  return apiFetch<UserRecord>(`/users/${userId}/${action}`, { method: 'PATCH' })
}

export function createMajor(payload: { code: string; name: string }) {
  return apiFetch<Major>('/majors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateMajor(code: string, payload: { name?: string; smtp_email?: string; smtp_password?: string }) {
  return apiFetch<Major>(`/majors/${code}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function revealSmtpPassword(code: string) {
  return apiFetch<{ smtp_password: string }>(`/majors/${code}/smtp-password`)
}

export function deleteMajor(code: string) {
  return apiFetch<{ deleted: boolean }>(`/majors/${code}`, { method: 'DELETE' })
}
