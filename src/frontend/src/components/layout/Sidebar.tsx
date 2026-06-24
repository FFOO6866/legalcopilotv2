import { NavLink, useNavigate } from "react-router-dom";
import {
  Scale,
  LayoutDashboard,
  Briefcase,
  BookOpen,
  LogOut,
  X,
} from "lucide-react";
import clsx from "clsx";
import { ROUTES, APP_NAME } from "@/utils/constants";
import { useAuthStore } from "@/stores/authStore";
import { getInitials } from "@/utils/helpers";
import Badge from "@/components/common/Badge";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navigation = [
  { name: "Dashboard", href: ROUTES.DASHBOARD, icon: LayoutDashboard },
  { name: "Cases", href: ROUTES.CASES, icon: Briefcase },
  { name: "Knowledge Base", href: ROUTES.KNOWLEDGE, icon: BookOpen },
] as const;

const roleLabelMap: Record<string, string> = {
  partner: "Partner",
  senior_associate: "Senior Associate",
  associate: "Associate",
  paralegal: "Paralegal",
  admin: "Admin",
  viewer: "Viewer",
};

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
  }

  function handleNavClick() {
    onClose();
  }

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-slate-900",
          "transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:z-auto",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-3 px-6 py-5 border-b border-slate-800">
          <button
            type="button"
            onClick={() => navigate(ROUTES.DASHBOARD)}
            className="flex items-center gap-3 min-w-0"
          >
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600">
              <Scale size={18} className="text-white" />
            </div>
            <span className="text-lg font-semibold text-white truncate">
              {APP_NAME}
            </span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="lg:hidden text-slate-400 hover:text-white p-1 rounded-md"
            aria-label="Close sidebar"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              onClick={handleNavClick}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150",
                  isActive
                    ? "bg-blue-600/20 text-blue-400"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white",
                )
              }
            >
              <item.icon size={20} className="shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>

        {user && (
          <div className="border-t border-slate-800 px-4 py-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-full bg-slate-700 text-sm font-medium text-white shrink-0">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name}
                    className="w-9 h-9 rounded-full object-cover"
                  />
                ) : (
                  getInitials(user.name)
                )}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {user.name}
                </p>
                <Badge variant="info" className="mt-0.5">
                  {roleLabelMap[user.role] ?? user.role}
                </Badge>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-white transition-colors duration-150"
            >
              <LogOut size={16} />
              <span>Log out</span>
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
