import { useNavigate } from 'react-router-dom'
import { useCurrentUser } from '../lib/hooks'

export function HubPage() {
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const firstName = user?.full_name?.split(' ')[0] ?? ''

  return (
    <>
      <div className="hub-portal">
      <div className="hub-hero">
        <div className="hub-hero-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
        </div>
        <h1>Welcome{firstName ? `, ${firstName}` : ' back'}</h1>
        <p>Choose an application below to get started.</p>
      </div>

      <div className="hub-apps">
        <button type="button" className="hub-app-card" onClick={() => navigate('/adviser')}>
          <div className="hub-app-icon hub-app-icon--teal">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <div className="hub-app-body">
            <h3>Student Advising</h3>
            <p>Eligibility engine, workspace, insights, and full advising flows.</p>
          </div>
          <div className="hub-app-arrow">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </div>
        </button>

        <button type="button" className="hub-app-card" onClick={() => navigate('/progress')}>
          <div className="hub-app-icon hub-app-icon--blue">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18" />
              <path d="M9 21V9" />
            </svg>
          </div>
          <div className="hub-app-body">
            <h3>Academic Progress</h3>
            <p>Upload progress reports, track completion, and manage elective assignments.</p>
          </div>
          <div className="hub-app-arrow">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </div>
        </button>
      </div>
    </div>
    <footer className="app-footer">Developed by Dr. Zahi Abdul Sater</footer>
    </>
  )
}
