# Theme Customization System - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐         ┌─────────────────┐                      │
│  │   App.tsx    │────────▶│  useTheme Hook  │                      │
│  │              │         │                 │                      │
│  │  - Loads     │         │  - Loads theme  │                      │
│  │    theme on  │         │    on app start │                      │
│  │    startup   │         │  - Applies CSS  │                      │
│  └──────────────┘         │    variables    │                      │
│                           │  - Sets favicon │                      │
│                           └─────────────────┘                      │
│                                    │                                 │
│  ┌────────────────────────────────▼──────────────────┐             │
│  │           ThemeEditor Component                     │             │
│  │  ┌─────────────────────────────────────────────┐  │             │
│  │  │  - Color Pickers (16 variables)              │  │             │
│  │  │  - Live Preview                              │  │             │
│  │  │  - Favicon Upload                            │  │             │
│  │  │  - Export/Import/Reset/Save buttons          │  │             │
│  │  └─────────────────────────────────────────────┘  │             │
│  └────────────────────────────────────────────────────┘             │
│                           │                                          │
│                           │ API Calls                                │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────┐            │
│  │              ApiService (api.ts)                     │            │
│  │  - getTheme()                                        │            │
│  │  - updateTheme(settings, favicon)                   │            │
│  │  - exportTheme()                                     │            │
│  │  - importTheme(themeData)                           │            │
│  │  - resetTheme()                                      │            │
│  │  - uploadFavicon(faviconData)                       │            │
│  └─────────────────────────────────────────────────────┘            │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
                                 │ HTTP/JSON
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Backend (Flask/Python)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────┐            │
│  │          Theme Routes (theme_routes.py)              │            │
│  │  ┌───────────────────────────────────────────────┐  │            │
│  │  │  GET  /api/theme              - Get theme     │  │            │
│  │  │  PUT  /api/theme              - Update theme  │  │            │
│  │  │  GET  /api/theme/export       - Export theme  │  │            │
│  │  │  POST /api/theme/import       - Import theme  │  │            │
│  │  │  POST /api/theme/reset        - Reset theme   │  │            │
│  │  │  POST /api/theme/favicon      - Upload icon   │  │            │
│  │  └───────────────────────────────────────────────┘  │            │
│  │                       │                              │            │
│  │                       │ Requires Admin Auth          │            │
│  └───────────────────────┼──────────────────────────────┘            │
│                          │                                            │
│                          ▼                                            │
│  ┌─────────────────────────────────────────────────────┐            │
│  │     ThemeSettings Model (theme_settings.py)          │            │
│  │  ┌───────────────────────────────────────────────┐  │            │
│  │  │  - id: Integer (Primary Key)                  │  │            │
│  │  │  - settings: Text (JSON)                      │  │            │
│  │  │  - favicon: Text (Base64)                     │  │            │
│  │  │  - updated_at: DateTime                       │  │            │
│  │  │                                                │  │            │
│  │  │  Methods:                                      │  │            │
│  │  │  - get_current_theme() - Static                │  │            │
│  │  │  - to_dict() - Serialization                  │  │            │
│  │  │  - theme_dict property - JSON parsing         │  │            │
│  │  └───────────────────────────────────────────────┘  │            │
│  └─────────────────────────────────────────────────────┘            │
│                          │                                            │
│                          │ SQLAlchemy ORM                             │
│                          ▼                                            │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                      Database (PostgreSQL)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────┐            │
│  │              theme_settings Table                    │            │
│  │  ┌───────────────────────────────────────────────┐  │            │
│  │  │  id          │ SERIAL PRIMARY KEY             │  │            │
│  │  │  settings    │ TEXT NOT NULL                  │  │            │
│  │  │  favicon     │ TEXT                           │  │            │
│  │  │  updated_at  │ TIMESTAMP NOT NULL             │  │            │
│  │  └───────────────────────────────────────────────┘  │            │
│  │                                                       │            │
│  │  Migration: 005_add_theme_settings_table.sql         │            │
│  └─────────────────────────────────────────────────────┘            │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Theme Loading (App Startup)
```
App.tsx → useTheme Hook → API GET /api/theme → Database → Response
                             ↓
                    Apply CSS Variables
                    Set Favicon in DOM
```

### 2. Theme Editing
```
User Changes Color → Live Preview (CSS Variables)
                              ↓
                    Click "Save Theme"
                              ↓
           API PUT /api/theme → Validate → Database → Success
```

### 3. Export Theme
```
Click "Export" → API GET /api/theme/export → JSON Download
```

### 4. Import Theme
```
Upload JSON → Parse → API POST /api/theme/import → Validate → Database
                                      ↓
                            Apply CSS Variables
```

### 5. Favicon Upload
```
Select Image → Validate (Type/Size) → Convert to Base64
                              ↓
           API POST /api/theme/favicon → Database → Apply to DOM
```

## CSS Variables System

All colors are defined as CSS variables in `:root`:

```css
:root {
  --color-primary: #3e59d1;
  --color-secondary: #38d352;
  --color-danger: #dc3545;
  /* ... 16 total variables ... */
}
```

Components reference these variables:

```css
.button {
  background: var(--color-primary);
  color: var(--color-text-primary);
}
```

Changes apply instantly when variables are updated via JavaScript:

```javascript
document.documentElement.style.setProperty('--color-primary', '#ff0000');
```

## Security Features

1. **Authentication**: All modification endpoints require admin role
2. **Validation**: 
   - Favicon: File type, extension, size (max 1MB)
   - Colors: Hex format validation
3. **Race Condition**: Transaction handling in theme creation
4. **Input Sanitization**: JSON validation on import
5. **SQL Injection**: Protected by SQLAlchemy ORM

## Access Control

```
User Type       | View Theme | Edit Theme | Access Editor
─────────────────────────────────────────────────────────
Regular User    | ✅         | ❌         | ❌
Admin User      | ✅         | ✅         | ✅
Unauthenticated | ✅         | ❌         | ❌
```

## File Structure

```
iserv-remote-desktop/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   └── theme_settings.py         [NEW]
│   │   ├── routes/
│   │   │   └── theme_routes.py           [NEW]
│   │   └── __init__.py                   [MODIFIED]
│   └── migrations/
│       └── 005_add_theme_settings_table.sql [NEW]
├── frontend/
│   ├── src/
│   │   ├── hooks/
│   │   │   └── useTheme.ts               [NEW]
│   │   ├── pages/
│   │   │   ├── ThemeEditor.tsx           [NEW]
│   │   │   ├── ThemeEditor.css           [NEW]
│   │   │   ├── AdminPanel.tsx            [MODIFIED]
│   │   │   └── index.ts                  [MODIFIED]
│   │   ├── services/
│   │   │   └── api.ts                    [MODIFIED]
│   │   ├── App.tsx                       [MODIFIED]
│   │   ├── index.css                     [MODIFIED]
│   │   └── [9 CSS files]                 [MODIFIED]
└── THEME_CUSTOMIZATION.md                [NEW]
```

## Feature Highlights

✅ **16 Customizable Colors**
✅ **Live Preview** - No page reload needed
✅ **Favicon Upload** - Custom branding
✅ **Export/Import** - Share themes
✅ **Reset to Default** - Quick restore
✅ **Admin Only** - Secure access
✅ **Persistent** - Stored in database
✅ **Global** - All users see changes
✅ **Validated** - Security checks
✅ **Documented** - Comprehensive guide
