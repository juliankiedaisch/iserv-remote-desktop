import React, { useState, useEffect } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { Alert, Loading } from '../components';
import './ThemeEditor.css';

interface ThemeSettings {
  [key: string]: string;
}

export const ThemeEditor: React.FC = () => {
  const { user, isAdmin, logout, loading: authLoading } = useAuth();
  const [theme, setTheme] = useState<ThemeSettings>({});
  const [originalTheme, setOriginalTheme] = useState<ThemeSettings>({});
  const [favicon, setFavicon] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const colorFields = [
    { key: 'color-primary', label: 'Primary Color', description: 'Main brand color' },
    { key: 'color-primary-dark', label: 'Primary Dark', description: 'Darker shade of primary' },
    { key: 'color-primary-gradient-start', label: 'Gradient Start', description: 'Start of primary gradient' },
    { key: 'color-primary-gradient-end', label: 'Gradient End', description: 'End of primary gradient' },
    { key: 'color-secondary', label: 'Secondary Color', description: 'Secondary actions' },
    { key: 'color-secondary-dark', label: 'Secondary Dark', description: 'Darker secondary' },
    { key: 'color-success', label: 'Success Color', description: 'Success states' },
    { key: 'color-danger', label: 'Danger Color', description: 'Error/danger states' },
    { key: 'color-danger-hover', label: 'Danger Hover', description: 'Danger button hover' },
    { key: 'color-warning', label: 'Warning Color', description: 'Warning states' },
    { key: 'color-info', label: 'Info Color', description: 'Info states' },
    { key: 'color-gray', label: 'Gray', description: 'Neutral gray' },
    { key: 'color-gray-dark', label: 'Gray Dark', description: 'Darker gray' },
    { key: 'color-admin-badge', label: 'Admin Badge', description: 'Admin badge color' },
    { key: 'color-admin-button', label: 'Admin Button', description: 'Admin button color' },
    { key: 'color-admin-button-hover', label: 'Admin Button Hover', description: 'Admin button hover' },
  ];

  useEffect(() => {
    loadTheme();
  }, []);

  const loadTheme = async () => {
    try {
      setLoading(true);
      const response = await apiService.getTheme();
      if (response.success && response.theme) {
        const settings = response.theme.settings || {};
        setTheme(settings);
        setOriginalTheme(settings);
        setFavicon(response.theme.favicon);
      } else {
        setError('Failed to load theme');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load theme');
    } finally {
      setLoading(false);
    }
  };

  const handleColorChange = (key: string, value: string) => {
    setTheme(prev => ({ ...prev, [key]: value }));
    // Apply the color change immediately for live preview
    document.documentElement.style.setProperty(`--${key}`, value);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      const response = await apiService.updateTheme(theme, favicon || undefined);
      if (response.success) {
        setOriginalTheme(theme);
        setSuccessMessage('Theme saved successfully!');
        // Apply all colors
        Object.keys(theme).forEach(key => {
          document.documentElement.style.setProperty(`--${key}`, theme[key]);
        });
      } else {
        setError(response.error || 'Failed to save theme');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to save theme');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset theme to default? This will discard all your changes.')) {
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const response = await apiService.resetTheme();
      if (response.success && response.theme) {
        const settings = response.theme.settings || {};
        setTheme(settings);
        setOriginalTheme(settings);
        setFavicon(response.theme.favicon);
        setSuccessMessage('Theme reset to defaults!');
        // Apply default colors
        Object.keys(settings).forEach(key => {
          document.documentElement.style.setProperty(`--${key}`, settings[key]);
        });
        if (response.theme.favicon) {
          updateFaviconInDOM(response.theme.favicon);
        } else {
          updateFaviconInDOM('/favicon.ico');
        }
      } else {
        setError(response.error || 'Failed to reset theme');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to reset theme');
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await apiService.exportTheme();
      if (response.success) {
        const dataStr = JSON.stringify(response.theme, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'theme-export.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        setSuccessMessage('Theme exported successfully!');
      } else {
        setError(response.error || 'Failed to export theme');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to export theme');
    }
  };

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;
        const themeData = JSON.parse(content);
        
        const response = await apiService.importTheme(themeData);
        if (response.success && response.theme) {
          const settings = response.theme.settings || {};
          setTheme(settings);
          setOriginalTheme(settings);
          if (response.theme.favicon) {
            setFavicon(response.theme.favicon);
            updateFaviconInDOM(response.theme.favicon);
          }
          setSuccessMessage('Theme imported successfully!');
          // Apply imported colors
          Object.keys(settings).forEach(key => {
            document.documentElement.style.setProperty(`--${key}`, settings[key]);
          });
        } else {
          setError(response.error || 'Failed to import theme');
        }
      } catch (err: any) {
        setError('Invalid theme file format');
      }
    };
    reader.readAsText(file);
    // Reset the input so the same file can be imported again
    event.target.value = '';
  };

  const handleFaviconUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please upload an image file');
      return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const base64 = e.target?.result as string;
        setFavicon(base64);
        updateFaviconInDOM(base64);
        setSuccessMessage('Favicon updated! Remember to save your changes.');
      } catch (err: any) {
        setError('Failed to upload favicon');
      }
    };
    reader.readAsDataURL(file);
    event.target.value = '';
  };

  const updateFaviconInDOM = (faviconData: string) => {
    let link = document.querySelector("link[rel*='icon']") as HTMLLinkElement;
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.getElementsByTagName('head')[0].appendChild(link);
    }
    link.href = faviconData;
  };

  if (authLoading || loading) {
    return (
      <div className="container">
        <Loading message="Loading theme settings..." />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🎨 Theme Settings</h1>
        <div className="user-info">
          <span className="username">{user?.username} (Admin)</span>
          <Link to="/admin" className="btn btn-secondary">
            ← Back to Admin
          </Link>
          <Link to="/" className="btn btn-secondary">
            🏠 Desktops
          </Link>
          <button className="btn btn-secondary" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <div className="theme-editor">
      <div className="theme-editor-header">
        <h2>🎨 Theme Customization</h2>
        <p>Customize the look and feel of your application</p>
      </div>

      {error && <Alert type="error" message={error} onDismiss={() => setError(null)} />}
      {successMessage && (
        <Alert type="success" message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className="theme-editor-actions">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          💾 Save Theme
        </button>
        <button className="btn btn-secondary" onClick={handleExport}>
          📥 Export Theme
        </button>
        <label className="btn btn-secondary file-upload-btn">
          📤 Import Theme
          <input
            type="file"
            accept=".json"
            onChange={handleImport}
            style={{ display: 'none' }}
          />
        </label>
        <button className="btn btn-danger" onClick={handleReset} disabled={saving}>
          🔄 Reset to Default
        </button>
      </div>

      <div className="theme-section">
        <h3>Favicon</h3>
        <div className="favicon-upload">
          <div className="favicon-preview">
            {favicon ? (
              <img src={favicon} alt="Favicon preview" />
            ) : (
              <div className="favicon-placeholder">No custom favicon</div>
            )}
          </div>
          <label className="btn btn-primary file-upload-btn">
            Upload Favicon
            <input
              type="file"
              accept="image/*"
              onChange={handleFaviconUpload}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </div>

      <div className="theme-section">
        <h3>Color Palette</h3>
        <div className="color-grid">
          {colorFields.map(field => (
            <div key={field.key} className="color-field">
              <label>
                <span className="color-field-label">{field.label}</span>
                <span className="color-field-description">{field.description}</span>
              </label>
              <div className="color-input-group">
                <input
                  type="color"
                  value={theme[field.key] || '#000000'}
                  onChange={(e) => handleColorChange(field.key, e.target.value)}
                  className="color-picker"
                />
                <input
                  type="text"
                  value={theme[field.key] || ''}
                  onChange={(e) => handleColorChange(field.key, e.target.value)}
                  className="color-text-input"
                  placeholder="#000000"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {saving && (
        <div className="loading-overlay">
          <div className="loading-content">
            <Loading message="Saving theme..." />
          </div>
        </div>
      )}
    </div>
  );
};

export default ThemeEditor;
