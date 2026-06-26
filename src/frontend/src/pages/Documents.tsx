import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, Filter, Search } from "lucide-react";
import * as Select from "@radix-ui/react-select";
import { ChevronDown, Check } from "lucide-react";
import * as caseService from "@/services/case.service";
import { useAuthStore } from "@/stores/authStore";
import type { Document as CaseDocument } from "@/types/case";
import { FILE_TYPES } from "@/utils/constants";
import { formatDate } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Input from "@/components/common/Input";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";

interface DocumentsProps {
  embedded?: boolean;
}

export default function Documents({ embedded }: DocumentsProps) {
  const user = useAuthStore((state) => state.user);
  const firmId = user?.firm_id ?? "";
  const [searchQuery, setSearchQuery] = useState("");
  const [fileTypeFilter, setFileTypeFilter] = useState<string>("all");

  const casesQuery = useQuery({
    queryKey: ["cases", firmId],
    queryFn: () => caseService.listCases(firmId),
    enabled: !!firmId,
  });

  const cases = casesQuery.data?.items ?? [];

  const documentQueries = useQuery({
    queryKey: ["all-documents", firmId, cases.map((c) => c.id)],
    queryFn: async () => {
      if (cases.length === 0) return [] as CaseDocument[];
      const results = await Promise.all(
        cases.map((c) => caseService.listDocuments(c.id, firmId, undefined, 100)),
      );
      return results.flatMap((r) => r.items);
    },
    enabled: !!firmId && cases.length > 0,
  });

  const allDocuments = documentQueries.data ?? [];

  const caseNameMap = new Map<string, string>();
  for (const c of cases) {
    caseNameMap.set(c.id, c.title);
  }

  const filteredDocuments = allDocuments.filter((doc) => {
    if (fileTypeFilter !== "all" && doc.file_type !== fileTypeFilter) {
      return false;
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const caseName = caseNameMap.get(doc.case_id) ?? "";
      return (
        doc.filename.toLowerCase().includes(query) ||
        caseName.toLowerCase().includes(query)
      );
    }
    return true;
  });

  const isLoading = casesQuery.isPending || (cases.length > 0 && documentQueries.isPending);
  const isError = casesQuery.isError || documentQueries.isError;

  const content = (
    <>
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
        <Input
          placeholder="Search documents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          icon={Search}
          className="w-full sm:w-72"
        />
        <Select.Root value={fileTypeFilter} onValueChange={setFileTypeFilter}>
          <Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]">
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-gray-400" />
              <Select.Value placeholder="File Type" />
            </div>
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
                  <Select.ItemText>All Types</Select.ItemText>
                  <Select.ItemIndicator>
                    <Check size={14} />
                  </Select.ItemIndicator>
                </Select.Item>
                {FILE_TYPES.map((ft) => (
                  <Select.Item
                    key={ft.value}
                    value={ft.value}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
                  >
                    <Select.ItemText>{ft.label}</Select.ItemText>
                    <Select.ItemIndicator>
                      <Check size={14} />
                    </Select.ItemIndicator>
                  </Select.Item>
                ))}
              </Select.Viewport>
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      {isLoading && <Loading size="md" text="Loading documents..." />}

      {isError && (
        <p className="text-sm text-red-600 py-4">Failed to load documents. Please try again.</p>
      )}

      {!isLoading && !isError && filteredDocuments.length === 0 && (
        <EmptyState
          icon={FileText}
          title="No documents found"
          description={
            searchQuery || fileTypeFilter !== "all"
              ? "No documents match your current filters. Try adjusting your search criteria."
              : "No documents have been uploaded yet. Go to a specific case to upload documents."
          }
        />
      )}

      {filteredDocuments.length > 0 && (
        <div className="space-y-2">
          {filteredDocuments.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 hover:border-gray-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50 shrink-0">
                  <FileText size={18} className="text-blue-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">
                    {doc.filename}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {caseNameMap.get(doc.case_id) ?? "Unknown case"} - {formatDate(doc.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant="neutral">{doc.file_type}</Badge>
                <Badge
                  variant={
                    doc.ocr_status === "complete"
                      ? "success"
                      : doc.ocr_status === "failed"
                        ? "danger"
                        : "warning"
                  }
                >
                  {doc.ocr_status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );

  if (embedded) {
    return content;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Documents</h1>
        <p className="text-sm text-gray-500 mt-1">
          Browse and manage documents across all your cases
        </p>
      </div>
      {content}
    </div>
  );
}
