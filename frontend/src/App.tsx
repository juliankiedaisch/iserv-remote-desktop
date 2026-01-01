import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Dashboard, AdminPanel, Login, ThemeEditor, DesktopTypesManager } from './pages';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { Loading } from './components';
import './App.css';

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { authenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="App">
        <Loading message="Loading..." />
      </div>
    );
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

function App() {
  // Load theme on app start
  useTheme();
  
  return (
    <Router>
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
            path="/admin/theme"
            element={
              <ProtectedRoute>
                <ThemeEditor />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
