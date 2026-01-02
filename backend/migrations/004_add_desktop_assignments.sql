-- Add desktop type management and assignments
-- Run this migration to add desktop type assignment functionality

CREATE TABLE IF NOT EXISTS desktop_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    docker_image VARCHAR(256) NOT NULL,
    description TEXT,
    icon VARCHAR(10),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS desktop_assignments (
    id SERIAL PRIMARY KEY,
    desktop_type_id INTEGER NOT NULL REFERENCES desktop_types(id) ON DELETE CASCADE,
    group_name VARCHAR(128),
    user_id VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (group_name IS NOT NULL OR user_id IS NOT NULL)
);

CREATE INDEX idx_desktop_assignments_type ON desktop_assignments(desktop_type_id);
CREATE INDEX idx_desktop_assignments_group ON desktop_assignments(group_name);
CREATE INDEX idx_desktop_assignments_user ON desktop_assignments(user_id);

-- Insert default desktop types
INSERT INTO desktop_types (name, docker_image, description, icon, enabled) VALUES
('VS Code', 'kasmweb/vs-code:1.16.0', 'Visual Studio Code development environment', '💻', TRUE),
('Ubuntu Desktop', 'kasmweb/ubuntu-jammy-desktop:1.16.0', 'Full Ubuntu desktop environment', '🖥️', TRUE)
ON CONFLICT (name) DO NOTHING;
