import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { ToastProvider } from './context/ToastContext';
import { AuthProvider } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <ToastProvider>
    <AuthProvider>
      <ProjectProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ProjectProvider>
    </AuthProvider>
  </ToastProvider>,
);
