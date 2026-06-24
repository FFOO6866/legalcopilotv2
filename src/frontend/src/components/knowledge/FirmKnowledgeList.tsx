import { useState } from "react";
import { Plus, Search, BookOpen, Trash2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import * as Dialog from "@radix-ui/react-dialog";
import clsx from "clsx";
import { nexusCall } from "@/services/api";
import type { FirmKnowledge } from "@/types/knowledge";
import { formatDate } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Input from "@/components/common/Input";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";
import FirmKnowledgeForm from "./FirmKnowledgeForm";

interface FirmKnowledgeListProps {
  firmId: string;
}

type CategoryTab = "all" | FirmKnowledge["category"];

const CATEGORY_TABS: Array<{ value: CategoryTab; label: string }> = [
  { value: "all", label: "All" },
  { value: "precedent", label: "Precedent" },
  { value: "playbook", label: "Playbook" },
  { value: "template", label: "Template" },
  { value: "policy", label: "Policy" },
  { value: "training", label: "Training" },
  { value: "other", label: "Other" },
];

const categoryBadgeVariant: Record<string, "info" | "success" | "warning" | "neutral" | "danger"> = {
  precedent: "info",
  playbook: "success",
  template: "warning",
  policy: "danger",
  training: "neutral",
  other: "neutral",
};

export default function FirmKnowledgeList({ firmId }: FirmKnowledgeListProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<CategoryTab>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FirmKnowledge | null>(null);

  const {
    data: entries,
    isPending,
    error,
  } = useQuery({
    queryKey: ["firm-knowledge", firmId],
    queryFn: () =>
      nexusCall<FirmKnowledge[]>("knowledge.list_firm_knowledge", {
        firm_id: firmId,
      }),
    enabled: !!firmId,
  });

  const createMutation = useMutation({
    mutationFn: (data: { title: string; category: FirmKnowledge["category"]; content: string }) =>
      nexusCall<FirmKnowledge>("knowledge.create_firm_knowledge", {
        firm_id: firmId,
        ...data,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["firm-knowledge", firmId] });
      setFormOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      nexusCall<void>("knowledge.delete_firm_knowledge", {
        firm_id: firmId,
        knowledge_id: id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["firm-knowledge", firmId] });
      setDeleteTarget(null);
    },
  });

  const filteredEntries = entries?.filter((entry) => {
    if (activeTab !== "all" && entry.category !== activeTab) {
      return false;
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return entry.title.toLowerCase().includes(query);
    }
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <Input
          placeholder="Search knowledge base..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          icon={Search}
          className="w-64"
        />
        <Button variant="primary" onClick={() => setFormOpen(true)}>
          <Plus size={16} />
          Add Knowledge
        </Button>
      </div>

      <Tabs.Root value={activeTab} onValueChange={(val) => setActiveTab(val as CategoryTab)}>
        <Tabs.List className="flex items-center gap-1 border-b border-gray-200 overflow-x-auto">
          {CATEGORY_TABS.map((tab) => (
            <Tabs.Trigger
              key={tab.value}
              value={tab.value}
              className={clsx(
                "px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px",
                activeTab === tab.value
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
              )}
            >
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
      </Tabs.Root>

      {isPending && <Loading size="md" text="Loading knowledge base..." />}

      {error && (
        <p className="text-sm text-red-600 py-4">
          Failed to load knowledge entries. Please try again.
        </p>
      )}

      {filteredEntries && filteredEntries.length === 0 && (
        <EmptyState
          icon={BookOpen}
          title="No knowledge entries"
          description={
            searchQuery || activeTab !== "all"
              ? "No entries match your current filters."
              : "Build your firm's knowledge base by adding precedents, playbooks, templates, and policies."
          }
          actionLabel={!searchQuery && activeTab === "all" ? "Add Knowledge" : undefined}
          onAction={!searchQuery && activeTab === "all" ? () => setFormOpen(true) : undefined}
        />
      )}

      {filteredEntries && filteredEntries.length > 0 && (
        <div className="space-y-2">
          {filteredEntries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-gray-900 truncate">
                  {entry.title}
                </h3>
                <div className="flex items-center gap-2 mt-1.5">
                  <Badge variant={categoryBadgeVariant[entry.category] ?? "neutral"}>
                    {entry.category}
                  </Badge>
                  <span className="text-xs text-gray-400">
                    {formatDate(entry.created_at)}
                  </span>
                  {!entry.is_active && (
                    <Badge variant="neutral">Inactive</Badge>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDeleteTarget(entry)}
                className="p-2 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors shrink-0"
                aria-label={`Delete ${entry.title}`}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <FirmKnowledgeForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isSubmitting={createMutation.isPending}
      />

      {/* Delete confirmation dialog */}
      <Dialog.Root open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 animate-in fade-in-0" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-gray-200 bg-white shadow-xl animate-in fade-in-0 zoom-in-95 p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900">
              Delete Knowledge Entry
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-500">
              Are you sure you want to delete &quot;{deleteTarget?.title}&quot;? This action
              cannot be undone.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <Button
                variant="secondary"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                isLoading={deleteMutation.isPending}
                onClick={() => {
                  if (deleteTarget) {
                    deleteMutation.mutate(deleteTarget.id);
                  }
                }}
              >
                Delete
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
