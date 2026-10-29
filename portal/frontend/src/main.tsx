import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { consumeVerificationFragment } from './account/verification';
import './style.css';

createRoot(document.getElementById('root')!).render(<StrictMode><App verificationToken={consumeVerificationFragment()} /></StrictMode>);
