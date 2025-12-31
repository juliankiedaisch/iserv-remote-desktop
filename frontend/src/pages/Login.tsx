import React from 'react';
import { Navigate } from 'react-router-dom';
import { Loading } from '../components';
import { useAuth } from '../hooks/useAuth';
import './Login.css';

export const Login: React.FC = () => {
  const { authenticated, loading, login, error } = useAuth();

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
          <h1>🖥️ Remote Desktop</h1>
          <p>Sign in to access your remote desktops</p>
        </div>

        {error && (
          <div className="login-error">
            {error}
          </div>
        )}

        <button className="btn btn-primary login-button" onClick={login}>
          Sign in with IServ
        </button>

        <div className="login-footer">
          <p>Secure OAuth authentication</p>
        </div>
      </div>
    </div>
  );
};

export default Login;
