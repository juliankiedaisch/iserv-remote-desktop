# Multi-Language Support (i18n)

This document describes the internationalization (i18n) system implemented in the iServ Remote Desktop application.

## Overview

The application now supports multiple languages (English and German) with an easily extensible system for adding more languages in the future.

## Frontend (React + TypeScript)

### Technologies
- **i18next**: Core internationalization framework
- **react-i18next**: React bindings for i18next

### Installation
The required packages are already installed:
```bash
npm install i18next react-i18next
```

### Configuration
The i18n system is configured in `/frontend/src/i18n/config.ts`:
- Automatically detects browser language
- Falls back to English if language not supported
- Persists language preference in localStorage
- Supports English (en) and German (de)

### Translation Files
Translation files are located in `/frontend/src/i18n/`:
- `en.json`: English translations
- `de.json`: German translations

### Language Switcher
A language switcher component is available in the header on all authenticated pages and on the login page:
- Click the language button to toggle between English and German
- Language preference is saved automatically
- All text updates immediately when language is changed

### Usage in Components
To use translations in a component:

```typescript
import { useTranslation } from 'react-i18next';

export const MyComponent: React.FC = () => {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t('common.loading')}</h1>
      <p>{t('dashboard.noDesktops')}</p>
      {/* With parameters */}
      <p>{t('admin.containersStopped', { count: 5 })}</p>
    </div>
  );
};
```

### Translated Components
The following components have been updated with translations:
- **Login.tsx**: Login page with language switcher
- **Dashboard.tsx**: Main dashboard with desktop cards
- **AdminPanel.tsx**: Admin panel with container management
- **Header.tsx**: Header component with navigation and language switcher
- **DesktopCard.tsx**: Desktop card with status information
- **App.tsx**: Protected routes with loading messages
- **LanguageSwitcher.tsx**: Language toggle button

### Translation Keys
Major translation key categories:
- `common.*`: Common UI elements (buttons, actions, etc.)
- `auth.*`: Authentication-related messages
- `dashboard.*`: Dashboard-specific text
- `admin.*`: Admin panel text
- `desktopCard.*`: Desktop card status and actions
- `header.*`: Navigation and header elements
- `fileManager.*`: File manager interface (optional)
- `theme.*`: Theme editor (optional)
- `desktopTypes.*`: Desktop types manager (optional)
- `assignments.*`: Assignment manager (optional)
- `errors.*`: Error messages

## Backend (Flask + Python)

### Technologies
- Custom i18n module with message dictionaries
- Language detection from request headers

### Configuration
The i18n system is implemented in `/backend/app/i18n/__init__.py`:
- Provides `get_message(key, lang, **kwargs)` function
- Provides `get_language_from_request()` function
- Supports English (en) and German (de)

### Translation Messages
All backend messages are defined in the `messages` dictionary in `/backend/app/i18n/__init__.py`:
- Organized by category (auth, containers, desktop types, file operations, etc.)
- Support parameter substitution using Python's `.format()` method

### Language Detection
The backend detects language from:
1. `?lang=` query parameter
2. `X-Language` header
3. `Accept-Language` header
4. Default: English

### Usage in Routes
To use translations in a route:

```python
from app.i18n import get_message, get_language_from_request

@app.route('/my-route')
def my_route():
    lang = get_language_from_request()
    
    return jsonify({
        'success': True,
        'message': get_message('container_stopped', lang)
    })
    
    # With parameters
    return jsonify({
        'message': get_message('containers_stopped', lang, count=5)
    })
```

### Updated Routes
The following routes have been updated with translations:
- **admin_routes.py**: All admin endpoints with translated messages
  - `require_admin` decorator
  - `list_all_containers`
  - `stop_container_admin`
  - `remove_container_admin`
  - `stop_all_containers`
  - `cleanup_stopped_containers`

### Translation Keys
Major translation key categories:
- Session and auth messages
- Container operations
- Desktop type management
- File operations
- Assignment management
- Theme management
- General errors

## Adding a New Language

### Frontend
1. Create a new translation file in `/frontend/src/i18n/` (e.g., `fr.json` for French)
2. Copy the structure from `en.json` or `de.json`
3. Translate all values
4. Import and register the language in `/frontend/src/i18n/config.ts`:

```typescript
import fr from './fr.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      de: { translation: de },
      fr: { translation: fr }  // Add new language
    },
    // ...
  });
```

5. Update the language switcher if needed to support more than 2 languages

### Backend
1. Add translations to the `messages` dictionary in `/backend/app/i18n/__init__.py`:

```python
messages = {
    'en': { ... },
    'de': { ... },
    'fr': {  # Add new language
        'session_required': 'Session requise',
        # ... add all translations
    }
}
```

2. Update `get_language_from_request()` to recognize the new language code
3. Update language detection logic if needed

## Testing

### Frontend Testing
1. Start the frontend: `cd frontend && npm start`
2. Open the application in a browser
3. Click the language switcher to toggle between languages
4. Verify all text changes correctly
5. Check that language preference persists after page reload

### Backend Testing
To test backend translations, send requests with different language headers:

```bash
# English (default)
curl http://localhost:5021/api/admin/containers

# German
curl http://localhost:5021/api/admin/containers -H "X-Language: de"

# Or with Accept-Language header
curl http://localhost:5021/api/admin/containers -H "Accept-Language: de-DE,de;q=0.9"
```

## Browser Language Detection
The application automatically detects the user's browser language on first visit:
- If browser language is German (de*), the app defaults to German
- Otherwise, defaults to English
- User's manual selection overrides browser detection and is saved in localStorage

## Best Practices
1. Always use translation keys instead of hardcoded text
2. Keep translation keys organized by feature/component
3. Use descriptive key names that indicate the context
4. Provide parameters for dynamic content (e.g., counts, names)
5. Test all translations in both languages before committing
6. Keep translation files synchronized (same keys in all languages)

## Future Enhancements
Possible improvements:
- Add more languages (French, Spanish, etc.)
- Implement pluralization rules for complex grammar
- Add date/time localization
- Add number formatting based on locale
- Implement server-side rendering with i18n
- Add translation management UI for admins
