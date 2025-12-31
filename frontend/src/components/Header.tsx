import React from 'react';
import { Link } from 'react-router-dom';
import { User } from '../types';
import './Header.css';

interface HeaderProps {
  title: string;
  user: User | null;
  isAdmin: boolean;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, user, isAdmin, onLogout }) => {
  return (
    <header className="header">
      <h1>{title}</h1>
      <div className="user-info">
        <span className="username">{user?.username || 'Loading...'}</span>
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
