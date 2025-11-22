-- Add proxy_path column to containers table
-- This migration is idempotent and safe to run multiple times

-- Add proxy_path column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='containers' AND column_name='proxy_path'
    ) THEN
        ALTER TABLE containers ADD COLUMN proxy_path VARCHAR(256) UNIQUE;
    END IF;
END $$;
