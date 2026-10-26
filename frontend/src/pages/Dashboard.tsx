import React from "react";
import { User } from "../types";
import { CreatorDashboard } from "../components/dashboards/CreatorDashboard";
import { ManagerDashboard } from "../components/dashboards/ManagerDashboard";
import { ReviewerDashboard } from "../components/dashboards/ReviewerDashboard";
import { AdminDashboard } from "../components/dashboards/AdminDashboard";

interface DashboardProps {
  user: User;
  navigate: (path: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ user, navigate }) => {
  switch (user.role) {
    case "creator":
      return <CreatorDashboard user={user} navigate={navigate} />;
    case "manager":
      return <ManagerDashboard user={user} navigate={navigate} />;
    case "reviewer":
      return <ReviewerDashboard user={user} navigate={navigate} />;
    case "admin":
      return <AdminDashboard user={user} navigate={navigate} />;
    default:
      return <CreatorDashboard user={user} navigate={navigate} />;
  }
};
