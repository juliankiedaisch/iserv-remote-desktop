import { useEffect, useState } from 'react';
import { apiService } from '../services/api';

export const useTheme = () => {
  const [themeLoaded, setThemeLoaded] = useState(false);

  useEffect(() => {
    const loadAndApplyTheme = async () => {
      try {
        const response = await apiService.getTheme();
        if (response.success && response.theme) {
          const settings = response.theme.settings || {};
          
          // Apply CSS variables
          Object.keys(settings).forEach(key => {
            document.documentElement.style.setProperty(`--${key}`, settings[key]);
          });

          // Apply favicon if set
          if (response.theme.favicon) {
            let link = document.querySelector("link[rel*='icon']") as HTMLLinkElement;
            if (!link) {
              link = document.createElement('link');
              link.rel = 'icon';
              document.getElementsByTagName('head')[0].appendChild(link);
            }
            link.href = response.theme.favicon;
          }
        }
      } catch (err) {
        console.error('Failed to load theme:', err);
      } finally {
        setThemeLoaded(true);
      }
    };

    loadAndApplyTheme();
  }, []);

  return { themeLoaded };
};
