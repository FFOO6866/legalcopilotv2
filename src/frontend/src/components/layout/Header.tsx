import { useLocation, useNavigate } from "react-router-dom";
import { Bell, Menu, User as UserIcon, LogOut } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ROUTES } from "@/utils/constants";
import { useAuthStore } from "@/stores/authStore";
import { getInitials } from "@/utils/helpers";

interface HeaderProps {
  onMenuClick: () => void;
}

const pageTitles: Record<string, string> = {
  [ROUTES.DASHBOARD]: "Dashboard",
  [ROUTES.CASES]: "Cases",
  [ROUTES.KNOWLEDGE]: "Knowledge Base",
  [ROUTES.PROFILE]: "Profile",
};

function getPageTitle(pathname: string): string {
  // Case detail pages get their own title
  if (/^\/cases\/[^/]+/.test(pathname)) {
    return "Case Workspace";
  }
  for (const [route, title] of Object.entries(pageTitles)) {
    if (pathname === route) {
      return title;
    }
  }
  return "Legal CoPilot";
}

export default function Header({ onMenuClick }: HeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const pageTitle = getPageTitle(location.pathname);

  function handleLogout() {
    logout();
  }

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-gray-200 bg-white px-6 py-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="lg:hidden p-2 -ml-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-lg font-semibold text-gray-900">{pageTitle}</h1>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="relative p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
          aria-label="Notifications"
        >
          <Bell size={20} />
        </button>

        {user && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                aria-label="User menu"
              >
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-xs font-medium text-white">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.name}
                      className="w-8 h-8 rounded-full object-cover"
                    />
                  ) : (
                    getInitials(user.name)
                  )}
                </div>
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="min-w-[200px] rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg animate-in fade-in-0 zoom-in-95"
                sideOffset={8}
                align="end"
              >
                <div className="px-3 py-2 border-b border-gray-100 mb-1">
                  <p className="text-sm font-medium text-gray-900">{user.name}</p>
                  <p className="text-xs text-gray-500">{user.email}</p>
                </div>

                <DropdownMenu.Item
                  className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg cursor-pointer outline-none hover:bg-gray-50 focus:bg-gray-50"
                  onSelect={() => navigate(ROUTES.PROFILE)}
                >
                  <UserIcon size={16} />
                  Profile
                </DropdownMenu.Item>

                <DropdownMenu.Separator className="my-1 h-px bg-gray-100" />

                <DropdownMenu.Item
                  className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 rounded-lg cursor-pointer outline-none hover:bg-red-50 focus:bg-red-50"
                  onSelect={handleLogout}
                >
                  <LogOut size={16} />
                  Log out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
      </div>
    </header>
  );
}
