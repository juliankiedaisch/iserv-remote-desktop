-- Migration 007: Increase icon column size to support image URLs
-- This migration increases the icon column from VARCHAR(10) to VARCHAR(255)
-- to support storing uploaded image URLs alongside emoji icons

ALTER TABLE desktop_images 
ALTER COLUMN icon TYPE VARCHAR(255);

-- Add comment to document the change
COMMENT ON COLUMN desktop_images.icon IS 'Icon emoji or image URL path (e.g., /api/admin/desktops/icons/filename.png)';
