import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken } from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyAuth = useCallback((payload) => {
    setToken(payload.access_token);
    setUser(payload.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    let active = true;
    api.meta().then((result) => active && setMeta(result)).catch(() => {});
    if (!getToken()) {
      setLoading(false);
      return () => { active = false; };
    }
    api.me()
      .then((result) => {
        if (active) setUser(result);
      })
      .catch(() => {
        setToken(null);
        if (active) setUser(null);
      })
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const login = useCallback(async (email, password) => {
    const payload = await api.login(email, password);
    applyAuth(payload);
    return payload.user;
  }, [applyAuth]);

  const demoLogin = useCallback(async (email) => {
    const payload = await api.demoLogin(email);
    applyAuth(payload);
    return payload.user;
  }, [applyAuth]);

  const register = useCallback(async (payload) => {
    const result = await api.register(payload);
    applyAuth(result);
    return result.user;
  }, [applyAuth]);

  const value = useMemo(() => ({
    user, meta, loading, login, demoLogin, register, logout, isAuthenticated: Boolean(user),
  }), [user, meta, loading, login, demoLogin, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
