import React from 'react';
import { useTranslation } from 'react-i18next';
import './LanguageSwitcher.css';

export const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'de' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <button 
      className="language-switcher" 
      onClick={toggleLanguage}
      title={i18n.language === 'en' ? 'Switch to German' : 'Zu Englisch wechseln'}
    >
      {i18n.language === 'en' ? '🇩🇪 DE' : '🇬🇧 EN'}
    </button>
  );
};

export default LanguageSwitcher;
