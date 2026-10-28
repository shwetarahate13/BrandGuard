import React from "react";

export const Skeleton: React.FC<{ className?: string }> = ({ className = "h-4 w-full" }) => (
  <div aria-hidden="true" className={`ui-skeleton animate-pulse ${className}`} />
);

export const DashboardSkeleton: React.FC = () => (
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
    <div className="flex justify-between items-center">
      <div className="space-y-2">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <Skeleton className="h-10 w-32 rounded-lg" />
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-3 w-36" />
        </div>
      ))}
    </div>
    <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-4">
      <Skeleton className="h-5 w-48" />
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-12 w-full rounded-xl" />
        ))}
      </div>
    </div>
  </div>
);
