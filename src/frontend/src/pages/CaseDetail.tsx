import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowLeft,
  FileText,
  MessageSquare,
  Info,
  Upload,
  Calendar,
  User as UserIcon,
  Clock,
  Search,
  PenTool,
  BarChart3,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Copy,
  Check,
} from "lucide-react";
import clsx from "clsx";
import * as caseService from "@/services/case.service";
import * as chatService from "@/services/chat.service";
import { useAuthStore } from "@/stores/authStore";
import { useCaseStore } from "@/stores/caseStore";
import type { Case, Document as CaseDocument } from "@/types/case";
import { ROUTES, FILE_TYPES, CASE_STAGES, DRAFT_TYPES } from "@/utils/constants";
import { formatDate, classifyPracticeArea } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import Loading from "@/components/common/Loading";
import EmptyState from "@/components/common/EmptyState";
import StageBar from "@/components/cases/StageBar";
import CaseForm from "@/components/cases/CaseForm";
import ChatArea from "@/components/chat/ChatArea";

type CaseStatus = Case["status"];

const statusVariant: Record<CaseStatus, "success" | "info" | "neutral" | "warning"> = {
  open: "info",
  in_progress: "success",
  pending_review: "warning",
  under_review: "warning",
  closed: "neutral",
  archived: "neutral",
};

const tabTriggerClass = clsx(
  "flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap",
  "data-[state=active]:border-blue-600 data-[state=active]:text-blue-600",
  "data-[state=inactive]:border-transparent data-[state=inactive]:text-gray-500 data-[state=inactive]:hover:text-gray-700",
);

// --- Tab Components ---

