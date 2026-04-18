import { useQuery } from '@tanstack/react-query'
import { apiFetch, AppTemplate, AuditEventRecord, BackupRun, CourseCatalogItem, CurrentUser, DashboardMetrics, DatasetVersion, ExclusionSummary, Major, Period, SessionSummary, StudentEligibility, StudentSearchItem, UserRecord, progressStatus, progressEquivalents, progressAssignmentTypes, progressAssignments, getProgressReport, ProgressDataStatus, EquivalentCourse, AssignmentType, ProgressAssignment, ProgressReportResponse, fetchExemptions, Exemption } from './api'

export function useCurrentUser() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<CurrentUser>('/auth/me'),
    retry: false,
    staleTime: Infinity,
  })
}

export function useMajors() {
  return useQuery({ queryKey: ['majors'], queryFn: () => apiFetch<Major[]>('/majors') })
}

export function useDashboard(majorCode?: string) {
  return useQuery({
    queryKey: ['dashboard', majorCode],
    queryFn: () => apiFetch<DashboardMetrics>(`/insights/${majorCode}/dashboard`),
    enabled: Boolean(majorCode),
  })
}

export function useStudents(majorCode?: string, query?: string) {
  return useQuery({
    queryKey: ['students', majorCode, query],
    queryFn: () => apiFetch<StudentSearchItem[]>(`/students/${majorCode}/search${query ? `?query=${encodeURIComponent(query)}` : ''}`),
    enabled: Boolean(majorCode),
  })
}

export function useStudentEligibility(majorCode?: string, studentId?: string) {
  return useQuery({
    queryKey: ['student-eligibility', majorCode, studentId],
    queryFn: () => apiFetch<StudentEligibility>(`/students/${majorCode}/${studentId}`),
    enabled: Boolean(majorCode && studentId),
  })
}

export function useCourseCatalog(majorCode?: string) {
  return useQuery({
    queryKey: ['course-catalog', majorCode],
    queryFn: () => apiFetch<CourseCatalogItem[]>(`/students/${majorCode}/catalog`),
    enabled: Boolean(majorCode),
  })
}

export function useDatasetVersions(majorCode?: string) {
  return useQuery({
    queryKey: ['dataset-versions', majorCode],
    queryFn: () => apiFetch<DatasetVersion[]>(`/datasets/${majorCode}`),
    enabled: Boolean(majorCode),
  })
}

export function usePeriods(majorCode?: string) {
  return useQuery({
    queryKey: ['periods', majorCode],
    queryFn: () => apiFetch<Period[]>(`/periods/${majorCode}`),
    enabled: Boolean(majorCode),
  })
}

export function useTemplates(majorCode?: string) {
  return useQuery({
    queryKey: ['templates', majorCode],
    queryFn: () => apiFetch<AppTemplate[]>(`/templates${majorCode ? `?major_code=${encodeURIComponent(majorCode)}` : ''}`),
  })
}

export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: () => apiFetch<UserRecord[]>('/users') })
}

export function useBackups() {
  return useQuery({ queryKey: ['backups'], queryFn: () => apiFetch<BackupRun[]>('/backups') })
}

export function useSessions(majorCode?: string, periodCode?: string, studentId?: string) {
  const params = new URLSearchParams()
  if (periodCode) params.set('period_code', periodCode)
  if (studentId) params.set('student_id', studentId)
  const query = params.toString()
  return useQuery({
    queryKey: ['sessions', majorCode, periodCode, studentId],
    queryFn: () => apiFetch<SessionSummary[]>(`/advising/sessions/${majorCode}${query ? `?${query}` : ''}`),
    enabled: Boolean(majorCode),
  })
}

export function useExclusions(majorCode?: string) {
  return useQuery({
    queryKey: ['exclusions', majorCode],
    queryFn: () => apiFetch<ExclusionSummary[]>(`/advising/exclusions/${majorCode}`),
    enabled: Boolean(majorCode),
  })
}

export function useAuditLog(eventType?: string) {
  const params = eventType ? `?event_type=${encodeURIComponent(eventType)}` : ''
  return useQuery({
    queryKey: ['audit-log', eventType],
    queryFn: () => apiFetch<AuditEventRecord[]>(`/audit-events${params}`),
  })
}

// ─────────────────────────────────────────────────────────────────
// Academic Progress hooks
// ─────────────────────────────────────────────────────────────────

export function useProgressStatus(majorCode?: string) {
  return useQuery({
    queryKey: ['progress-status', majorCode],
    queryFn: () => progressStatus(majorCode!),
    enabled: Boolean(majorCode),
  })
}

export function useProgressEquivalents(majorCode?: string) {
  return useQuery({
    queryKey: ['progress-equivalents', majorCode],
    queryFn: () => progressEquivalents(majorCode!),
    enabled: Boolean(majorCode),
  })
}

export function useProgressAssignmentTypes(majorCode?: string) {
  return useQuery({
    queryKey: ['progress-assignment-types', majorCode],
    queryFn: () => progressAssignmentTypes(majorCode!),
    enabled: Boolean(majorCode),
  })
}

export function useProgressAssignments(majorCode?: string, studentId?: string) {
  return useQuery({
    queryKey: ['progress-assignments', majorCode, studentId],
    queryFn: () => progressAssignments(majorCode!, studentId),
    enabled: Boolean(majorCode),
  })
}

export function useExemptions(majorCode?: string, studentId?: string) {
  return useQuery({
    queryKey: ['exemptions', majorCode, studentId],
    queryFn: () => fetchExemptions(majorCode!, studentId),
    enabled: Boolean(majorCode) && Boolean(studentId),
  })
}

export function useProgressReport(
  majorCode: string | undefined,
  params: { showAllGrades?: boolean; page?: number; pageSize?: number; search?: string },
) {
  return useQuery({
    queryKey: ['progress-report', majorCode, params],
    queryFn: () => getProgressReport(majorCode!, params),
    enabled: Boolean(majorCode),
  })
}
