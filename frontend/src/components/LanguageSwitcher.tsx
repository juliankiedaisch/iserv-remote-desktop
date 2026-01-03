import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './LanguageSwitcher.css';

interface Language {
  code: string;
  name: string;
  flag: string;
}

const languages: Language[] = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
];

export const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleLanguageChange = (langCode: string) => {
    i18n.changeLanguage(langCode);
    setIsOpen(false);
  };

  return (
    <div className="language-switcher-container" ref={menuRef}>
      <button 
        className="language-switcher-circle" 
        onClick={() => setIsOpen(!isOpen)}
        title={currentLanguage.name}
      >
        <span className="language-flag">{currentLanguage.flag}</span>
        <span className="language-code">{currentLanguage.code.toUpperCase()}</span>
      </button>
      
      {isOpen && (
        <div className="language-menu">
          {languages.map((lang) => (
            <button
              key={lang.code}
              className={`language-menu-item ${lang.code === i18n.language ? 'active' : ''}`}
              onClick={() => handleLanguageChange(lang.code)}
            >
              <span className="language-flag">{lang.flag}</span>
              <span className="language-name">{lang.name}</span>
              {lang.code === i18n.language && <span className="checkmark">✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default LanguageSwitcher;
