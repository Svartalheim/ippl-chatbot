import React, { createContext, useContext, useEffect, useState } from "react";
import { api, clearTokens, getAccessToken, getRefreshToken, setTokens } from "../api/client";

export interface UserProfile {
  id: string | null;
  username: string;
  email: string | null;
  full_name: string;
  first_name?: string | null;
  last_name?: string | null;
  subject: string;
  roles: string[];
  role: string;
  allowed_classifications: string[];
  email_verified: boolean;
}

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  canManageDocs: boolean;
  canManageRbac: boolean;
  canViewAudit: boolean;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("current_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchProfile = async (): Promise<UserProfile | null> => {
    try {
      const data = await api.get<UserProfile>("/me");
      setUser(data);
      localStorage.setItem("current_user", JSON.stringify(data));
      return data;
    } catch {
      setUser(null);
      localStorage.removeItem("current_user");
      return null;
    }
  };

  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      fetchProfile().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const tokenRes = await api.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/login", { username, password });

      setTokens(tokenRes.access_token, tokenRes.refresh_token);
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await api.post("/auth/logout", { refresh_token: refreshToken });
      } catch {
        // Abaikan jika logout gagal
      }
    }
    clearTokens();
    setUser(null);
    window.location.href = "/login";
  };

  const userRole = user?.role || (user?.roles?.[0] ?? "Karyawan");
  const canManageDocs = userRole === "Admin";
  const canManageRbac = userRole === "Admin";
  const canViewAudit = userRole === "Auditor" || userRole === "Admin";

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        canManageDocs,
        canManageRbac,
        canViewAudit,
        refreshProfile: async () => {
          await fetchProfile();
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
