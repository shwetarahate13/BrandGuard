import React from "react";
import { Loader2 } from "lucide-react";

interface ColdStartBannerProps {
  isWaking: boolean;
}

export const ColdStartBanner: React.FC<ColdStartBannerProps> = ({ isWaking }) => {
  if (!isWaking) return null;

  return (
    <div className="bg-amber-500 text-stone-950 px-4 py-2 text-sm font-medium flex items-center justify-center gap-2 shadow-sm animate-pulse z-50">
      <Loader2 className="w-4 h-4 animate-spin text-stone-950" />
      <span>
        Waking up the server instance on Render free tier. This can take up to 45 seconds on cold start...
      </span>
    </div>
  );
};
