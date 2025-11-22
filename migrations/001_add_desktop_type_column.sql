-- Migration: Add desktop_type column to containers table
-- This column stores the type of desktop environment (e.g., 'ubuntu-desktop', 'vs-code', 'chromium')

-- Add the desktop_type column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'containers' AND column_name = 'desktop_type'
    ) THEN
        ALTER TABLE containers ADD COLUMN desktop_type VARCHAR(50);
        RAISE NOTICE 'Added desktop_type column to containers table';
    ELSE
        RAISE NOTICE 'desktop_type column already exists in containers table';
    END IF;
END $$;
