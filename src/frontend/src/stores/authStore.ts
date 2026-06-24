import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User } from "@/types/auth";
import * as authService from "@/services/auth.service";

interface AuthStore {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  initializeAuth: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authService.login(email, password);
          authService.storeAuth(response.access_token, response.user);
          sessionStorage.setItem("refresh_token", response.refresh_token);
          set({
            user: response.user,
            token: response.access_token,
            isLoading: false,
            error: null,
          });
        } catch (err: unknown) {
          const message =
            err instanceof Error ? err.message : "Login failed. Please try again.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      logout: () => {
        set({ user: null, token: null, error: null });
        sessionStorage.removeItem("auth-storage");
        authService.logout();
      },

      initializeAuth: () => {
        const token = authService.getStoredToken();
        const user = authService.getStoredUser();
        if (token && user) {
          set({ user, token });
        } else {
          set({ user: null, token: null });
        }
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
      }),
    },
  ),
);

export function useIsAuthenticated(): boolean {
  return useAuthStore((state) => state.user !== null && state.token !== null);
}
