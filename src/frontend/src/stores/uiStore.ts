import { create } from "zustand";

interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: "default" | "success" | "error" | "warning";
}

interface UIStore {
  sidebarOpen: boolean;
  theme: "light" | "dark";
  toasts: Toast[];
  toggleSidebar: () => void;
  setTheme: (theme: "light" | "dark") => void;
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

let toastCounter = 0;

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  theme: "light",
  toasts: [],

  toggleSidebar: () => {
    set((state) => ({ sidebarOpen: !state.sidebarOpen }));
  },

  setTheme: (theme: "light" | "dark") => {
    set({ theme });
    document.documentElement.classList.toggle("dark", theme === "dark");
  },

  addToast: (toast: Omit<Toast, "id">) => {
    toastCounter += 1;
    const id = `toast-${toastCounter}-${Date.now()}`;
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }));

    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, 5000);
  },

  removeToast: (id: string) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },
}));
