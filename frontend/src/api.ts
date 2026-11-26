import axios from 'axios';
export const api=axios.create({baseURL:import.meta.env.VITE_API_URL || 'http://localhost:8000'});
export function saveTokens(data:{access_token:string,refresh_token:string}){localStorage.setItem('access',data.access_token);localStorage.setItem('refresh',data.refresh_token)}
export function logout(){localStorage.removeItem('access');localStorage.removeItem('refresh');location.assign('/login')}
api.interceptors.request.use(c=>{const t=localStorage.getItem('access');if(t)c.headers.Authorization=`Bearer ${t}`;return c});
let refreshing:Promise<void>|null=null;
api.interceptors.response.use(r=>r,async e=>{const c=e.config;if(e.response?.status!==401||!c||c._retry||c.url?.startsWith('/auth/'))throw e;c._retry=true;try{if(!refreshing)refreshing=axios.post(`${api.defaults.baseURL}/auth/refresh`,{refresh_token:localStorage.getItem('refresh')}).then(r=>saveTokens(r.data)).finally(()=>{refreshing=null});await refreshing;return api(c)}catch(err){logout();throw err}});
