
import React, { createContext, useState, ReactNode, useMemo } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  login: (callback?: () => void) => void;
  logout: () => void;
  user: { name: string } | null;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ name: string } | null>(null);

  const login = (callback?: () => void) => {
    setIsAuthenticated(true);
    setUser({ name: 'System Administrator' });
    if (callback) callback();
  };

  const logout = () => {
    setIsAuthenticated(false);
    setUser(null);
  };

  const value = useMemo(() => ({ isAuthenticated, login, logout, user }), [isAuthenticated, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
