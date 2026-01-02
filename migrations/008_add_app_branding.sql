-- Migration: Add app_name and app_icon to theme_settings table
-- Date: 2026-01-02

ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS app_name VARCHAR(255) DEFAULT 'MDG Remote Desktop';
ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS app_icon TEXT;

-- Update existing record if exists
UPDATE theme_settings SET app_name = 'MDG Remote Desktop' WHERE app_name IS NULL;
