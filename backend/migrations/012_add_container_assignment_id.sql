-- Migration 012: Add assignment_id to containers table
-- This links containers to specific assignments, allowing users to have multiple containers
-- for the same docker image but different assignments

-- Add assignment_id column
ALTER TABLE containers 
ADD COLUMN IF NOT EXISTS assignment_id INTEGER REFERENCES desktop_assignments(id) ON DELETE SET NULL;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_containers_assignment_id ON containers(assignment_id);

-- Create composite index for common query pattern (user + desktop_type + assignment)
CREATE INDEX IF NOT EXISTS idx_containers_user_desktop_assignment 
ON containers(user_id, desktop_type, assignment_id);
