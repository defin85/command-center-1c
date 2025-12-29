const AUTH_CHANGE_EVENT = 'auth:changed'

export const getAuthToken = () => localStorage.getItem('auth_token')

export const notifyAuthChanged = () => {
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT))
}

export const subscribeAuthChange = (callback: () => void) => {
  window.addEventListener(AUTH_CHANGE_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(AUTH_CHANGE_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}
