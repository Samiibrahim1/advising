import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import type { Major } from './api'
import { useCurrentUser, useMajors } from './hooks'

interface MajorContextValue {
  majorCode: string
  setMajorCode: (code: string) => void
  allowedMajors: Major[]
}

const MajorContext = createContext<MajorContextValue>({
  majorCode: '',
  setMajorCode: () => {},
  allowedMajors: [],
})

export function useMajorContext() {
  return useContext(MajorContext)
}

export function MajorProvider({ children }: { children: ReactNode }) {
  const currentUser = useCurrentUser()
  const majors = useMajors()
  const [majorCode, setMajorCode] = useState('')

  const allowedMajors = useMemo(() => {
    if (!majors.data) return []
    const user = currentUser.data
    // Admins see all majors; advisers see only their assigned ones
    if (!user || user.role === 'admin' || !user.major_codes?.length) return majors.data
    return majors.data.filter((m) => user.major_codes.includes(m.code))
  }, [majors.data, currentUser.data])

  // Set initial major once allowed list is known
  useEffect(() => {
    if (!majorCode && allowedMajors.length > 0) {
      setMajorCode(allowedMajors[0].code)
    }
  }, [allowedMajors, majorCode])

  return (
    <MajorContext.Provider value={{ majorCode, setMajorCode, allowedMajors }}>
      {children}
    </MajorContext.Provider>
  )
}
