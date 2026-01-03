import React from 'react';
import { Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Loading, LanguageSwitcher } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import './Login.css';

export const Login: React.FC = () => {
  const { authenticated, loading, login, error } = useAuth();
  const { themeData } = useTheme();
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="login-container">
        <Loading message={t('common.checkingSession')} />
      </div>
    );
  }

  if (authenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="login-container">
      <div className="login-language-switcher">
        <LanguageSwitcher />
      </div>
      <div className="login-card">
        <div className="login-header">
          {themeData.app_icon ? (
            <img src={themeData.app_icon} alt={themeData.app_name} className="login-icon" />
          ) : (
            <span className="login-icon-emoji">🖥️</span>
          )}
          <h1>{themeData.app_name}</h1>
          <p>{t('auth.loginDescription')}</p>
        </div>

        {error && (
          <div className="login-error">
            {error}
          </div>
        )}

        <button className="btn btn-primary login-button" onClick={login}>
          {t('auth.loginWithIServ')}
        </button>

      </div>
    </div>
  );
};

export default Login;
