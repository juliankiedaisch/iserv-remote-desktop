import { useEffect, useState } from 'react';
import { apiService } from '../services/api';

interface ThemeData {
  settings: { [key: string]: string };
  favicon?: string;
  app_name: string;
  app_icon?: string;
}

export const useTheme = () => {
  const [themeLoaded, setThemeLoaded] = useState(false);
  const [themeData, setThemeData] = useState<ThemeData>({
    settings: {},
    app_name: 'MDG Remote Desktop',
  });

  useEffect(() => {
    const loadAndApplyTheme = async () => {
      try {
        const response = await apiService.getTheme();
        if (response.success && response.theme) {
          const settings = response.theme.settings || {};
          
          setThemeData({
            settings,
            favicon: response.theme.favicon,
            app_name: response.theme.app_name || 'MDG Remote Desktop',
            app_icon: response.theme.app_icon,
          });
          
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

  return { themeLoaded, themeData };
};
