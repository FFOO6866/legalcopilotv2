import { useState, useRef, useCallback, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import clsx from "clsx";
import { MAX_MESSAGE_LENGTH } from "@/utils/constants";

interface ChatInputProps {
  onSend: (content: string) => void;
  isProcessing: boolean;
  disabled?: boolean;
}

export default function ChatInput({
  onSend,
  isProcessing,
  disabled = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const lineHeight = 24;
    const maxHeight = lineHeight * 5;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const newValue = e.target.value;
    if (newValue.length <= MAX_MESSAGE_LENGTH) {
      setValue(newValue);
      adjustHeight();
    }
  }

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || isProcessing || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isDisabled = disabled || isProcessing;
  const canSend = value.trim().length > 0 && !isDisabled;
  const charCount = value.length;
  const showCharWarning = charCount > MAX_MESSAGE_LENGTH * 0.9;

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="flex items-end gap-3">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={
              isProcessing
                ? "Waiting for response..."
                : "Type your legal question..."
            }
            disabled={isDisabled}
            rows={1}
            className={clsx(
              "w-full resize-none rounded-xl border border-gray-300 bg-white px-4 py-3 pr-12 text-sm text-gray-900",
              "placeholder:text-gray-400",
              "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
              "disabled:bg-gray-50 disabled:cursor-not-allowed",
              "transition-colors",
            )}
          />
        </div>
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className={clsx(
            "flex items-center justify-center w-10 h-10 rounded-xl transition-colors shrink-0",
            canSend
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-gray-100 text-gray-400 cursor-not-allowed",
          )}
          aria-label="Send message"
        >
          <SendHorizontal size={18} />
        </button>
      </div>
      {showCharWarning && (
        <p
          className={clsx(
            "text-xs mt-1.5 text-right tabular-nums",
            charCount >= MAX_MESSAGE_LENGTH ? "text-red-500" : "text-gray-400",
          )}
        >
          {charCount.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()}
        </p>
      )}
    </div>
  );
}
