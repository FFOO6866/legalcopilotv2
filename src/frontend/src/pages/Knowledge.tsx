import { useState } from "react";
import { Search, BookOpen, FileText } from "lucide-react";
import clsx from "clsx";
import { useAuthStore } from "@/stores/authStore";
import SearchPanel from "@/components/knowledge/SearchPanel";
import FirmKnowledgeList from "@/components/knowledge/FirmKnowledgeList";
import EmptyState from "@/components/common/EmptyState";
import Documents from "@/pages/Documents";

type KnowledgeTab = "search" | "firm" | "documents";

const TABS: Array<{ value: KnowledgeTab; label: string; icon: typeof Search }> = [
  { value: "search", label: "Case Law Search", icon: Search },
  { value: "firm", label: "Firm Knowledge", icon: BookOpen },
  { value: "documents", label: "Documents", icon: FileText },
];

export default function Knowledge() {
  const user = useAuthStore((state) => state.user);
  const firmId = user?.firm_id ?? "";
  const [activeTab, setActiveTab] = useState<KnowledgeTab>("search");

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-sm text-gray-500 mt-1">
          Search case law, manage firm knowledge, and browse documents
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-gray-200 mb-6 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setActiveTab(tab.value)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px",
              activeTab === tab.value
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
            )}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "search" && <SearchPanel />}
      {activeTab === "firm" && (firmId
        ? <FirmKnowledgeList firmId={firmId} />
        : <EmptyState icon={BookOpen} title="No firm associated" description="Your account is not linked to a firm." />
      )}
      {activeTab === "documents" && <Documents embedded />}
    </div>
  );
}
