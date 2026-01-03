import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { User } from '../types';
import { LanguageSwitcher } from './LanguageSwitcher';
import './Header.css';

interface HeaderProps {
  title: string;
  user: User | null;
  isAdmin: boolean;
  isTeacher?: boolean;
  onLogout: () => void;
  appIcon?: string;
  appName?: string;
}

export const Header: React.FC<HeaderProps> = ({ 
  title, 
  user, 
  isAdmin, 
  isTeacher, 
  onLogout,
  appIcon,
  appName
}) => {
  const { t } = useTranslation();
  const displayTitle = appName || title;
  
  return (
    <header className="header">
      <div className="header-title">
        {appIcon ? (
          <img src={appIcon} alt={displayTitle} className="header-icon" />
        ) : (
          <span className="header-icon-emoji">🖥️</span>
        )}
        <h1>{displayTitle}</h1>
      </div>
      <div className="user-info">
        <span className="username">{user?.username || t('header.loading')}</span>
        <Link to="/" className="dashboard-icon" title={t('header.dashboard')}>
          🏠
        </Link>
        <Link to="/files" className="files-icon" title={t('header.fileManager')}>
          📁
        </Link>
        {isTeacher && (
          <Link to="/teacher/assignments" className="teacher-icon" title={t('header.manageAssignments')}>
            📚
          </Link>
        )}
        {isAdmin && (
          <Link to="/admin" className="admin-icon" title={t('header.adminPanel')}>
            ⚙️
          </Link>
        )}
        <LanguageSwitcher />
        <button className="btn btn-secondary" onClick={onLogout}>
          {t('common.logout')}
        </button>
      </div>
    </header>
  );
};

export default Header;
