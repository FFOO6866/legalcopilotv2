import { useState } from "react";
import { Plus, Search, Briefcase } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import * as Select from "@radix-ui/react-select";
import { ChevronDown, Check } from "lucide-react";
import * as caseService from "@/services/case.service";
import { useAuthStore } from "@/stores/authStore";
import type { Case, CaseStatus } from "@/types/case";
import { PRACTICE_AREAS, CASE_STATUSES } from "@/utils/constants";
import { formatDate, classifyPracticeArea } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Input from "@/components/common/Input";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";
import CaseForm from "./CaseForm";

const statusBadgeVariant: Record<CaseStatus, "success" | "info" | "neutral" | "warning"> = {
  open: "info",
  in_progress: "success",
  pending_review: "warning",
  under_review: "warning",
  closed: "neutral",
  archived: "neutral",
};

interface SelectFilterProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder: string;
  options: ReadonlyArray<{ value: string; label: string }>;
}

function SelectFilter({ value, onValueChange, placeholder, options }: SelectFilterProps) {
  return (
    <Select.Root value={value} onValueChange={onValueChange}>
      <Select.Trigger
        className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]"
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon>
          <ChevronDown size={14} className="text-gray-400" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
          position="popper"
          sideOffset={4}
        >
          <Select.Viewport className="p-1">
            <Select.Item
              value="all"
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
            >
              <Select.ItemText>All {placeholder}</Select.ItemText>
              <Select.ItemIndicator>
                <Check size={14} />
              </Select.ItemIndicator>
            </Select.Item>
            {options.map((option) => (
              <Select.Item
                key={option.value}
                value={option.value}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
              >
                <Select.ItemText>{option.label}</Select.ItemText>
                <Select.ItemIndicator>
                  <Check size={14} />
                </Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}

interface CaseListProps {
  onSelectCase?: (caseItem: Case) => void;
}

export default function CaseList({ onSelectCase }: CaseListProps) {
  const user = useAuthStore((s) => s.user);
  const [searchQuery, setSearchQuery] = useState("");
  const [practiceAreaFilter, setPracticeAreaFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);

  const {
    data: cases,
    isPending,
    error,
  } = useQuery({
    queryKey: ["cases", user?.firm_id],
    queryFn: async () => {
      const result = await caseService.listCases(user?.firm_id ?? "");
      return result.items;
    },
    enabled: !!user,
  });

  const filteredCases = cases?.filter((c) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesSearch =
        c.title.toLowerCase().includes(query) ||
        (c.client_name ?? "").toLowerCase().includes(query);
      if (!matchesSearch) return false;
    }
    if (practiceAreaFilter !== "all" && c.practice_area !== practiceAreaFilter) {
      return false;
    }
    if (statusFilter !== "all" && c.status !== statusFilter) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Search cases..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={Search}
            className="w-64"
          />
          <SelectFilter
            value={practiceAreaFilter}
            onValueChange={setPracticeAreaFilter}
            placeholder="Practice Area"
            options={PRACTICE_AREAS}
          />
          <SelectFilter
            value={statusFilter}
            onValueChange={setStatusFilter}
            placeholder="Status"
            options={CASE_STATUSES}
          />
        </div>
        <Button variant="primary" onClick={() => setFormOpen(true)}>
          <Plus size={16} />
          New Case
        </Button>
      </div>

      {isPending && <Loading size="md" text="Loading cases..." />}

      {error && (
        <p className="text-sm text-red-600 py-4">
          Failed to load cases. Please try again.
        </p>
      )}

      {filteredCases && filteredCases.length === 0 && (
        <EmptyState
          icon={Briefcase}
          title="No cases found"
          description={
            searchQuery || practiceAreaFilter !== "all" || statusFilter !== "all"
              ? "No cases match your current filters. Try adjusting your search criteria."
              : "You have not created any cases yet. Start by creating your first case."
          }
          actionLabel={!searchQuery ? "Create Case" : undefined}
          onAction={!searchQuery ? () => setFormOpen(true) : undefined}
        />
      )}

      {filteredCases && filteredCases.length > 0 && (
        <div className="grid gap-3">
          {filteredCases.map((caseItem) => (
            <button
              key={caseItem.id}
              type="button"
              onClick={() => onSelectCase?.(caseItem)}
              className={clsx(
                "w-full text-left rounded-xl border border-gray-200 bg-white p-4 sm:p-5",
                "hover:border-gray-300 hover:shadow-sm transition-all",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-gray-900 truncate">
                    {caseItem.title}
                  </h3>
                  {caseItem.client_name && (
                    <p className="text-sm text-gray-500 mt-0.5">
                      {caseItem.client_name}
                    </p>
                  )}
                </div>
                <Badge variant={statusBadgeVariant[caseItem.status]}>
                  {caseItem.status}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <Badge variant="info">
                  {classifyPracticeArea(caseItem.practice_area)}
                </Badge>
                {caseItem.case_type && (
                  <Badge variant="neutral">{caseItem.case_type}</Badge>
                )}
                <span className="text-xs text-gray-400 ml-auto">
                  Created {formatDate(caseItem.created_at)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      <CaseForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={() => setFormOpen(false)}
      />
    </div>
  );
}
