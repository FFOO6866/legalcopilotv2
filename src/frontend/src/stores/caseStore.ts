import { create } from "zustand";
import type { Case, CaseStage } from "@/types/case";

interface CaseStore {
  activeCase: Case | null;
  activeTab: string;
  setActiveCase: (c: Case | null) => void;
  updateStage: (stage: CaseStage) => void;
  setActiveTab: (tab: string) => void;
}

export const useCaseStore = create<CaseStore>((set) => ({
  activeCase: null,
  activeTab: "overview",

  setActiveCase: (c) => set({ activeCase: c }),

  updateStage: (stage) =>
    set((state) => {
      if (!state.activeCase) return state;
      return { activeCase: { ...state.activeCase, stage } };
    }),

  setActiveTab: (tab) => set({ activeTab: tab }),
}));
