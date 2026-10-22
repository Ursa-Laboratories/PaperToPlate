import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import VisionDemo from './VisionDemo';
import './style.css';
const vision=new URLSearchParams(location.search).get('vision')==='1';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{vision?<VisionDemo/>:<App/>}</React.StrictMode>);
