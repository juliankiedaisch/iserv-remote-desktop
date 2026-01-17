-- Migration 010: Add audio_port column to containers table
-- This column stores the host port mapped to the container's audio WebSocket (port 4901)

ALTER TABLE containers 
ADD COLUMN IF NOT EXISTS audio_port INTEGER;

-- Add comment for documentation
COMMENT ON COLUMN containers.audio_port IS 'Port on host machine for audio WebSocket (maps to container port 4901)';
