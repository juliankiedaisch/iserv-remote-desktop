-- Migration 011: Add description column to desktop_assignments
-- This allows teachers to add a description to each assignment
-- enabling users to distinguish between multiple assignments with the same container image

ALTER TABLE desktop_assignments ADD COLUMN IF NOT EXISTS description TEXT;
