-- Migration 006: Restructure Desktop Images and Assignments
-- This migration separates the desktop image management from assignments
-- and adds folder assignment capabilities for teachers

-- Step 1: Rename desktop_types table to desktop_images
ALTER TABLE desktop_types RENAME TO desktop_images;

-- Step 2: Add new columns to desktop_images table
ALTER TABLE desktop_images 
    ADD COLUMN created_by VARCHAR(128) REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Step 3: Update desktop_assignments table structure
-- First, add new columns
ALTER TABLE desktop_assignments
    ADD COLUMN desktop_image_id INTEGER,
    ADD COLUMN group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    ADD COLUMN assignment_folder_path VARCHAR(512),
    ADD COLUMN assignment_folder_name VARCHAR(128),
    ADD COLUMN created_by VARCHAR(128) NOT NULL DEFAULT 'system',
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Step 4: Migrate data from old structure to new structure
-- Copy desktop_type_id to desktop_image_id
UPDATE desktop_assignments 
SET desktop_image_id = desktop_type_id
WHERE desktop_type_id IS NOT NULL;

-- Step 5: Migrate group_name to group_id (if groups exist)
-- This will need to be done manually or with a script since we need to match group names
-- For now, we'll leave group_id as NULL for existing assignments
-- and require admins to reassign them

-- Step 6: Make desktop_image_id NOT NULL and add foreign key
ALTER TABLE desktop_assignments
    ALTER COLUMN desktop_image_id SET NOT NULL,
    ADD CONSTRAINT fk_desktop_assignments_desktop_image 
        FOREIGN KEY (desktop_image_id) REFERENCES desktop_images(id) ON DELETE CASCADE;

-- Step 7: Add foreign key for created_by
ALTER TABLE desktop_assignments
    ADD CONSTRAINT fk_desktop_assignments_created_by
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE;

-- Step 8: Update user_id column to reference users table properly
ALTER TABLE desktop_assignments
    DROP CONSTRAINT IF EXISTS desktop_assignments_user_id_fkey,
    ADD CONSTRAINT fk_desktop_assignments_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Step 9: Drop old columns that are no longer needed
ALTER TABLE desktop_assignments
    DROP COLUMN IF EXISTS desktop_type_id,
    DROP COLUMN IF EXISTS group_name;

-- Step 10: Add new column to containers table
ALTER TABLE containers
    ADD COLUMN desktop_image_id INTEGER REFERENCES desktop_images(id) ON DELETE SET NULL;

-- Step 11: Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_desktop_assignments_desktop_image_id 
    ON desktop_assignments(desktop_image_id);
CREATE INDEX IF NOT EXISTS idx_desktop_assignments_group_id 
    ON desktop_assignments(group_id);
CREATE INDEX IF NOT EXISTS idx_desktop_assignments_user_id 
    ON desktop_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_desktop_assignments_created_by 
    ON desktop_assignments(created_by);
CREATE INDEX IF NOT EXISTS idx_containers_desktop_image_id 
    ON containers(desktop_image_id);
CREATE INDEX IF NOT EXISTS idx_desktop_images_enabled 
    ON desktop_images(enabled);

-- Step 12: Add check constraint to ensure either group_id or user_id is set (but not both)
ALTER TABLE desktop_assignments
    ADD CONSTRAINT check_assignment_target 
    CHECK (
        (group_id IS NOT NULL AND user_id IS NULL) OR 
        (group_id IS NULL AND user_id IS NOT NULL)
    );

-- Notes for manual migration:
-- 1. Existing assignments with group_name will need to be mapped to group_id
--    Run this query to see mappings:
--    SELECT da.id, da.group_name, g.id as group_id, g.name 
--    FROM desktop_assignments da
--    LEFT JOIN groups g ON da.group_name = g.name;
--
-- 2. Set created_by for existing assignments to an appropriate admin user
--
-- 3. Review and update desktop_images.created_by for existing images
