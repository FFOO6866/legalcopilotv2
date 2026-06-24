import { Loader2 } from "lucide-react";
import clsx from "clsx";

type LoadingSize = "sm" | "md" | "lg";

interface LoadingProps {
  fullscreen?: boolean;
  size?: LoadingSize;
  text?: string;
}

const sizeMap: Record<LoadingSize, number> = {
  sm: 16,
  md: 24,
  lg: 36,
};

export default function Loading({
  fullscreen = false,
  size = "md",
  text,
}: LoadingProps) {
  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3">
      <Loader2
        size={sizeMap[size]}
        className="animate-spin text-blue-600"
      />
      {text && (
        <p
          className={clsx(
            "text-gray-500",
            size === "sm" && "text-xs",
            size === "md" && "text-sm",
            size === "lg" && "text-base",
          )}
        >
          {text}
        </p>
      )}
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm">
        {spinner}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-8">
      {spinner}
    </div>
  );
}