function OverviewTab({ caseData }: { caseData: Case }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="Case Information">
        <dl className="space-y-3">
          {[
            ["Client", caseData.client_name],
            ["Practice Area", classifyPracticeArea(caseData.practice_area)],
            ["Case Type", caseData.case_type],
            ["Priority", caseData.priority],
            ["Opposing Party", caseData.opposing_party],
            ["Court", caseData.court],
            ["Case Number", caseData.case_number],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</dt>
              <dd className="text-sm text-gray-900 mt-0.5">{value || "Not specified"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Description">
        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
          {caseData.description || "No description provided."}
        </p>
      </Card>

      <Card title="Timeline">
        <dl className="space-y-3">
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-gray-400" />
            <div>
              <dt className="text-xs font-medium text-gray-500">Created</dt>
              <dd className="text-sm text-gray-900">{formatDate(caseData.created_at)}</dd>
            </div>
          </div>
          {caseData.filing_date && (
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-gray-400" />
              <div>
                <dt className="text-xs font-medium text-gray-500">Filing Date</dt>
                <dd className="text-sm text-gray-900">{formatDate(caseData.filing_date)}</dd>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-gray-400" />
            <div>
              <dt className="text-xs font-medium text-gray-500">Last Updated</dt>
              <dd className="text-sm text-gray-900">{formatDate(caseData.updated_at)}</dd>
            </div>
          </div>
        </dl>
      </Card>

      <Card title="Assigned To">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-100">
            <UserIcon size={18} className="text-gray-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {caseData.assigned_user_id ? `User ${caseData.assigned_user_id.slice(0, 8)}` : "Unassigned"}
            </p>
            <p className="text-xs text-gray-500">
              Created by {caseData.created_by_id ? caseData.created_by_id.slice(0, 8) : "Unknown"}
            </p>
          </div>
        </div>
      </Card>

      {caseData.tags.length > 0 && (
        <Card title="Tags">
          <div className="flex flex-wrap gap-1.5">
            {caseData.tags.map((tag) => (
              <Badge key={tag} variant="info">{tag}</Badge>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function DocumentsTab({ caseId, firmId, userId }: { caseId: string; firmId: string; userId: string }) {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [filename, setFilename] = useState("");
  const [fileType, setFileType] = useState("other");
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const documentsQuery = useQuery({
    queryKey: ["case-documents", caseId, firmId],
    queryFn: () => caseService.listDocuments(caseId, firmId),
    enabled: !!caseId && !!firmId,
  });

  const uploadMutation = useMutation({
    mutationFn: () =>
      caseService.uploadDocument(caseId, firmId, userId, filename, fileType as CaseDocument["file_type"]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-documents", caseId, firmId] });
      setFilename("");
      setFileType("other");
      setUploading(false);
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 3000);
    },
  });

  const documents = documentsQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{documents.length} document(s)</p>
        <Button variant="primary" size="sm" onClick={() => setUploading(true)}>
          <Upload size={14} />
          Upload
        </Button>
      </div>

      {uploadSuccess && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-800">
          <Check size={16} className="shrink-0" />
          Document uploaded successfully.
        </div>
      )}

      {uploading && (
        <Card>
          <div className="space-y-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Filename</label>
              <input
                type="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                placeholder="document.pdf"
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">File Type</label>
              <select
                value={fileType}
                onChange={(e) => setFileType(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {FILE_TYPES.map((ft) => (
                  <option key={ft.value} value={ft.value}>{ft.label}</option>
                ))}
              </select>
            </div>
            {uploadMutation.isError && (
              <p className="text-sm text-red-600">Upload failed. Please try again.</p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setUploading(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => uploadMutation.mutate()}
                isLoading={uploadMutation.isPending}
                disabled={!filename.trim()}
              >
                Upload
              </Button>
            </div>
          </div>
        </Card>
      )}

      {documentsQuery.isPending && <Loading size="md" text="Loading documents..." />}
      {documentsQuery.isError && (
        <p className="text-sm text-red-600 py-4">Failed to load documents.</p>
      )}

      {!documentsQuery.isPending && documents.length === 0 && !uploading && (
        <EmptyState
          icon={FileText}
          title="No documents"
          description="Upload case documents to enable AI-powered analysis and timeline extraction."
          actionLabel="Upload Document"
          onAction={() => setUploading(true)}
        />
      )}

      {documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText size={18} className="text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-500">{formatDate(doc.created_at)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant="neutral">{doc.file_type}</Badge>
                <Badge
                  variant={
                    doc.ocr_status === "complete"
                      ? "success"
                      : doc.ocr_status === "failed"
                        ? "danger"
                        : "warning"
                  }
                >
                  {doc.ocr_status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChronologyTab({ onGoToDocuments }: { caseId: string; firmId: string; onGoToDocuments: () => void }) {
  return (
    <EmptyState
      icon={Clock}
      title="Chronology — coming soon"
      description="Upload documents in the Documents tab first. The AI will automatically extract key dates, parties, and events to build your case timeline."
      actionLabel="Go to Documents"
      onAction={onGoToDocuments}
    />
  );
}

function ResearchTab({ onOpenChat }: { caseId: string; firmId: string; onOpenChat: () => void }) {
  return (
    <EmptyState
      icon={Search}
      title="Research — coming soon"
      description="Use the Case Assistant to ask legal research questions. Once research features are live, your findings will be saved here for reference."
      actionLabel="Open Case Assistant"
      onAction={onOpenChat}
    />
  );
}

function getFilteredDraftTypes(practiceArea: string) {
  return DRAFT_TYPES.filter(
    (dt) => !("practiceArea" in dt) || dt.practiceArea === practiceArea,
  );
}

function DraftsTab({ caseId, firmId, caseData }: { caseId: string; firmId: string; caseData: Case }) {
  const user = useAuthStore((state) => state.user);
  const userId = user?.id ?? "";
  const [showForm, setShowForm] = useState(false);
  const filteredDraftTypes = getFilteredDraftTypes(caseData.practice_area);
  const [draftType, setDraftType] = useState(filteredDraftTypes[0]?.value ?? DRAFT_TYPES[0].value);
  const [instructions, setInstructions] = useState("");
  const [generatedDraft, setGeneratedDraft] = useState<{
    content: string;
    type: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const draftMutation = useMutation({
    mutationFn: () =>
      chatService.draftDocument(
        draftType,
        instructions,
        firmId,
        userId,
        caseId,
        caseData.case_type,
        caseData.description,
      ),
    onSuccess: (result) => {
      setGeneratedDraft({
        content: result.draft.draft_text,
        type: draftType,
      });
      setShowForm(false);
      setInstructions("");
    },
  });

  function handleCopy() {
    if (!generatedDraft) return;
    navigator.clipboard.writeText(generatedDraft.content).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      () => {
        // Clipboard API may not be available in insecure contexts
      },
    );
  }

  if (generatedDraft) {
    const typeLabel = DRAFT_TYPES.find((d) => d.value === generatedDraft.type)?.label ?? generatedDraft.type;
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">{typeLabel}</h3>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setGeneratedDraft(null)}>
              Back
            </Button>
            <Button variant="primary" size="sm" onClick={handleCopy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <div className="text-sm text-gray-900 leading-relaxed whitespace-pre-wrap">
            {generatedDraft.content}
          </div>
        </div>
      </div>
    );
  }

  if (showForm) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Generate Document</h3>
          <Button variant="secondary" size="sm" onClick={() => setShowForm(false)}>
            Cancel
          </Button>
        </div>
        <Card>
          <div className="space-y-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Document Type</label>
              <select
                value={draftType}
                onChange={(e) => setDraftType(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {filteredDraftTypes.map((dt) => (
                  <option key={dt.value} value={dt.value}>{dt.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Instructions</label>
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder="Describe what the document should cover, key arguments, specific points to include..."
                rows={5}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
            </div>
            {draftMutation.isError && (
              <p className="text-sm text-red-600">Failed to generate draft. Please try again.</p>
            )}
            <div className="flex justify-end">
              <Button
                variant="primary"
                size="sm"
                onClick={() => draftMutation.mutate()}
                isLoading={draftMutation.isPending}
                disabled={!instructions.trim()}
              >
                <PenTool size={14} />
                Generate Draft
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <EmptyState
      icon={PenTool}
      title="Document drafts"
      description="Generate legal documents using AI — submissions, affidavits, letters of demand, and more — based on your case materials."
      actionLabel="Generate Draft"
      onAction={() => setShowForm(true)}
    />
  );
}

function AnalysisTab({ caseData, onOpenChat }: { caseData: Case; onOpenChat: () => void }) {
  const currentStageIndex = CASE_STAGES.findIndex((s) => s.value === caseData.stage);
  const currentStageLabel = CASE_STAGES[currentStageIndex]?.label ?? caseData.stage;

  return (
    <div className="space-y-5">
      <Card title="Case Summary">
        <dl className="space-y-3">
          <div>
            <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">Current Stage</dt>
            <dd className="text-sm text-gray-900 mt-0.5">{currentStageLabel} (Step {currentStageIndex + 1} of {CASE_STAGES.length})</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">Status</dt>
            <dd className="mt-0.5">
              <Badge variant={statusVariant[caseData.status]}>
                {caseData.status.replace(/_/g, " ")}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">Practice Area</dt>
            <dd className="text-sm text-gray-900 mt-0.5">{classifyPracticeArea(caseData.practice_area)}</dd>
          </div>
        </dl>
      </Card>

      <Card title="AI Analysis — coming soon">
        <p className="text-sm text-gray-500 mb-4">
          Automated IRAC analysis, strengths and weaknesses assessment, and next-step recommendations will appear here once the analysis engine is live.
        </p>
        <p className="text-sm text-gray-500 mb-4">
          In the meantime, use the Case Assistant to ask for case analysis, legal research, and strategy advice.
        </p>
        <Button variant="primary" size="sm" onClick={onOpenChat}>
          <MessageSquare size={14} />
          Open Case Assistant
        </Button>
      </Card>
    </div>
  );
}

// --- Chat Panel (right side) ---

function ChatPanel({ caseId, firmId }: { caseId: string; firmId: string }) {
  const user = useAuthStore((state) => state.user);
  const userId = user?.id ?? "";
  const queryClient = useQueryClient();
  const [activeChatId, setActiveChatId] = useState<string | null>(null);

  const conversationsQuery = useQuery({
    queryKey: ["case-conversations", firmId, caseId],
    queryFn: () => chatService.listConversations(firmId, caseId),
    enabled: !!firmId && !!caseId,
  });

  const conversations = conversationsQuery.data ?? [];

  const createMutation = useMutation({
    mutationFn: () =>
      chatService.createConversation(firmId, userId, caseId, "case_analysis"),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ["case-conversations", firmId, caseId] });
      setActiveChatId(newConv.id);
    },
  });

  // Active chat view
  if (activeChatId) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveChatId(null)}
            className="p-1 rounded hover:bg-gray-200 transition-colors"
            aria-label="Back to conversations"
          >
            <ArrowLeft size={14} />
          </button>
          <h3 className="text-sm font-semibold text-gray-900 truncate">Case Chat</h3>
        </div>
        <ChatArea conversationId={activeChatId} />
      </div>
    );
  }

  // Conversation list view
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Case Assistant</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {conversations.length} conversation(s)
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => createMutation.mutate()}
            isLoading={createMutation.isPending}
          >
            <Plus size={14} />
            New
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {conversationsQuery.isPending && <Loading size="sm" text="Loading..." />}

        {conversations.length === 0 && !conversationsQuery.isPending && (
          <div className="text-center py-8">
            <MessageSquare size={32} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">No conversations yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Start a new chat for AI assistance on this case
            </p>
          </div>
        )}

        {conversations.map((conv) => (
          <button
            key={conv.id}
            type="button"
            onClick={() => setActiveChatId(conv.id)}
            className="w-full text-left rounded-lg border border-gray-200 bg-white px-3 py-2.5 mb-2 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <p className="text-sm font-medium text-gray-900 truncate">
              {conv.title ?? "Untitled"}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={conv.status === "active" ? "success" : "neutral"}>
                {conv.status}
              </Badge>
              <span className="text-xs text-gray-400">
                {formatDate(conv.created_at)}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// --- Main CaseDetail ---

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const firmId = user?.firm_id ?? "";
  const userId = user?.id ?? "";
  const activeTab = useCaseStore((s) => s.activeTab);
  const setActiveTab = useCaseStore((s) => s.setActiveTab);
  const [editOpen, setEditOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [mobileChatOpen, setMobileChatOpen] = useState(false);
  const queryClient = useQueryClient();

  function handleOpenChat() {
    // On desktop, ensure the chat panel is open; on mobile, open the overlay
    if (window.innerWidth >= 1024) {
      setChatOpen(true);
    } else {
      setMobileChatOpen(true);
    }
  }

  useEffect(() => {
    setActiveTab("overview");
  }, [id, setActiveTab]);

  const caseQuery = useQuery({
    queryKey: ["case", id, firmId],
    queryFn: () => caseService.getCase(id!, firmId),
    enabled: !!id && !!firmId,
  });

  const caseData = caseQuery.data;

  if (caseQuery.isPending) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loading size="lg" text="Loading case..." />
      </div>
    );
  }

  if (caseQuery.isError || !caseData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center py-12">
          <p className="text-sm text-red-600 mb-4">Failed to load case details.</p>
          <Button variant="secondary" onClick={() => navigate(ROUTES.CASES)}>
            Back to Cases
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="shrink-0 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => navigate(ROUTES.CASES)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors shrink-0"
              aria-label="Back to cases"
            >
              <ArrowLeft size={18} />
            </button>
            <div className="min-w-0">
              <h1 className="text-base font-bold text-gray-900 truncate">
                {caseData.title}
              </h1>
              <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                <Badge variant={statusVariant[caseData.status]}>
                  {caseData.status.replace(/_/g, " ")}
                </Badge>
                <Badge variant="info">
                  {classifyPracticeArea(caseData.practice_area)}
                </Badge>
                {caseData.client_name && (
                  <span className="text-xs text-gray-500">{caseData.client_name}</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
            <button
              type="button"
              onClick={() => setChatOpen(!chatOpen)}
              className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors lg:block hidden"
              aria-label={chatOpen ? "Close chat panel" : "Open chat panel"}
            >
              {chatOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
            </button>
          </div>
        </div>

        {/* Stage bar */}
        <StageBar currentStage={caseData.stage} className="mt-3" />
      </div>

      {/* Split pane: tabs + chat */}
      <div className="flex flex-1 min-h-0">
        {/* Left: tabbed content */}
        <div className="flex-1 flex flex-col min-w-0">
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex flex-col flex-1 min-h-0">
            <Tabs.List className="flex border-b border-gray-200 px-4 sm:px-6 overflow-x-auto shrink-0 bg-white">
              <Tabs.Trigger value="overview" className={tabTriggerClass}>
                <Info size={14} />
                Overview
              </Tabs.Trigger>
              <Tabs.Trigger value="documents" className={tabTriggerClass}>
                <FileText size={14} />
                Documents
              </Tabs.Trigger>
              <Tabs.Trigger value="chronology" className={tabTriggerClass}>
                <Clock size={14} />
                Chronology
              </Tabs.Trigger>
              <Tabs.Trigger value="research" className={tabTriggerClass}>
                <Search size={14} />
                Research
              </Tabs.Trigger>
              <Tabs.Trigger value="drafts" className={tabTriggerClass}>
                <PenTool size={14} />
                Drafts
              </Tabs.Trigger>
              <Tabs.Trigger value="analysis" className={tabTriggerClass}>
                <BarChart3 size={14} />
                Analysis
              </Tabs.Trigger>
            </Tabs.List>

            <div className="flex-1 overflow-y-auto p-4 sm:p-6">
              <Tabs.Content value="overview">
                <OverviewTab caseData={caseData} />
              </Tabs.Content>
              <Tabs.Content value="documents">
                <DocumentsTab caseId={caseData.id} firmId={firmId} userId={userId} />
              </Tabs.Content>
              <Tabs.Content value="chronology">
                <ChronologyTab caseId={caseData.id} firmId={firmId} onGoToDocuments={() => setActiveTab("documents")} />
              </Tabs.Content>
              <Tabs.Content value="research">
                <ResearchTab caseId={caseData.id} firmId={firmId} onOpenChat={handleOpenChat} />
              </Tabs.Content>
              <Tabs.Content value="drafts">
                <DraftsTab caseId={caseData.id} firmId={firmId} caseData={caseData} />
              </Tabs.Content>
              <Tabs.Content value="analysis">
                <AnalysisTab caseData={caseData} onOpenChat={handleOpenChat} />
              </Tabs.Content>
            </div>
          </Tabs.Root>
        </div>

        {/* Right: chat panel */}
        {chatOpen && (
          <div className="hidden lg:flex w-[340px] shrink-0 border-l border-gray-200 bg-white flex-col">
            <ChatPanel key={caseData.id} caseId={caseData.id} firmId={firmId} />
          </div>
        )}
      </div>

      {/* Mobile chat overlay */}
      {mobileChatOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-white lg:hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
            <h3 className="text-sm font-semibold text-gray-900">Case Assistant</h3>
            <button
              type="button"
              onClick={() => setMobileChatOpen(false)}
              className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-200 transition-colors"
              aria-label="Close chat"
            >
              <ArrowLeft size={18} />
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <ChatPanel key={`mobile-${caseData.id}`} caseId={caseData.id} firmId={firmId} />
          </div>
        </div>
      )}

      {/* Mobile chat floating button */}
      <button
        type="button"
        onClick={() => setMobileChatOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center justify-center w-14 h-14 rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 transition-colors lg:hidden"
        aria-label="Open Case Assistant"
      >
        <MessageSquare size={22} />
      </button>

      <CaseForm
        open={editOpen}
        onOpenChange={setEditOpen}
        initialValues={caseData}
        onSubmit={() => {
          setEditOpen(false);
          queryClient.invalidateQueries({ queryKey: ["case", id, firmId] });
        }}
      />
    </div>
  );
}
