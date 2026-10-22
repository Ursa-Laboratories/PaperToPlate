export async function api<T>(path:string,init?:RequestInit):Promise<T>{
 const response=await fetch('/api'+path,{...init,headers:{...(init?.body && !(init.body instanceof FormData)?{'Content-Type':'application/json'}:{}),...init?.headers}});
 if(!response.ok){let message='The request could not be completed.';try{const body=await response.json();message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail);}catch{/* HTTP fallback */}throw new Error(message);}
 return response.json();
}
export function upload<T>(path:string,file:File):Promise<T>{const body=new FormData();body.append('file',file);return api<T>(path,{method:'POST',body});}
export const timeLabel=(seconds:number)=>`${Math.floor(Math.max(0,seconds)/60)}:${Math.floor(Math.max(0,seconds)%60).toString().padStart(2,'0')}`;
