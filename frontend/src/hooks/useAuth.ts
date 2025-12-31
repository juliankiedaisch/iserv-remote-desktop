import { useState, useEffect, useCallback } from 'react';
import { AuthState } from '../types';
import { apiService } from '../services/api';

const initialState: AuthState = {
  session: null,
  user: null,
  authenticated: false,
  loading: true,
  error: null,
};

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>(initialState);

  const validateSession = useCallback(async () => {
    setAuthState(prev => ({ ...prev, loading: true, error: null }));
    
    const sessionId = apiService.getSessionId();
    if (!sessionId) {
      setAuthState({
        session: null,
        user: null,
        authenticated: false,
        loading: false,
        error: null,
      });
      return false;
    }

    try {
      const response = await apiService.validateSession();
      
      if (response.authenticated) {
        setAuthState({
          session: response.session,
          user: response.user,
          authenticated: true,
          loading: false,
          error: null,
        });
        return true;
      } else {
        apiService.clearSession();
        setAuthState({
          session: null,
          user: null,
          authenticated: false,
          loading: false,
          error: null,
        });
        return false;
      }
    } catch (error: any) {
      console.error('Session validation failed:', error);
      apiService.clearSession();
      setAuthState({
        session: null,
        user: null,
        authenticated: false,
        loading: false,
        error: error.message || 'Failed to validate session',
      });
      return false;
    }
  }, []);

  const login = useCallback(() => {
    window.location.href = apiService.getLoginUrl();
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    }
    setAuthState({
      session: null,
      user: null,
      authenticated: false,
      loading: false,
      error: null,
    });
    window.location.href = '/';
  }, []);

  // Handle session ID from URL params (after OAuth callback)
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionIdFromUrl = urlParams.get('session_id');
    
    if (sessionIdFromUrl) {
      apiService.setSession(sessionIdFromUrl);
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    validateSession();
  }, [validateSession]);

  return {
    ...authState,
    login,
    logout,
    validateSession,
    isAdmin: authState.user?.role === 'admin',
    isTeacher: authState.user?.role === 'teacher' || authState.user?.role === 'admin',
  };
}

export default useAuth;
