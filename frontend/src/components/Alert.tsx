import React from 'react';
import './Alert.css';

interface AlertProps {
  type: 'error' | 'success' | 'warning' | 'info';
  message: string;
  onDismiss?: () => void;
}

export const Alert: React.FC<AlertProps> = ({ type, message, onDismiss }) => {
  return (
    <div className={`alert alert-${type}`}>
      <strong>{type.charAt(0).toUpperCase() + type.slice(1)}:</strong> {message}
      {onDismiss && (
        <button className="alert-dismiss" onClick={onDismiss}>
          ×
        </button>
      )}
    </div>
  );
};

export default Alert;
