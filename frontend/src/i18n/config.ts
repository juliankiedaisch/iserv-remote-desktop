import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import de from './de.json';

// Get language from localStorage or browser settings
const getInitialLanguage = (): string => {
  // Check localStorage first
  const savedLanguage = localStorage.getItem('language');
  if (savedLanguage && (savedLanguage === 'en' || savedLanguage === 'de')) {
    return savedLanguage;
  }

  // Check browser language
  const browserLanguage = navigator.language.toLowerCase();
  if (browserLanguage.startsWith('de')) {
    return 'de';
  }

  // Default to English
  return 'en';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: en
      },
      de: {
        translation: de
      }
    },
    lng: getInitialLanguage(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false // React already escapes values
    }
  });

// Save language preference when it changes
i18n.on('languageChanged', (lng) => {
  localStorage.setItem('language', lng);
});

export default i18n;
