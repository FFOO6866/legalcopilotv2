import { useNavigate } from "react-router-dom";
import { FileQuestion } from "lucide-react";
import { ROUTES } from "@/utils/constants";
import Button from "@/components/common/Button";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-4 bg-gray-50">
      <div className="flex items-center justify-center w-20 h-20 rounded-full bg-gray-100 mb-6">
        <FileQuestion size={36} className="text-gray-400" />
      </div>
      <h1 className="text-6xl font-bold text-gray-900 mb-2">404</h1>
      <p className="text-lg text-gray-600 mb-1">Page not found</p>
      <p className="text-sm text-gray-500 mb-8 text-center max-w-sm">
        The page you are looking for does not exist or has been moved.
      </p>
      <Button
        variant="primary"
        size="lg"
        onClick={() => navigate(ROUTES.DASHBOARD, { replace: true })}
      >
        Go to Dashboard
      </Button>
    </div>
  );
}
