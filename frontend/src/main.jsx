import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { DeckMasterProvider } from './context/DeckMasterContext';
import './styles/app.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DeckMasterProvider>
      <App />
    </DeckMasterProvider>
  </React.StrictMode>
);
