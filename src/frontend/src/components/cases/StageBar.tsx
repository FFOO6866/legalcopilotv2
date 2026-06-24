import clsx from "clsx";
import { Check } from "lucide-react";
import { CASE_STAGES } from "@/utils/constants";
import type { CaseStage } from "@/types/case";

interface StageBarProps {
  currentStage: CaseStage;
  className?: string;
}

export default function StageBar({ currentStage, className }: StageBarProps) {
  const currentIndex = CASE_STAGES.findIndex((s) => s.value === currentStage);

  return (
    <div className={clsx("w-full", className)}>
      {/* Desktop: horizontal stepper */}
      <div className="hidden sm:flex items-center gap-1">
        {CASE_STAGES.map((stage, i) => {
          const isComplete = i < currentIndex;
          const isCurrent = i === currentIndex;

          return (
            <div key={stage.value} className="flex items-center flex-1 min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <div
                  className={clsx(
                    "flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0 transition-colors",
                    isComplete && "bg-green-600 text-white",
                    isCurrent && "bg-blue-600 text-white ring-2 ring-blue-200",
                    !isComplete && !isCurrent && "bg-gray-200 text-gray-500",
                  )}
                >
                  {isComplete ? <Check size={12} /> : i + 1}
                </div>
                <span
                  className={clsx(
                    "text-xs font-medium truncate",
                    isCurrent ? "text-blue-700" : isComplete ? "text-green-700" : "text-gray-400",
                  )}
                >
                  {stage.label}
                </span>
              </div>
              {i < CASE_STAGES.length - 1 && (
                <div
                  className={clsx(
                    "flex-1 h-0.5 mx-1.5 rounded-full",
                    i < currentIndex ? "bg-green-400" : "bg-gray-200",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Mobile: compact indicator */}
      <div className="sm:hidden flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / CASE_STAGES.length) * 100}%` }}
          />
        </div>
        <span className="text-xs font-medium text-gray-600 shrink-0">
          {currentIndex + 1}/{CASE_STAGES.length}
        </span>
      </div>
    </div>
  );
}
