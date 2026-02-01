import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Dashboard, AdminPanel, Login, ThemeEditor, DesktopTypesManager, AssignmentManager, FileManager, UserManagement } from './pages';
import Viewer from './pages/Viewer';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { Loading, LanguageSwitcher, VersionFooter } from './components';
import './App.css';

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { authenticated, loading } = useAuth();
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="App">
        <Loading message={t('common.loading')} />
      </div>
    );
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

const AppContent: React.FC = () => {
  const location = useLocation();
  const isViewerPage = location.pathname.startsWith('/viewer/');

  return (
    <div className="App">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/desktop-types"
          element={
            <ProtectedRoute>
              <DesktopTypesManager />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute>
              <UserManagement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/assignments"
          element={
            <ProtectedRoute>
              <AssignmentManager />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/theme"
          element={
            <ProtectedRoute>
              <ThemeEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/files"
          element={
            <ProtectedRoute>
              <FileManager />
            </ProtectedRoute>
          }
        />
        <Route
          path="/viewer/:proxyPath"
          element={
            <ProtectedRoute>
              <Viewer />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {!isViewerPage && <LanguageSwitcher />}
      {!isViewerPage && <VersionFooter />}
    </div>
  );
};

function App() {
  // Load theme on app start
  useTheme();
  
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
