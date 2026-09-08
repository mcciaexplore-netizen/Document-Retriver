export const label=(value:string)=>value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
export const date=(value:string|undefined)=>value?new Date(value).toLocaleString([], {dateStyle:'medium',timeStyle:'short'}):'—';
export const terminal=(status:string)=>['RESOLVED','VERIFIED','CLOSED'].includes(status);
export function remaining(due:string){const minutes=Math.ceil((new Date(due).getTime()-Date.now())/60000);return minutes<0?`${Math.abs(minutes)}m overdue`:minutes>=60?`${Math.floor(minutes/60)}h ${minutes%60}m`:`${minutes}m remaining`;}
