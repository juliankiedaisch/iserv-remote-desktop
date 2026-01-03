# Language System Examples

## Frontend Usage Examples

### Example 1: Simple Text Translation

```typescript
// Before (hardcoded German)
<p>Login mit IServ, um auf Ihre Remote-Desktops zuzugreifen</p>

// After (with i18n)
import { useTranslation } from 'react-i18next';

const { t } = useTranslation();
<p>{t('auth.loginDescription')}</p>

// Result:
// EN: "Login with IServ to access your remote desktops"
// DE: "Login mit IServ, um auf Ihre Remote-Desktops zuzugreifen"
```

### Example 2: Button Labels

```typescript
// Before (hardcoded English)
<button className="btn btn-secondary" onClick={logout}>
  Logout
</button>

// After (with i18n)
<button className="btn btn-secondary" onClick={logout}>
  {t('common.logout')}
</button>

// Result:
// EN: "Logout"
// DE: "Abmelden"
```

### Example 3: Dynamic Content with Parameters

```typescript
// Before (hardcoded)
<p>Successfully stopped ${count} containers</p>

// After (with i18n)
<p>{t('admin.containersStopped', { count: 5 })}</p>

// Result:
// EN: "Successfully stopped 5 container(s)"
// DE: "5 Container erfolgreich gestoppt"
```

### Example 4: Status Messages

```typescript
// Before (hardcoded)
const status = isRunning ? 'Running' : 'Stopped';

// After (with i18n)
const status = isRunning 
  ? t('desktopCard.running') 
  : t('desktopCard.stopped');

// Result:
// EN: "Running" / "Stopped"
// DE: "Läuft" / "Gestoppt"
```

## Backend Usage Examples

### Example 1: Error Messages

```python
# Before (hardcoded)
return jsonify({'error': 'Admin access required'}), 403

# After (with i18n)
from app.i18n import get_message, get_language_from_request

lang = get_language_from_request()
return jsonify({'error': get_message('admin_required', lang)}), 403

# Result:
# EN: "Admin access required"
# DE: "Admin-Zugriff erforderlich"
```

### Example 2: Success Messages

```python
# Before (hardcoded)
return jsonify({
    'success': True,
    'message': 'Container stopped successfully'
})

# After (with i18n)
lang = get_language_from_request()
return jsonify({
    'success': True,
    'message': get_message('container_stopped', lang)
})

# Result:
# EN: "Container stopped successfully"
# DE: "Container erfolgreich gestoppt"
```

### Example 3: Messages with Parameters

```python
# Before (hardcoded)
return jsonify({
    'message': f'Stopped {stopped_count} containers'
})

# After (with i18n)
lang = get_language_from_request()
return jsonify({
    'message': get_message('containers_stopped', lang, count=stopped_count)
})

# Result:
# EN: "Successfully stopped 5 container(s)"
# DE: "5 Container erfolgreich gestoppt"
```

## Language Detection

### Frontend (Browser)
```typescript
// Automatic detection on first visit
const browserLang = navigator.language; // e.g., "de-DE"
if (browserLang.startsWith('de')) {
  // Set language to German
}

// Manual selection (saved to localStorage)
i18n.changeLanguage('de');
// Language preference persists across sessions
```

### Backend (HTTP Headers)
```python
# Method 1: Query parameter
# GET /api/admin/containers?lang=de

# Method 2: Custom header
# GET /api/admin/containers
# X-Language: de

# Method 3: Accept-Language header
# GET /api/admin/containers
# Accept-Language: de-DE,de;q=0.9

# Detection logic
lang = request.args.get('lang') or \
       request.headers.get('X-Language') or \
       ('de' if 'de' in request.headers.get('Accept-Language', '').lower() else 'en')
```

## Language Switcher Component

The language switcher is visible in two places:
1. **Login Page**: Top-right corner
2. **All Authenticated Pages**: Header next to logout button

```typescript
// LanguageSwitcher.tsx
export const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'de' : 'en';
    i18n.changeLanguage(newLang);  // All text updates immediately
  };

  return (
    <button className="language-switcher" onClick={toggleLanguage}>
      {i18n.language === 'en' ? '🇩🇪 DE' : '🇬🇧 EN'}
    </button>
  );
};
```

## User Flow Example

1. **User visits site** → Browser language detected
   - Browser: `de-DE` → App shows German
   - Browser: `en-US` → App shows English

2. **User clicks language switcher**
   - Changes from German to English (or vice versa)
   - Preference saved to localStorage
   - All text updates immediately

3. **User closes browser and returns**
   - Preference loaded from localStorage
   - App shows previously selected language

4. **User makes API request**
   - Frontend sends `Accept-Language` header
   - Backend returns messages in user's language

## Translation File Structure

### Frontend (JSON)
```json
{
  "common": {
    "loading": "Loading...",
    "logout": "Logout",
    // ...
  },
  "auth": {
    "loginWithIServ": "Login with IServ",
    // ...
  },
  "dashboard": {
    "title": "MDG Remote Desktop",
    // ...
  }
}
```

### Backend (Python Dictionary)
```python
messages = {
    'en': {
        'session_required': 'Session required',
        'container_stopped': 'Container stopped successfully',
        # ...
    },
    'de': {
        'session_required': 'Sitzung erforderlich',
        'container_stopped': 'Container erfolgreich gestoppt',
        # ...
    }
}
```

## Benefits

1. **Consistent UX**: Users see interface in their preferred language
2. **Easy Maintenance**: All translations in one place
3. **Extensible**: Easy to add new languages
4. **Type-Safe**: TypeScript catches translation key typos
5. **Performance**: Translations loaded once, no runtime overhead
6. **Automatic**: Browser language detected automatically
7. **Persistent**: Language choice saved and remembered
