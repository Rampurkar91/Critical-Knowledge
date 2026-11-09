import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import { Loading } from './components/ui';
import Landing from './pages/Landing';
import AuthPage from './pages/AuthPage';
import Dashboard from './pages/Dashboard';
import ProjectWorkspace from './pages/ProjectWorkspace';
import SourceIntegration from './pages/SourceIntegration';
import KnowledgeGraph from './pages/KnowledgeGraph';
import DecisionHistory from './pages/DecisionHistory';
import VerificationDashboard from './pages/VerificationDashboard';
import ConflictDashboard from './pages/ConflictDashboard';
import RiskDependency from './pages/RiskDependency';
import ReviewCentre from './pages/ReviewCentre';
import HandoverReport from './pages/HandoverReport';
import IncomingDashboard from './pages/IncomingDashboard';
import ContinuityDashboard from './pages/ContinuityDashboard';
import AccessManagement from './pages/AccessManagement';
import AuditHistory from './pages/AuditHistory';

function ProtectedLayout() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center"><Loading label="Preparing your secure workspace…" /></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Layout />;
}

function NotFound() {
  return <div className="grid min-h-[60vh] place-items-center text-center"><div><p className="text-5xl font-extrabold text-navy-900">404</p><p className="muted mt-2">This route is not part of the KnowledgeBridge workspace.</p><a className="link mt-4 inline-block" href="/dashboard">Return to dashboard</a></div></div>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/workspace" element={<ProjectWorkspace />} />
        <Route path="/sources" element={<SourceIntegration />} />
        <Route path="/graph" element={<KnowledgeGraph />} />
        <Route path="/decisions" element={<DecisionHistory />} />
        <Route path="/verification" element={<VerificationDashboard />} />
        <Route path="/conflicts" element={<ConflictDashboard />} />
        <Route path="/risks" element={<RiskDependency />} />
        <Route path="/review" element={<ReviewCentre />} />
        <Route path="/handover" element={<HandoverReport />} />
        <Route path="/incoming" element={<IncomingDashboard />} />
        <Route path="/continuity" element={<ContinuityDashboard />} />
        <Route path="/access" element={<AccessManagement />} />
        <Route path="/audit" element={<AuditHistory />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
