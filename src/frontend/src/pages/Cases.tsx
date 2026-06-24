import { useNavigate } from "react-router-dom";
import type { Case } from "@/types/case";
import CaseList from "@/components/cases/CaseList";

export default function Cases() {
  const navigate = useNavigate();

  function handleSelectCase(caseItem: Case) {
    navigate(`/cases/${caseItem.id}`);
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <CaseList onSelectCase={handleSelectCase} />
    </div>
  );
}
