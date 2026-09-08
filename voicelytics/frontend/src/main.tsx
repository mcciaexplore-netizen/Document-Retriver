import React from 'react';
import ReactDOM from 'react-dom/client';
import {BrowserRouter,Routes,Route,Navigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {SessionProvider,useSession} from './stores/session';
import {ToastProvider,Loading,ErrorState} from './components/ui';
import {Shell} from './layouts/Shell';
import {Login} from './pages/Login';
import {Dashboard} from './pages/Dashboard';
import {ReportIssue} from './pages/ReportIssue';
import {Incidents,IncidentDetail} from './pages/Incidents';
import {Machines,MachineDetail} from './pages/Machines';
import {MachineLogs,Documents,Reports,Maintenance,Alerts,OperationsQuery} from './pages/Operations';
import {Rules,Users,Settings,Audit} from './pages/Admin';
import './styles.css';
const qc=new QueryClient({defaultOptions:{queries:{staleTime:15000,refetchInterval:60000,retry:1}}});
function AdminOnly({children}:{children:React.ReactNode}){const {user}=useSession();return user?.role==='Admin'?children:<ErrorState error={{message:'Administrator access is required for this page.'}}/>;}
function App(){const {user,loading}=useSession();if(loading)return <Loading/>;if(!user)return <Login/>;return <Routes><Route element={<Shell/>}><Route index element={<Dashboard/>}/><Route path="report" element={<ReportIssue/>}/><Route path="incidents" element={<Incidents/>}/><Route path="incidents/:id" element={<IncidentDetail/>}/><Route path="machines" element={<Machines/>}/><Route path="machines/:id" element={<MachineDetail/>}/><Route path="map" element={<Machines map/>}/><Route path="logs" element={<MachineLogs/>}/><Route path="maintenance" element={<Maintenance/>}/><Route path="documents" element={<Documents/>}/><Route path="alerts" element={<Alerts/>}/><Route path="reports" element={<Reports/>}/><Route path="query" element={<OperationsQuery/>}/><Route path="rules" element={<AdminOnly><Rules/></AdminOnly>}/><Route path="users" element={<AdminOnly><Users/></AdminOnly>}/><Route path="settings" element={<Settings/>}/><Route path="audit" element={<AdminOnly><Audit/></AdminOnly>}/><Route path="*" element={<Navigate to="/" replace/>}/></Route></Routes>;}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={qc}><SessionProvider><ToastProvider><BrowserRouter><App/></BrowserRouter></ToastProvider></SessionProvider></QueryClientProvider></React.StrictMode>);
