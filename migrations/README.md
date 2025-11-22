# Database Migrations

This directory contains SQL migration scripts for the database schema.

## Migration Files

- `001_add_desktop_type_column.sql` - Adds the desktop_type column to the containers table

## How It Works

Migrations are automatically run when the application starts via the `run_migrations()` function in `run.py`.

Each migration file is executed in order based on its numeric prefix (e.g., 001, 002, etc.).

## Adding New Migrations

1. Create a new SQL file with the next sequential number (e.g., `002_your_migration.sql`)
2. Write idempotent SQL (use IF NOT EXISTS checks where applicable)
3. The migration will be automatically picked up and executed on the next application start
