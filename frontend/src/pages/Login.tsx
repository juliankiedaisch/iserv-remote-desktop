import React from 'react';
import { Navigate } from 'react-router-dom';
import { Loading } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import './Login.css';

export const Login: React.FC = () => {
  const { authenticated, loading, login, error } = useAuth();
  const { themeData } = useTheme();

  if (loading) {
    return (
      <div className="login-container">
        <Loading message="Checking session..." />
      </div>
    );
  }

  if (authenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          {themeData.app_icon ? (
            <img src={themeData.app_icon} alt={themeData.app_name} className="login-icon" />
          ) : (
            <span className="login-icon-emoji">🖥️</span>
          )}
          <h1>{themeData.app_name}</h1>
          <p>Login mit IServ, um auf Ihre Remote-Desktops zuzugreifen</p>
        </div>

        {error && (
          <div className="login-error">
            {error}
          </div>
        )}

        <button className="btn btn-primary login-button" onClick={login}>
          Login mit IServ
        </button>

      </div>
    </div>
  );
};

export default Login;
