import { useState } from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import clsx from "clsx";
import type { Source } from "@/types/chat";
import Badge from "@/components/common/Badge";

interface SourcesListProps {
  sources: Source[];
}

export default function SourcesList({ sources }: SourcesListProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (sources.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Sources ({sources.length})
      </button>

      {isExpanded && (
        <div className="divide-y divide-gray-100">
          {sources.map((source, index) => (
            <div key={`${source.citation}-${index}`} className="px-3 py-2.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-900 truncate">
                    {source.case_name}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {source.citation}
                    {source.court && ` - ${source.court}`}
                  </p>
                </div>
                {source.treatment_warning && (
                  <Badge
                    variant={
                      source.treatment_warning.toLowerCase().includes("overruled")
                        ? "danger"
                        : "warning"
                    }
                  >
                    <AlertTriangle size={10} className="mr-1" />
                    {source.treatment_warning}
                  </Badge>
                )}
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className={clsx(
                      "h-full rounded-full transition-all",
                      source.score >= 0.8
                        ? "bg-green-500"
                        : source.score >= 0.5
                          ? "bg-yellow-500"
                          : "bg-red-400",
                    )}
                    style={{ width: `${Math.round(source.score * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 shrink-0 tabular-nums">
                  {Math.round(source.score * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
