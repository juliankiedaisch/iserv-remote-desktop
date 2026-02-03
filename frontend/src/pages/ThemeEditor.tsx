import React, { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { Alert, Loading } from '../components';
import './ThemeEditor.css';

interface ThemeSettings {
  [key: string]: string;
}

export const ThemeEditor: React.FC = () => {
  const { user, isAdmin, loading: authLoading } = useAuth();
  const { t } = useTranslation();
  const [theme, setTheme] = useState<ThemeSettings>({});
  const [favicon, setFavicon] = useState<string | null>(null);
  const [appName, setAppName] = useState<string>('MDG Remote Desktop');
  const [appIcon, setAppIcon] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showResetModal, setShowResetModal] = useState(false);

  const colorFields = [
    { key: 'color-primary', label: t('theme.colorPrimary'), description: t('theme.colorPrimaryDesc') },
    { key: 'color-primary-dark', label: t('theme.colorPrimaryDark'), description: t('theme.colorPrimaryDarkDesc') },
    { key: 'color-primary-gradient-start', label: t('theme.colorGradientStart'), description: t('theme.colorGradientStartDesc') },
    { key: 'color-primary-gradient-end', label: t('theme.colorGradientEnd'), description: t('theme.colorGradientEndDesc') },
    { key: 'color-secondary', label: t('theme.colorSecondary'), description: t('theme.colorSecondaryDesc') },
    { key: 'color-secondary-dark', label: t('theme.colorSecondaryDark'), description: t('theme.colorSecondaryDarkDesc') },
    { key: 'color-success', label: t('theme.colorSuccess'), description: t('theme.colorSuccessDesc') },
    { key: 'color-danger', label: t('theme.colorDanger'), description: t('theme.colorDangerDesc') },
    { key: 'color-danger-hover', label: t('theme.colorDangerHover'), description: t('theme.colorDangerHoverDesc') },
    { key: 'color-warning', label: t('theme.colorWarning'), description: t('theme.colorWarningDesc') },
    { key: 'color-info', label: t('theme.colorInfo'), description: t('theme.colorInfoDesc') },
    { key: 'color-gray', label: t('theme.colorGray'), description: t('theme.colorGrayDesc') },
    { key: 'color-gray-dark', label: t('theme.colorGrayDark'), description: t('theme.colorGrayDarkDesc') },
    { key: 'color-admin-badge', label: t('theme.colorAdminBadge'), description: t('theme.colorAdminBadgeDesc') },
    { key: 'color-admin-button', label: t('theme.colorAdminButton'), description: t('theme.colorAdminButtonDesc') },
    { key: 'color-admin-button-hover', label: t('theme.colorAdminButtonHover'), description: t('theme.colorAdminButtonHoverDesc') },
  ];

  const loadTheme = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiService.getTheme();
      if (response.success && response.theme) {
        const settings = response.theme.settings || {};
        setTheme(settings);
        setFavicon(response.theme.favicon);
        setAppName(response.theme.app_name || 'MDG Remote Desktop');
        setAppIcon(response.theme.app_icon);
      } else {
        setError(t('theme.failedToLoadTheme'));
      }
    } catch (err: any) {
      setError(err.message || t('theme.failedToLoadTheme'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadTheme();
  }, [loadTheme]);

  const handleColorChange = (key: string, value: string) => {
    setTheme(prev => ({ ...prev, [key]: value }));
    // Apply the color change immediately for live preview
    document.documentElement.style.setProperty(`--${key}`, value);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      const response = await apiService.updateTheme(theme, favicon || undefined, appName, appIcon || undefined);
      if (response.success) {
        setSuccessMessage(t('theme.themeSaved'));
        // Apply all colors
        Object.keys(theme).forEach(key => {
          document.documentElement.style.setProperty(`--${key}`, theme[key]);
        });
      } else {
        setError(response.error || t('theme.failedToSaveTheme'));
      }
    } catch (err: any) {
      setError(err.message || t('theme.failedToSaveTheme'));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setShowResetModal(true);
  };

  const confirmReset = async () => {
    setShowResetModal(false);

    try {
      setSaving(true);
      setError(null);
      const response = await apiService.resetTheme();
      if (response.success && response.theme) {
        const settings = response.theme.settings || {};
        setTheme(settings);
        setFavicon(response.theme.favicon);
        setAppName(response.theme.app_name || 'MDG Remote Desktop');
        setAppIcon(response.theme.app_icon);
        setSuccessMessage(t('theme.themeReset'));
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
        setError(response.error || t('theme.failedToResetTheme'));
      }
    } catch (err: any) {
      setError(err.message || t('theme.failedToResetTheme'));
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
        setSuccessMessage(t('theme.themeExported'));
      } else {
        setError(response.error || t('theme.failedToExportTheme'));
      }
    } catch (err: any) {
      setError(err.message || t('theme.failedToExportTheme'));
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
          if (response.theme.favicon) {
            setFavicon(response.theme.favicon);
            updateFaviconInDOM(response.theme.favicon);
          }
          setAppName(response.theme.app_name || 'MDG Remote Desktop');
          setAppIcon(response.theme.app_icon);
          setSuccessMessage(t('theme.themeImported'));
          // Apply imported colors
          Object.keys(settings).forEach(key => {
            document.documentElement.style.setProperty(`--${key}`, settings[key]);
          });
        } else {
          setError(response.error || t('theme.failedToSaveTheme'));
        }
      } catch (err: any) {
        setError(t('theme.invalidThemeFile'));
      } finally {
        // Reset the input so the same file can be imported again
        event.target.value = '';
      }
    };
    reader.readAsText(file);
  };

  const handleFaviconUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type by extension and MIME type
    const validExtensions = ['png', 'jpg', 'jpeg', 'ico', 'gif', 'svg'];
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    
    if (!file.type.startsWith('image/') || !validExtensions.includes(fileExtension || '')) {
      setError(t('theme.faviconInvalidType'));
      event.target.value = '';
      return;
    }

    // Check file size (max 1MB)
    if (file.size > 1048576) {
      setError(t('theme.faviconTooLarge'));
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const base64 = e.target?.result as string;
        setFavicon(base64);
        updateFaviconInDOM(base64);
        setSuccessMessage(t('theme.faviconUpdated'));
      } catch (err: any) {
        setError(t('theme.failedToSaveTheme'));
      } finally {
        event.target.value = '';
      }
    };
    reader.readAsDataURL(file);
  };

  const handleAppIconUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type by extension and MIME type
    const validExtensions = ['png', 'jpg', 'jpeg', 'gif', 'svg'];
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    
    if (!file.type.startsWith('image/') || !validExtensions.includes(fileExtension || '')) {
      setError(t('theme.appIconInvalidType'));
      event.target.value = '';
      return;
    }

    // Check file size (max 2MB)
    if (file.size > 2097152) {
      setError(t('theme.appIconTooLarge'));
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const base64 = e.target?.result as string;
        setAppIcon(base64);
        setSuccessMessage(t('theme.appIconUpdated'));
      } catch (err: any) {
        setError(t('theme.failedToSaveTheme'));
      } finally {
        event.target.value = '';
      }
    };
    reader.readAsDataURL(file);
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
        <Loading message={t('theme.loading')} />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🎨 {t('theme.title')}</h1>
        <div className="user-info">
          <span className="username">{user?.username} ({t('admin.admin')})</span>
          <Link to="/admin" className="btn btn-secondary">
            {t('theme.backToAdmin')}
          </Link>
        </div>
      </header>

      <div className="theme-editor">
      <div className="theme-editor-header">
        <h2>🎨 {t('theme.customization')}</h2>
        <p>{t('theme.customizationDesc')}</p>
      </div>

      {error && <Alert type="error" message={error} onDismiss={() => setError(null)} />}
      {successMessage && (
        <Alert type="success" message={successMessage} onDismiss={() => setSuccessMessage(null)} />
      )}

      <div className="theme-editor-actions">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {t('theme.saveTheme')}
        </button>
        <button className="btn btn-secondary" onClick={handleExport}>
          {t('theme.exportTheme')}
        </button>
        <label className="btn btn-secondary file-upload-btn">
          {t('theme.importTheme')}
          <input
            type="file"
            accept=".json"
            onChange={handleImport}
            style={{ display: 'none' }}
          />
        </label>
        <button className="btn btn-danger" onClick={handleReset} disabled={saving}>
          {t('theme.resetToDefault')}
        </button>
      </div>

      <div className="theme-section">
        <h3>{t('theme.favicon')}</h3>
        <div className="favicon-upload">
          <div className="favicon-preview">
            {favicon ? (
              <img src={favicon} alt={t('theme.faviconPreview')} />
            ) : (
              <div className="favicon-placeholder">{t('theme.noCustomFavicon')}</div>
            )}
          </div>
          <label className="btn btn-primary file-upload-btn">
            {t('theme.faviconUpload')}
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
        <h3>{t('theme.appBranding')}</h3>
        <div className="branding-section">
          <div className="form-group">
            <label htmlFor="app-name">{t('theme.appName')}</label>
            <input
              id="app-name"
              type="text"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              className="form-input"
              placeholder={t('theme.appNamePlaceholder')}
              maxLength={255}
            />
            <p className="form-help">{t('theme.appNameHelp')}</p>
          </div>
          
          <div className="form-group">
            <label>{t('theme.appIcon')}</label>
            <div className="icon-upload">
              <div className="icon-preview">
                {appIcon ? (
                  <img src={appIcon} alt={t('theme.appIconPreview')} />
                ) : (
                  <div className="icon-placeholder">{t('theme.appIconPlaceholder')}</div>
                )}
              </div>
              <div>
                <label className="btn btn-primary file-upload-btn">
                  {t('theme.appIconUpload')}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleAppIconUpload}
                    style={{ display: 'none' }}
                  />
                </label>
                {appIcon && (
                  <button 
                    className="btn btn-secondary"
                    onClick={() => setAppIcon(null)}
                    style={{ marginLeft: '10px' }}
                  >
                    {t('theme.removeIcon')}
                  </button>
                )}
                <p className="form-help">{t('theme.appIconHelp')}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="theme-section">
        <h3>{t('theme.colorPalette')}</h3>
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
            <Loading message={t('theme.saving')} />
          </div>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {showResetModal && (
        <div className="modal-overlay" onClick={() => setShowResetModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{t('theme.resetTitle')}</h2>
            <p>{t('theme.resetConfirmation')}</p>
            <div className="modal-actions">
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={() => setShowResetModal(false)}
              >
                {t('common.cancel')}
              </button>
              <button 
                type="button" 
                className="btn btn-danger" 
                onClick={confirmReset}
              >
                {t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default ThemeEditor;
