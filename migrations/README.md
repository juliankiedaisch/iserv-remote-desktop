# Database Migrations

This directory contains SQL migration scripts for the database schema.

## Migration Files

- `001_add_desktop_type_column.sql` - Adds the desktop_type column to the containers table

## How It Works

Migrations are automatically run when the application starts via the `run_migrations()` function in `run.py`.

Each migration file is executed in order based on its numeric prefix (e.g., 001, 002, etc.).

## Requirements

- Migrations must be written in PostgreSQL-compatible SQL
- Each migration should be idempotent (safe to run multiple times)
- Use `IF NOT EXISTS` checks or similar patterns to ensure idempotency
- Include `table_schema = current_schema()` in schema checks for security

## Adding New Migrations

1. Create a new SQL file with the next sequential number (e.g., `002_your_migration.sql`)
2. Write idempotent SQL using PostgreSQL syntax
3. Test your migration syntax with `python3 scripts/test_migration.py`
4. The migration will be automatically picked up and executed on the next application start

## Example Migration

```sql
-- Migration: Add example_column to table_name
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'table_name' 
        AND column_name = 'example_column'
        AND table_schema = current_schema()
    ) THEN
        ALTER TABLE table_name ADD COLUMN example_column VARCHAR(100);
        RAISE NOTICE 'Added example_column to table_name';
    ELSE
        RAISE NOTICE 'example_column already exists in table_name';
    END IF;
END $$;
```

## Troubleshooting

If a migration fails:
1. Check the application logs for error messages
2. Verify the migration SQL syntax is correct
3. Ensure the migration is idempotent
4. Manually inspect the database schema if needed
5. Fix the migration file and restart the application

