import React, { useEffect, useState } from 'react';
import './VersionFooter.css';

// Import version directly - will be bundled at build time
const FRONTEND_VERSION = process.env.REACT_APP_VERSION || '1.0.1';

const VersionFooter: React.FC = () => {
  const [backendVersion, setBackendVersion] = useState<string>('...');

  useEffect(() => {
    // Fetch backend version from API
    fetch('/api/version')
      .then(response => response.json())
      .then(data => {
        setBackendVersion(data.version || 'unknown');
      })
      .catch(() => {
        setBackendVersion('unknown');
      });
  }, []);

  return (
    <div className="version-footer">
      <span>Frontend: v{FRONTEND_VERSION}</span>
      <span className="version-separator">•</span>
      <span>Backend: v{backendVersion}</span>
    </div>
  );
};

export default VersionFooter;
