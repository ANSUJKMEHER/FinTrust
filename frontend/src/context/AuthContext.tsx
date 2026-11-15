import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { User, Tenant } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSessionData = useCallback(async () => {
    const token = localStorage.getItem('fintrust_access_token');
    if (!token) {
      setUser(null);
      setTenant(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const currentUser = await api.getMe();
      setUser(currentUser);
      try {
        const currentTenant = await api.getCurrentTenant();
        setTenant(currentTenant);
      } catch {
        // tenant fetch failure should not kill session
      }
    } catch (err: any) {
      console.warn('Session verification failed:', err.message);
      setUser(null);
      setTenant(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessionData();

    const handleAuthExpired = () => {
      setUser(null);
      setTenant(null);
    };

    window.addEventListener('fintrust-auth-expired', handleAuthExpired);
    return () => {
      window.removeEventListener('fintrust-auth-expired', handleAuthExpired);
    };
  }, [fetchSessionData]);

  const login = async (username: string, pass: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.login(username, pass);
      await fetchSessionData();
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
    setTenant(null);
  };

  const refreshUser = async () => {
    await fetchSessionData();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
