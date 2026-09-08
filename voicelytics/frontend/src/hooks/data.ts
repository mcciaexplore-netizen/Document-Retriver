import {useEffect,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from '../services/api';
import {Lookup} from '../types';
export function useData<T=any>(path:string){return useQuery<T>({queryKey:[path],queryFn:async()=>(await api.get(path)).data});}
export const useLookup=()=>useData<Lookup>('/lookup');
export function useRealtime(){const qc=useQueryClient();const [connected,setConnected]=useState(false);useEffect(()=>{let socket:WebSocket|undefined,stopped=false,retry:ReturnType<typeof setTimeout>;async function connect(){try{const {data}=await api.post('/auth/ws-ticket');if(stopped)return;socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws?ticket=${encodeURIComponent(data.ticket)}`);socket.onopen=()=>{setConnected(true);qc.invalidateQueries();};socket.onmessage=e=>{if(JSON.parse(e.data).type==='records_changed')qc.invalidateQueries();};socket.onclose=()=>{setConnected(false);if(!stopped)retry=setTimeout(connect,3000);};socket.onerror=()=>socket?.close();}catch{if(!stopped)retry=setTimeout(connect,5000);}}connect();const ping=setInterval(()=>{if(socket?.readyState===WebSocket.OPEN)socket.send('ping');},25000);return()=>{stopped=true;clearTimeout(retry);clearInterval(ping);socket?.close();};},[qc]);return connected;}
