import { type InputHTMLAttributes, type ElementType, useId } from "react";
import clsx from "clsx";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  error?: string;
  icon?: ElementType;
}

export default function Input({
  label,
  error,
  icon: Icon,
  className,
  required,
  id: externalId,
  ...rest
}: InputProps) {
  const generatedId = useId();
  const inputId = externalId ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-sm font-medium text-gray-700"
        >
          {label}
          {required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-gray-400">
            <Icon size={16} />
          </div>
        )}
        <input
          id={inputId}
          required={required}
          className={clsx(
            "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900",
            "placeholder:text-gray-400",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            "disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed",
            error && "border-red-500 focus:ring-red-500 focus:border-red-500",
            Icon && "pl-9",
            className,
          )}
          {...rest}
        />
      </div>
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}
