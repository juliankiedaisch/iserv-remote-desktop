import React from 'react';
import { Link } from 'react-router-dom';
import { User } from '../types';
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
        <span className="username">{user?.username || 'Loading...'}</span>
        {isTeacher && (
          <Link to="/teacher/assignments" className="teacher-icon" title="Manage Assignments">
            📚
          </Link>
        )}
        {isAdmin && (
          <Link to="/admin" className="admin-icon" title="Admin Panel">
            ⚙️
          </Link>
        )}
        <button className="btn btn-secondary" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
