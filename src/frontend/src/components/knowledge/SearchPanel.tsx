import { useState } from "react";
import { Search, ChevronDown, Check, BookOpen, ChevronRight } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import * as Select from "@radix-ui/react-select";
import clsx from "clsx";
import * as knowledgeService from "@/services/knowledge.service";
import type { KnowledgeEntry } from "@/types/knowledge";
import { JURISDICTIONS } from "@/utils/constants";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Input from "@/components/common/Input";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";

interface SearchResult extends KnowledgeEntry {
  id?: string;
}

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [currentLimit, setCurrentLimit] = useState(20);
  const pageSize = 20;

  const searchMutation = useMutation({
    mutationFn: (params: { query: string; limit: number }) =>
      knowledgeService.searchCases(
        params.query,
        jurisdiction === "all" ? undefined : jurisdiction,
        undefined,
        undefined,
        undefined,
        params.limit,
      ),
    onSuccess: (data, variables) => {
      setResults(data);
      setHasMore(data.length >= variables.limit);
      setCurrentLimit(variables.limit);
    },
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setCurrentLimit(pageSize);
    setExpandedId(null);
    searchMutation.mutate({ query: query.trim(), limit: pageSize });
  }

  function handleLoadMore() {
    const nextLimit = currentLimit + pageSize;
    searchMutation.mutate({ query: query.trim(), limit: nextLimit });
  }

  function toggleExpand(citation: string) {
    setExpandedId((prev) => (prev === citation ? null : citation));
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSearch} className="space-y-3">
        <Input
          placeholder="Search case law, statutes, or legal concepts..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          icon={Search}
        />

        <div className="flex flex-wrap items-center gap-3">
          <Select.Root value={jurisdiction} onValueChange={setJurisdiction}>
            <Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]">
              <Select.Value placeholder="Jurisdiction" />
              <Select.Icon>
                <ChevronDown size={14} className="text-gray-400" />
              </Select.Icon>
            </Select.Trigger>
            <Select.Portal>
              <Select.Content
                className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg max-h-60"
                position="popper"
                sideOffset={4}
              >
                <Select.Viewport className="p-1">
                  <Select.Item
                    value="all"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
                  >
                    <Select.ItemText>All Jurisdictions</Select.ItemText>
                    <Select.ItemIndicator><Check size={14} /></Select.ItemIndicator>
                  </Select.Item>
                  {JURISDICTIONS.map((j) => (
                    <Select.Item
                      key={j.value}
                      value={j.value}
                      className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
                    >
                      <Select.ItemText>{j.label}</Select.ItemText>
                      <Select.ItemIndicator><Check size={14} /></Select.ItemIndicator>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>

          <Button
            type="submit"
            variant="primary"
            isLoading={searchMutation.isPending && currentLimit === pageSize}
          >
            <Search size={16} />
            Search
          </Button>
        </div>
      </form>

      {searchMutation.isPending && currentLimit === pageSize && (
        <Loading size="md" text="Searching legal databases..." />
      )}

      {searchMutation.isError && (
        <p className="text-sm text-red-600 py-4">
          Search failed. Please try again.
        </p>
      )}

      {!searchMutation.isPending && results.length === 0 && searchMutation.isSuccess && (
        <EmptyState
          icon={BookOpen}
          title="No results found"
          description="Try adjusting your search terms, jurisdiction, or practice area filters."
        />
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            Showing {results.length} result{results.length !== 1 ? "s" : ""}
          </p>

          {results.map((result, index) => {
            const resultKey = result.citation + "-" + index;
            const isExpanded = expandedId === resultKey;

            return (
              <div
                key={resultKey}
                className="rounded-xl border border-gray-200 bg-white overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => toggleExpand(resultKey)}
                  className="w-full text-left p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <ChevronRight
                          size={14}
                          className={clsx(
                            "text-gray-400 transition-transform shrink-0",
                            isExpanded && "rotate-90",
                          )}
                        />
                        <h3 className="text-sm font-semibold text-gray-900 truncate">
                          {result.case_name}
                        </h3>
                      </div>
                      <p className="text-xs text-gray-500 ml-6">
                        {result.citation}
                        {result.court && ` | ${result.court}`}
                        {result.year > 0 && ` | ${result.year}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {result.jurisdiction && (
                        <Badge variant="info">{result.jurisdiction}</Badge>
                      )}
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-0 border-t border-gray-100">
                    <div className="pl-6 pt-3">
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {result.summary}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        {result.court && (
                          <Badge variant="neutral">{result.court}</Badge>
                        )}
                        {result.year > 0 && (
                          <Badge variant="neutral">{result.year}</Badge>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {hasMore && (
            <div className="flex justify-center pt-2">
              <Button
                variant="secondary"
                onClick={handleLoadMore}
                isLoading={searchMutation.isPending && currentLimit > pageSize}
              >
                Load more results
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
