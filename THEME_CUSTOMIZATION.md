# Theme Customization Feature

This document describes the theme customization feature that allows administrators to modify the application's appearance.

## Overview

The theme customization feature enables administrators to:
- Change colors throughout the application UI
- Upload and set a custom favicon
- Export theme configurations to JSON files
- Import previously saved theme configurations
- Reset theme to default settings

## Features

### 1. Global CSS Variables

All colors in the application use CSS variables defined in `index.css`. This allows dynamic theme changes without reloading the page.

**Available color variables:**
- `--color-primary`: Main brand color
- `--color-primary-dark`: Darker shade of primary color
- `--color-primary-gradient-start`: Start of primary gradient
- `--color-primary-gradient-end`: End of primary gradient
- `--color-secondary`: Secondary actions color
- `--color-secondary-dark`: Darker secondary color
- `--color-success`: Success states color
- `--color-danger`: Error/danger states color
- `--color-danger-hover`: Danger button hover color
- `--color-warning`: Warning states color
- `--color-info`: Info states color
- `--color-gray`: Neutral gray color
- `--color-gray-dark`: Darker gray color
- `--color-admin-badge`: Admin badge color
- `--color-admin-button`: Admin button color
- `--color-admin-button-hover`: Admin button hover color

### 2. Theme Editor UI

**Location:** Admin Panel → Theme Settings (🎨 button)

**Access:** Admin users only

**Features:**
- **Color Palette Editor**: Color pickers and hex input fields for each theme variable
- **Live Preview**: Changes apply immediately in the editor
- **Favicon Upload**: Upload custom favicon (any image format)
- **Save Theme**: Persist theme changes to database
- **Export Theme**: Download theme as JSON file
- **Import Theme**: Upload previously exported theme JSON
- **Reset to Default**: Restore original theme colors

### 3. Backend API Endpoints

#### Get Theme
```
GET /api/theme
Returns: Current theme settings and favicon
```

#### Update Theme
```
PUT /api/theme
Body: { settings: {...}, favicon: "base64..." }
Auth: Admin only
```

#### Export Theme
```
GET /api/theme/export
Returns: Theme JSON for download
Auth: Admin only
```

#### Import Theme
```
POST /api/theme/import
Body: Theme JSON
Auth: Admin only
```

#### Reset Theme
```
POST /api/theme/reset
Resets to default theme
Auth: Admin only
```

#### Upload Favicon
```
POST /api/theme/favicon
Body: { favicon: "base64..." }
Auth: Admin only
```

## Usage Guide

### For Administrators

1. **Accessing Theme Settings:**
   - Log in as an administrator
   - Navigate to Admin Panel
   - Click "🎨 Theme Settings" button

2. **Changing Colors:**
   - Use color pickers to select colors visually
   - Or enter hex color codes directly (#RRGGBB format)
   - Changes preview immediately
   - Click "💾 Save Theme" to persist changes

3. **Changing Favicon:**
   - Click "Upload Favicon" in the Favicon section
   - Select an image file (recommended: 32x32 or 64x64 pixels)
   - Preview appears immediately
   - Click "💾 Save Theme" to persist

4. **Exporting Theme:**
   - Click "📥 Export Theme"
   - JSON file downloads automatically
   - Save for backup or sharing

5. **Importing Theme:**
   - Click "📤 Import Theme"
   - Select a previously exported JSON file
   - Theme applies immediately
   - Click "💾 Save Theme" to persist

6. **Resetting Theme:**
   - Click "🔄 Reset to Default"
   - Confirm the action
   - Theme reverts to original colors

### For Developers

1. **Using CSS Variables in New Components:**
   ```css
   .my-component {
     background-color: var(--color-primary);
     color: var(--color-text-primary);
   }
   ```

2. **Adding New Theme Variables:**
   - Add variable to `index.css` `:root` section
   - Add to default theme in `theme_settings.py`
   - Add to `colorFields` array in `ThemeEditor.tsx`

3. **Database Schema:**
   - Table: `theme_settings`
   - Columns: `id`, `settings` (JSON), `favicon` (TEXT), `updated_at`
   - Migration: `005_add_theme_settings_table.sql`

## Theme JSON Format

```json
{
  "settings": {
    "color-primary": "#3e59d1",
    "color-primary-dark": "#303383",
    "color-secondary": "#38d352",
    ...
  },
  "favicon": "data:image/png;base64,..."
}
```

## Files Modified/Added

### Backend
- `backend/app/models/theme_settings.py` - Theme settings model
- `backend/app/routes/theme_routes.py` - Theme API routes
- `backend/app/__init__.py` - Register theme routes
- `migrations/005_add_theme_settings_table.sql` - Database migration

### Frontend
- `frontend/src/index.css` - CSS variables definition
- `frontend/src/pages/ThemeEditor.tsx` - Theme editor component
- `frontend/src/pages/ThemeEditor.css` - Theme editor styles
- `frontend/src/hooks/useTheme.ts` - Theme loading hook
- `frontend/src/services/api.ts` - Theme API methods
- `frontend/src/App.tsx` - Added theme route and loading
- `frontend/src/pages/AdminPanel.tsx` - Added theme settings link
- All CSS files - Converted to use CSS variables

## Security Considerations

1. **Authentication:** All theme modification endpoints require admin authentication
2. **Authorization:** Only users with admin role can access theme settings
3. **Input Validation:** Color values are validated on both frontend and backend
4. **File Upload:** Favicon uploads are base64 encoded and size-limited
5. **SQL Injection:** Protected by SQLAlchemy ORM

## Performance

- Theme loads asynchronously on app start
- CSS variables update instantly without page reload
- Theme settings cached in browser after load
- Minimal impact on page load time (~1-2ms)

## Browser Compatibility

- All modern browsers (Chrome, Firefox, Safari, Edge)
- CSS variables supported in all major browsers since 2017
- Favicon changes apply immediately in most browsers
- Some browsers may require cache clear for favicon updates

## Troubleshooting

**Theme not saving:**
- Check browser console for errors
- Verify admin permissions
- Check database connection

**Colors not applying:**
- Clear browser cache
- Check CSS variable names match
- Inspect element to verify variable values

**Favicon not changing:**
- Hard refresh browser (Ctrl+F5)
- Clear browser cache
- Check favicon file size and format

**Import fails:**
- Verify JSON file format
- Check all required color keys present
- Ensure valid hex color codes

## Future Enhancements

Potential improvements for future versions:
- Theme templates/presets
- Dark mode support
- Font customization
- Logo upload
- Per-user themes
- Theme scheduling (day/night modes)
- Advanced color picker (HSL, RGB)
- Theme preview before applying
