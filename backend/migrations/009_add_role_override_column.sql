-- Migration 009: Add role_override column to users table
-- This allows admins to override the OAuth-based role assignment

-- Add role_override column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_override VARCHAR(50);

-- Add a comment to explain the column
COMMENT ON COLUMN users.role_override IS 'Admin-set role override. When set, this takes precedence over OAuth group-based role assignment.';
