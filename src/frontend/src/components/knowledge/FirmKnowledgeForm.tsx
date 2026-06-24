import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import { X, ChevronDown, Check } from "lucide-react";
import clsx from "clsx";
import type { FirmKnowledge } from "@/types/knowledge";
import Input from "@/components/common/Input";
import Button from "@/components/common/Button";

type KnowledgeCategory = FirmKnowledge["category"];

interface FirmKnowledgeFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { title: string; category: KnowledgeCategory; content: string }) => void;
  isSubmitting?: boolean;
}

const CATEGORIES: Array<{ value: KnowledgeCategory; label: string }> = [
  { value: "precedent", label: "Precedent" },
  { value: "playbook", label: "Playbook" },
  { value: "template", label: "Template" },
  { value: "policy", label: "Policy" },
  { value: "training", label: "Training" },
  { value: "other", label: "Other" },
];

const TITLE_MAX = 500;
const CONTENT_MAX = 100000;

export default function FirmKnowledgeForm({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
}: FirmKnowledgeFormProps) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<KnowledgeCategory>("other");
  const [content, setContent] = useState("");
  const [titleError, setTitleError] = useState<string | null>(null);

  function resetForm() {
    setTitle("");
    setCategory("other");
    setContent("");
    setTitleError(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setTitleError("Title is required");
      return;
    }
    setTitleError(null);
    onSubmit({ title: title.trim(), category, content: content.trim() });
    resetForm();
  }

  function handleTitleChange(value: string) {
    if (value.length <= TITLE_MAX) {
      setTitle(value);
      if (titleError) setTitleError(null);
    }
  }

  function handleContentChange(value: string) {
    if (value.length <= CONTENT_MAX) {
      setContent(value);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 animate-in fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-xl -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-gray-200 bg-white shadow-xl animate-in fade-in-0 zoom-in-95 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-gray-900">
              Add Knowledge Entry
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
            <div>
              <Input
                label="Title"
                required
                placeholder="Enter knowledge title"
                value={title}
                onChange={(e) => handleTitleChange(e.target.value)}
                error={titleError ?? undefined}
              />
              <p
                className={clsx(
                  "text-xs mt-1 text-right tabular-nums",
                  title.length > TITLE_MAX * 0.9 ? "text-yellow-600" : "text-gray-400",
                )}
              >
                {title.length} / {TITLE_MAX}
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Category</label>
              <Select.Root value={category} onValueChange={(val) => setCategory(val as KnowledgeCategory)}>
                <Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full">
                  <Select.Value />
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
                      {CATEGORIES.map((cat) => (
                        <Select.Item
                          key={cat.value}
                          value={cat.value}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
                        >
                          <Select.ItemText>{cat.label}</Select.ItemText>
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

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Content</label>
              <textarea
                value={content}
                onChange={(e) => handleContentChange(e.target.value)}
                placeholder="Enter the knowledge content, legal analysis, template text, or policy details..."
                rows={10}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y min-h-[200px]"
              />
              <p
                className={clsx(
                  "text-xs text-right tabular-nums",
                  content.length > CONTENT_MAX * 0.9 ? "text-yellow-600" : "text-gray-400",
                )}
              >
                {content.length.toLocaleString()} / {CONTENT_MAX.toLocaleString()}
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={() => onOpenChange(false)}
                type="button"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                type="submit"
                isLoading={isSubmitting}
              >
                Add Knowledge
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
