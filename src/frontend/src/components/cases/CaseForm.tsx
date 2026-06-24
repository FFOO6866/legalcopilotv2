import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import { X, ChevronDown, Check } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as caseService from "@/services/case.service";
import { useAuthStore } from "@/stores/authStore";
import type { Case, PracticeArea } from "@/types/case";
import { PRACTICE_AREAS } from "@/utils/constants";
import Input from "@/components/common/Input";
import Button from "@/components/common/Button";

interface CaseFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  initialValues?: Partial<Case>;
}

interface FormState {
  title: string;
  client_name: string;
  practice_area: PracticeArea;
  case_type: string;
  description: string;
}

const emptyForm: FormState = {
  title: "",
  client_name: "",
  practice_area: "general",
  case_type: "",
  description: "",
};

function formFromValues(values?: Partial<Case>): FormState {
  return {
    title: values?.title ?? "",
    client_name: values?.client_name ?? "",
    practice_area: values?.practice_area ?? "general",
    case_type: values?.case_type ?? "",
    description: values?.description ?? "",
  };
}

export default function CaseForm({
  open,
  onOpenChange,
  onSubmit,
  initialValues,
}: CaseFormProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const firmId = user?.firm_id ?? "";
  const isEditing = !!initialValues?.id;

  const [form, setForm] = useState<FormState>(formFromValues(initialValues));
  const [titleError, setTitleError] = useState<string | null>(null);

  // Reinitialize form when dialog opens or initialValues change
  useEffect(() => {
    if (open) {
      setForm(formFromValues(initialValues));
      setTitleError(null);
    }
  }, [open, initialValues]);

  const createMutation = useMutation({
    mutationFn: (data: FormState) =>
      caseService.createCase(
        firmId,
        user?.id ?? "",
        data.title,
        data.practice_area,
        data.case_type,
        data.client_name,
        data.description,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      onSubmit();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: FormState) =>
      caseService.updateCase(initialValues!.id!, firmId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["case", initialValues?.id] });
      onSubmit();
    },
  });

  const mutation = isEditing ? updateMutation : createMutation;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) {
      setTitleError("Case title is required");
      return;
    }
    setTitleError(null);
    mutation.mutate(form);
  }

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (key === "title" && titleError) {
      setTitleError(null);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 animate-in fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-gray-200 bg-white shadow-xl animate-in fade-in-0 zoom-in-95">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-gray-900">
              {initialValues ? "Edit Case" : "New Case"}
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
            <Input
              label="Case Title"
              required
              placeholder="Enter case title"
              value={form.title}
              onChange={(e) => updateField("title", e.target.value)}
              error={titleError ?? undefined}
            />

            <Input
              label="Client Name"
              placeholder="Enter client name"
              value={form.client_name}
              onChange={(e) => updateField("client_name", e.target.value)}
            />

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">
                Practice Area
              </label>
              <Select.Root
                value={form.practice_area}
                onValueChange={(val) => updateField("practice_area", val as PracticeArea)}
              >
                <Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full">
                  <Select.Value />
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
                      {PRACTICE_AREAS.map((area) => (
                        <Select.Item
                          key={area.value}
                          value={area.value}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50 data-[state=checked]:text-blue-600"
                        >
                          <Select.ItemText>{area.label}</Select.ItemText>
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

            <Input
              label="Case Type"
              placeholder="e.g., Civil Suit, Appeal, Application"
              value={form.case_type}
              onChange={(e) => updateField("case_type", e.target.value)}
            />

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                value={form.description}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="Describe the case details"
                rows={4}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
            </div>

            {mutation.isError && (
              <p className="text-sm text-red-600">
                {isEditing ? "Failed to update case." : "Failed to create case."} Please try again.
              </p>
            )}

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
                isLoading={mutation.isPending}
              >
                {initialValues ? "Save Changes" : "Create Case"}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
