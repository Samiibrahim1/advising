import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login } from '../lib/api'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const response = await login(email, password)
      window.localStorage.setItem('advising_v2_token', response.access_token)
      navigate('/')
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="eyebrow">Render + Neon + R2</div>
        <h1>PU Academic Portal</h1>
        <p>Academic advising and progress tracking for Phoenicia University.</p>
        <form onSubmit={handleSubmit} className="stack">
          <label>
            <span>Email</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            <span>Password</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="alert error">{error}</div> : null}
          <button disabled={busy} type="submit">{busy ? 'Signing in...' : 'Sign in'}</button>
        </form>
        <p className="login-credit">Developed by Dr. Zahi Abdul Sater</p>
      </div>
    </div>
  )
}
