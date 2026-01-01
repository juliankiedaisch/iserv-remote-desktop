-- Migration: Add theme_settings table for customizable UI themes
-- This table stores theme configuration including colors and favicon

-- Create the theme_settings table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'theme_settings'
        AND table_schema = current_schema()
    ) THEN
        CREATE TABLE theme_settings (
            id SERIAL PRIMARY KEY,
            settings TEXT NOT NULL,
            favicon TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        RAISE NOTICE 'Created theme_settings table';
        
        -- Insert default theme
        INSERT INTO theme_settings (settings, favicon, updated_at)
        VALUES (
            '{"color-primary": "#3e59d1", "color-primary-dark": "#303383", "color-primary-gradient-start": "#667eea", "color-primary-gradient-end": "#764ba2", "color-secondary": "#38d352", "color-secondary-dark": "#278d31", "color-success": "#28a745", "color-danger": "#dc3545", "color-danger-hover": "#c82333", "color-warning": "#ffc107", "color-info": "#17a2b8", "color-gray": "#6c757d", "color-gray-dark": "#5a6268", "color-admin-badge": "#aaffad", "color-admin-button": "#32469c", "color-admin-button-hover": "#2d3c8d"}',
            NULL,
            CURRENT_TIMESTAMP
        );
        RAISE NOTICE 'Inserted default theme settings';
    ELSE
        RAISE NOTICE 'theme_settings table already exists';
    END IF;
END $$;
