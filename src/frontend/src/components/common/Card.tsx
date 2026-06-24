import { type ReactNode } from "react";
import clsx from "clsx";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  headerAction?: ReactNode;
}

export default function Card({
  title,
  subtitle,
  children,
  className,
  headerAction,
}: CardProps) {
  const hasHeader = title || subtitle || headerAction;

  return (
    <div
      className={clsx(
        "rounded-xl border border-gray-200 bg-white shadow-sm",
        className,
      )}
    >
      {hasHeader && (
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-4">
          <div className="min-w-0">
            {title && (
              <h3 className="text-base font-semibold text-gray-900 truncate">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 text-sm text-gray-500 truncate">
                {subtitle}
              </p>
            )}
          </div>
          {headerAction && (
            <div className="shrink-0">{headerAction}</div>
          )}
        </div>
      )}
      <div className="px-6 py-4">{children}</div>
    </div>
  );
}
