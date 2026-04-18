import { useMajors, useUsers, useBackups } from '../../lib/hooks'
import { StatCard } from '../../components/StatCard'

export function AdminOverviewPage() {
  const majors = useMajors()
  const users = useUsers()
  const backups = useBackups()

  return (
    <section className="stack">
      <div className="page-header">
        <div>
          <div className="eyebrow">Admin Panel</div>
          <h2>Operations Overview</h2>
        </div>
      </div>
      <div className="stats-grid">
        <StatCard label="Majors" value={majors.data?.length ?? 0} detail="Active academic programs" />
        <StatCard label="Users" value={users.data?.length ?? 0} detail="Admin + adviser accounts" />
        <StatCard label="Backups" value={backups.data?.length ?? 0} detail="Tracked backup runs" />
      </div>
    </section>
  )
}
