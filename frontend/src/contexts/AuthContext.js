'use client';
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getApiErrorMessage } from '@/lib/apiError';

const AuthContext = createContext(null);

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'rxos_session_token';
const USER_KEY = 'rxos_session_user';
const ACTIVITY_KEY = 'rxos_last_activity';
const IDLE_TIMEOUT_MS = 30 * 60 * 1000;

function tokenExpiresAt(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload.padEnd(Math.ceil(payload.length / 4) * 4, '=');
    return JSON.parse(atob(padded)).exp * 1000;
  } catch {
    return 0;
  }
}

function clearStoredSession() {
  [localStorage, sessionStorage].forEach((storage) => {
    storage.removeItem(TOKEN_KEY);
    storage.removeItem(USER_KEY);
    storage.removeItem(ACTIVITY_KEY);
  });
  // Clear the original persistent keys once during the session-storage upgrade.
  localStorage.removeItem('rxos_token');
  localStorage.removeItem('rxos_user');
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const storageRef = useRef(null);

  useEffect(() => {
    // Authentication storage is an external browser system. Hydrate it once
    // after mounting to keep server rendering independent from localStorage.
    /* eslint-disable react-hooks/set-state-in-effect */
    const legacyToken = localStorage.getItem('rxos_token');
    const legacyUser = localStorage.getItem('rxos_user');
    const storage = sessionStorage.getItem(TOKEN_KEY) || legacyToken ? sessionStorage : localStorage;
    const stored = storage.getItem(TOKEN_KEY) || legacyToken;
    const storedUser = storage.getItem(USER_KEY) || legacyUser;
    if (!storage.getItem(TOKEN_KEY) && legacyToken && legacyUser) {
      storage.setItem(TOKEN_KEY, legacyToken);
      storage.setItem(USER_KEY, legacyUser);
      storage.setItem(ACTIVITY_KEY, String(Date.now()));
      localStorage.removeItem('rxos_token');
      localStorage.removeItem('rxos_user');
    }
    const lastActivity = Number(storage.getItem(ACTIVITY_KEY) || 0);
    const sessionIsCurrent = stored && storedUser && tokenExpiresAt(stored) > Date.now()
      && Date.now() - lastActivity < IDLE_TIMEOUT_MS;
    if (sessionIsCurrent) {
      try {
        setToken(stored);
        setUser(JSON.parse(storedUser));
        storageRef.current = storage;
      } catch {
        clearStoredSession();
      }
    } else {
      clearStoredSession();
    }
    setLoading(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const storeSession = useCallback((data, remember = false) => {
    clearStoredSession();
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(TOKEN_KEY, data.token);
    storage.setItem(USER_KEY, JSON.stringify(data.user));
    storage.setItem(ACTIVITY_KEY, String(Date.now()));
    storageRef.current = storage;
    setToken(data.token);
    setUser(data.user);
  }, []);

  const login = async (email, password, remember = false) => {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(getApiErrorMessage(data, 'Login failed'));

    storeSession(data, remember);
    return data;
  };

  const signup = async (email, password, full_name) => {
    const res = await fetch(`${API_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(getApiErrorMessage(data, 'Signup failed'));

    storeSession(data, false);
    return data;
  };

  const logout = useCallback(() => {
    clearStoredSession();
    storageRef.current = null;
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (!token || !user) return undefined;
    let idleTimer;
    const recordActivity = () => {
      const storage = storageRef.current;
      if (storage) storage.setItem(ACTIVITY_KEY, String(Date.now()));
      clearTimeout(idleTimer);
      const remainingTokenTime = Math.max(0, tokenExpiresAt(token) - Date.now());
      idleTimer = setTimeout(logout, Math.min(IDLE_TIMEOUT_MS, remainingTokenTime));
    };
    const events = ['click', 'keydown', 'touchstart', 'focus'];
    events.forEach((event) => window.addEventListener(event, recordActivity));
    recordActivity();
    return () => {
      clearTimeout(idleTimer);
      events.forEach((event) => window.removeEventListener(event, recordActivity));
    };
  }, [logout, token, user]);

  const authFetch = useCallback(
    async (url, options = {}) => {
      const headers = { ...options.headers };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const res = await fetch(url, { ...options, headers });
      if (res.status === 401) {
        logout();
        throw new Error('Session expired');
      }
      return res;
    },
    [token, logout]
  );

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout, authFetch, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
