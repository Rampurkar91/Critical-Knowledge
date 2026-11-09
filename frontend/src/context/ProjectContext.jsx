import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { useAuth } from './AuthContext';
import { useToast } from './ToastContext';

const ProjectContext = createContext(null);
const SELECTED_KEY = 'knowledgebridge_project';

export function ProjectProvider({ children }) {
  const { user, meta } = useAuth();
  const { notify } = useToast();
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectIdState] = useState(() => localStorage.getItem(SELECTED_KEY));
  const [loading, setLoading] = useState(false);

  const setSelectedProjectId = useCallback((id) => {
    setSelectedProjectIdState(id);
    if (id) localStorage.setItem(SELECTED_KEY, id);
    else localStorage.removeItem(SELECTED_KEY);
  }, []);

  const refresh = useCallback(async () => {
    if (!user) {
      setProjects([]);
      return [];
    }
    setLoading(true);
    try {
      const result = await api.get('/api/projects');
      setProjects(result);
      const valid = result.some((project) => project.id === selectedProjectId);
      if (!valid) setSelectedProjectId(result[0]?.id || null);
      return result;
    } catch (error) {
      notify(error.message, 'error');
      return [];
    } finally {
      setLoading(false);
    }
  }, [user, selectedProjectId, setSelectedProjectId, notify]);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const currentProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );
  const membership = useMemo(() => {
    if (!user?.memberships) return null;
    return user.memberships.find((item) => item.project_id === selectedProjectId) || currentProject || null;
  }, [user, selectedProjectId, currentProject]);
  const role = currentProject?.role || membership?.role || null;
  const policy = meta?.roles?.[role] || null;
  const isManager = role === 'project_manager';
  const isPrivileged = ['project_manager', 'tech_lead', 'auditor'].includes(role);
  const can = useCallback((action) => {
    if (!policy) return false;
    return policy.actions.includes('*') || policy.actions.includes(action);
  }, [policy]);

  const value = useMemo(() => ({
    projects,
    projectId: selectedProjectId,
    currentProject,
    membership,
    role,
    policy,
    can,
    isManager,
    isPrivileged,
    loading,
    refresh,
    setSelectedProjectId,
  }), [projects, selectedProjectId, currentProject, membership, role, policy, can, isManager, isPrivileged, loading, refresh, setSelectedProjectId]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export const useProject = () => useContext(ProjectContext);
