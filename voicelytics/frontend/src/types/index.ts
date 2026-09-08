export type Row = {id:number; [key:string]: any};
export interface User extends Row {name:string;email:string;role:string;factory_id:number;department_id:number;}
export interface Incident extends Row {incident_number:string;description:string;severity:string;status:string;machine_name:string;machine_code:string;sla_due_at:string;category:string;assigned_user:string;department:string;created_at:string;}
export type Lookup = Record<string, Row[]>;
