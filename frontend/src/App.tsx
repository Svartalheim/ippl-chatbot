import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AdminLayout } from "./layouts/AdminLayout";
import { AuditorLayout } from "./layouts/AuditorLayout";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { AdminDocumentsPage } from "./pages/admin/AdminDocumentsPage";
import { AdminRolesPage } from "./pages/admin/AdminRolesPage";
import { AuditorLogsPage } from "./pages/auditor/AuditorLogsPage";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";

const ProtectedRoute: React.FC<{
  children: React.ReactNode;
  requiredRole?: "Admin" | "Auditor";
}> = ({ children, requiredRole }) => {
  const { isAuthenticated, isLoading, canManageDocs, canViewAudit } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#10100F] text-white">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500 mb-3"></div>
        <span className="text-xs text-gray-400">Memeriksa sesi autentikasi...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole === "Admin" && !canManageDocs) {
    return <Navigate to="/" replace />;
  }

  if (requiredRole === "Auditor" && !canViewAudit) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRole="Admin">
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AdminDashboardPage />} />
            <Route path="documents" element={<AdminDocumentsPage />} />
            <Route path="roles" element={<AdminRolesPage />} />
          </Route>
          <Route
            path="/auditor"
            element={
              <ProtectedRoute requiredRole="Auditor">
                <AuditorLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AuditorLogsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};
