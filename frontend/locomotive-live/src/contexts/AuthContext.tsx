import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  type PublicUser,
  type RoleName,
  type StoredSession,
  getCurrentUser,
  loginRequest,
} from "@/lib/api";

interface AuthContextType {
  user: PublicUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  canOperate: boolean;
}

const SESSION_STORAGE_KEY = "digital_twin_session";

const AuthContext = createContext<AuthContextType | null>(null);

function roleAllows(currentRole: RoleName, requiredRole: RoleName): boolean {
  const levels: Record<RoleName, number> = {
    viewer: 1,
    operator: 2,
    admin: 3,
  };
  return levels[currentRole] >= levels[requiredRole];
}

function loadStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

function saveStoredSession(session: StoredSession | null): void {
  if (!session) {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    return;
  }
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<PublicUser | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const initializeSession = async () => {
      const session = loadStoredSession();
      if (!session) {
        setLoading(false);
        return;
      }

      if (new Date(session.expiresAt).getTime() <= Date.now()) {
        saveStoredSession(null);
        setLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser(session.accessToken);
        setUser(currentUser);
        setToken(session.accessToken);
        saveStoredSession({
          accessToken: session.accessToken,
          expiresAt: session.expiresAt,
          user: currentUser,
        });
      } catch {
        saveStoredSession(null);
        setUser(null);
        setToken(null);
      } finally {
        setLoading(false);
      }
    };

    initializeSession();
  }, []);

  const logout = () => {
    setUser(null);
    setToken(null);
    saveStoredSession(null);
  };

  const login = async (username: string, password: string) => {
    const response = await loginRequest(username, password);
    const session: StoredSession = {
      accessToken: response.access_token,
      expiresAt: response.expires_at,
      user: response.user,
    };
    setUser(response.user);
    setToken(response.access_token);
    saveStoredSession(session);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        isAdmin: user?.role === "admin",
        canOperate: user ? roleAllows(user.role, "operator") : false,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export { ApiError, type PublicUser, type RoleName };
