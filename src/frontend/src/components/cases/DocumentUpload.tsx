import { useState, useRef, useCallback } from "react";
import { Upload, File, CheckCircle2, Clock, Loader2, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Select from "@radix-ui/react-select";
import { ChevronDown, Check } from "lucide-react";
import clsx from "clsx";
import { useAuthStore } from "@/stores/authStore";
import * as caseService from "@/services/case.service";
import type { Document, FileType } from "@/types/case";
import { FILE_TYPES } from "@/utils/constants";
import { formatDate } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";

interface DocumentUploadProps {
  caseId: string;
  firmId: string;
}

interface UploadingFile {
  id: string;
  name: string;
  progress: number;
  status: "uploading" | "complete" | "error";
  errorMessage?: string;
}

const ocrStatusBadge: Record<string, { variant: "success" | "warning" | "neutral" | "info"; label: string }> = {
  complete: { variant: "success", label: "Processed" },
  processing: { variant: "info", label: "Processing" },
  pending: { variant: "warning", label: "Pending" },
  failed: { variant: "neutral", label: "Failed" },
};

export default function DocumentUpload({ caseId, firmId }: DocumentUploadProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFileType, setSelectedFileType] = useState<FileType>("other");
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);

  const {
    data: documents,
    isPending,
  } = useQuery({
    queryKey: ["documents", caseId, firmId],
    queryFn: async () => {
      const result = await caseService.listDocuments(caseId, firmId);
      return result.items;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const uploadId = crypto.randomUUID();
      setUploadingFiles((prev) => [
        ...prev,
        { id: uploadId, name: file.name, progress: 0, status: "uploading" },
      ]);

      // Read file content as text for the Nexus handler
      const contentText = await file.text();

      setUploadingFiles((prev) =>
        prev.map((f) =>
          f.id === uploadId ? { ...f, progress: 50 } : f,
        ),
      );

      const doc = await caseService.uploadDocument(
        caseId,
        firmId,
        user?.id ?? "",
        file.name,
        selectedFileType,
        contentText,
      );

      setUploadingFiles((prev) =>
        prev.map((f) =>
          f.id === uploadId ? { ...f, progress: 100, status: "complete" } : f,
        ),
      );

      return doc;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", caseId, firmId] });
    },
    onError: (_error, _file) => {
      setUploadingFiles((prev) => {
        const uploading = prev.find((f) => f.status === "uploading");
        if (uploading) {
          return prev.map((f) =>
            f.id === uploading.id
              ? { ...f, status: "error" as const, errorMessage: "Upload failed" }
              : f,
          );
        }
        return prev;
      });
    },
  });

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      Array.from(files).forEach((file) => {
        uploadMutation.mutate(file);
      });
    },
    [uploadMutation],
  );

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function removeUploadingFile(id: string) {
    setUploadingFiles((prev) => prev.filter((f) => f.id !== id));
  }

  const fileTypeLabel = FILE_TYPES.find((ft) => ft.value === selectedFileType)?.label ?? "Other";

  return (
    <div className="space-y-6">
      {/* File type selector */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-gray-700">Document Type</label>
        <Select.Root value={selectedFileType} onValueChange={(val) => setSelectedFileType(val as FileType)}>
          <Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full max-w-xs">
            <Select.Value>{fileTypeLabel}</Select.Value>
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

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={clsx(
          "flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 cursor-pointer transition-colors",
          isDragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 hover:bg-gray-50",
        )}
      >
        <div className="flex items-center justify-center w-12 h-12 rounded-full bg-gray-100">
          <Upload size={20} className="text-gray-500" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-gray-700">
            Drop files here or click to browse
          </p>
          <p className="text-xs text-gray-500 mt-1">
            PDF, DOCX, TXT, or image files supported
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg"
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
        />
      </div>

      {/* Upload progress */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700">Uploads</h4>
          {uploadingFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3"
            >
              {file.status === "uploading" && (
                <Loader2 size={16} className="animate-spin text-blue-600 shrink-0" />
              )}
              {file.status === "complete" && (
                <CheckCircle2 size={16} className="text-green-600 shrink-0" />
              )}
              {file.status === "error" && (
                <X size={16} className="text-red-500 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 truncate">{file.name}</p>
                {file.status === "uploading" && (
                  <div className="mt-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-blue-600 transition-all"
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                )}
                {file.status === "error" && (
                  <p className="text-xs text-red-500 mt-0.5">{file.errorMessage}</p>
                )}
              </div>
              {file.status !== "uploading" && (
                <button
                  type="button"
                  onClick={() => removeUploadingFile(file.id)}
                  className="p-1 text-gray-400 hover:text-gray-600 shrink-0"
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Document list */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Uploaded Documents</h4>
        {isPending && <Loading size="sm" />}

        {documents && documents.length === 0 && (
          <EmptyState
            icon={File}
            title="No documents yet"
            description="Upload documents to this case for AI-powered analysis and research."
          />
        )}

        {documents && documents.length > 0 && (
          <div className="space-y-2">
            {documents.map((doc) => {
              const statusInfo = ocrStatusBadge[doc.ocr_status] ?? ocrStatusBadge.pending;
              return (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3"
                >
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gray-50 shrink-0">
                    {doc.ocr_status === "processing" ? (
                      <Loader2 size={16} className="animate-spin text-blue-600" />
                    ) : doc.ocr_status === "complete" ? (
                      <CheckCircle2 size={16} className="text-green-600" />
                    ) : (
                      <Clock size={16} className="text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {doc.filename}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge variant="neutral">{doc.file_type}</Badge>
                      <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                      <span className="text-xs text-gray-400">
                        {formatDate(doc.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
