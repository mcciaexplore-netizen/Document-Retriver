import axios from 'axios';
export const api = axios.create({baseURL:'/api',timeout:30000});
api.interceptors.request.use(config=>{const token=sessionStorage.getItem('voicelytics-token');if(token)config.headers.Authorization=`Bearer ${token}`;return config;});
api.interceptors.response.use(response=>response,error=>{if(error.response?.status===401&&!error.config.url.includes('/auth/login')){sessionStorage.removeItem('voicelytics-token');window.dispatchEvent(new Event('session-expired'));}return Promise.reject(error);});
export function errorMessage(error:any):string {const detail=error.response?.data?.detail;if(typeof detail==='string')return detail;if(detail?.errors)return detail.message+'\n'+detail.errors.map((e:any)=>`Row ${e.row}: ${e.message}`).join('\n');if(Array.isArray(detail))return detail.map(e=>`${e.loc?.slice(1).join('.')}: ${e.msg}`).join('\n');return error.message||'Request failed. Please retry.';}
export async function download(path:string,name:string){const {data}=await api.get(path,{responseType:'blob'});const url=URL.createObjectURL(data);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
