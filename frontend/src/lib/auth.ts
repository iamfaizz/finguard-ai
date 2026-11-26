import {api, saveTokens, logout} from '../api';
let pending: Promise<string> | null = null;
export async function getAccessToken(forceRefresh = false): Promise<string> {
  const token = localStorage.getItem('access');
  if (token && !forceRefresh) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      if (payload.exp * 1000 > Date.now() + 30000) return token;
    } catch { /* refresh malformed or expired token */ }
  }
  if (!pending) pending = (async () => {
    const refresh = localStorage.getItem('refresh');
    if (!refresh) throw new Error('Login required');
    const {data} = await api.post('/auth/refresh', {refresh_token: refresh});
    saveTokens(data);
    return data.access_token as string;
  })().catch(error => { logout(); throw error; }).finally(() => { pending = null; });
  return pending;
}
