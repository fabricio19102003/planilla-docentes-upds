import axios from 'axios'

/** Student portal session, kept apart from the staff session in `auth_token`. */
export const STUDENT_TOKEN_KEY = 'student_token'
export const STUDENT_LOGIN_PATH = '/estudiante/login'

export const studentApi = axios.create({
  baseURL: '/api/student-portal',
  headers: { 'Content-Type': 'application/json' },
})

studentApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(STUDENT_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

studentApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url === '/auth/login'
    if (error.response?.status === 401 && !isLogin && localStorage.getItem(STUDENT_TOKEN_KEY)) {
      localStorage.removeItem(STUDENT_TOKEN_KEY)
      if (window.location.pathname !== STUDENT_LOGIN_PATH) window.location.replace(STUDENT_LOGIN_PATH)
    }
    return Promise.reject(error)
  },
)
