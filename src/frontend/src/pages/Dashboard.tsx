import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Briefcase,
  FileText,
  MessageSquare,
  Plus,
  ArrowRight,
  Clock,
} from "lucide-react";
import * as caseService from "@/services/case.service";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES, CASE_STAGES } from "@/utils/constants";
import { formatDate, classifyPracticeArea } from "@/utils/helpers";
import Badge from "@/components/common/Badge";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import Loading from "@/components/common/Loading";

export default function Dashboard() {
  const user = useAuthStore((state) => state.user);
  const firmId = user?.firm_id ?? "";

  const casesQuery = useQuery({
    queryKey: ["cases", firmId],
    queryFn: () => caseService.listCases(firmId, undefined, undefined, 200),
    enabled: !!firmId,
  });

  const cases = casesQuery.data?.items ?? [];
  const activeCases = cases.filter(
    (c) => c.status !== "closed" && c.status !== "archived",
  );
  const recentCases = [...cases]
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
    .slice(0, 5);

  if (casesQuery.isPending) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loading size="lg" text="Loading dashboard..." />
      </div>
    );
  }

  if (casesQuery.isError) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <p className="text-sm text-red-600 py-8 text-center">
          Failed to load dashboard data. Please refresh the page.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">
          Welcome back{user?.name ? `, ${user.name}` : ""}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Here's an overview of your legal practice
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3 mb-8">
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50">
              <Briefcase size={20} className="text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{cases.length}</p>
              <p className="text-xs text-gray-500">Total Cases</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-green-50">
              <Clock size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {activeCases.length}
              </p>
              <p className="text-xs text-gray-500">Active Cases</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-purple-50">
              <MessageSquare size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {
                  activeCases.filter((c) => c.stage !== "intake").length
                }
              </p>
              <p className="text-xs text-gray-500">In Progress</p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Cases + Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">
              Recent Cases
            </h2>
            <Link
              to={ROUTES.CASES}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
            >
              View all <ArrowRight size={14} />
            </Link>
          </div>

          {recentCases.length === 0 ? (
            <Card>
              <p className="text-sm text-gray-500 text-center py-4">
                No cases yet. Create your first case to get started.
              </p>
            </Card>
          ) : (
            <div className="space-y-2">
              {recentCases.map((c) => (
                <Link
                  key={c.id}
                  to={`/cases/${c.id}`}
                  className="flex items-center justify-between gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 hover:border-blue-200 hover:shadow-sm transition-all"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {c.title}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {c.client_name ? `${c.client_name} · ` : ""}
                      {classifyPracticeArea(c.practice_area)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="info">
                      {CASE_STAGES.find((s) => s.value === c.stage)?.label ??
                        c.stage}
                    </Badge>
                    <span className="text-xs text-gray-400">
                      {formatDate(c.updated_at)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-4">
            Quick Actions
          </h2>
          <div className="space-y-3">
            <Link to={ROUTES.CASES}>
              <Button
                variant="primary"
                size="md"
                className="w-full justify-start"
              >
                <Plus size={16} />
                New Case
              </Button>
            </Link>
            <Link to={ROUTES.KNOWLEDGE}>
              <Button
                variant="secondary"
                size="md"
                className="w-full justify-start"
              >
                <FileText size={16} />
                Browse Documents
              </Button>
            </Link>
          </div>

          {cases.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">
                Case Stages
              </h3>
              <div className="space-y-2">
                {CASE_STAGES.map((stage) => {
                  const count = cases.filter(
                    (c) => c.stage === stage.value,
                  ).length;
                  if (count === 0) return null;
                  return (
                    <div
                      key={stage.value}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-gray-600">{stage.label}</span>
                      <span className="font-medium text-gray-900">
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
