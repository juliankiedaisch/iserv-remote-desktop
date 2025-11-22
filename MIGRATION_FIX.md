# Fix for Missing desktop_type Column Error

## Problem

The application was throwing the following error:

```
Error: Failed to load desktops: (psycopg2.errors.UndefinedColumn) column containers.desktop_type does not exist
LINE 1: ..., containers.image_name AS containers_image_name, containers...
```

This occurred because:
1. The `desktop_type` column was added to the `Container` model in `app/models/containers.py`
2. The application code in `app/routes/container_routes.py` queries this column
3. However, the database table `containers` was already created without this column
4. `db.create_all()` only creates new tables, it doesn't alter existing ones

## Solution

Implemented a database migration system to safely add the missing column:

### 1. Migration System (`run.py`)

- Added `run_migrations()` function that:
  - Discovers SQL migration files in `/migrations` directory
  - Executes them in sorted order on application startup
  - Handles errors gracefully with rollback

### 2. Migration File (`migrations/001_add_desktop_type_column.sql`)

```sql
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'containers' 
        AND column_name = 'desktop_type'
        AND table_schema = current_schema()
    ) THEN
        ALTER TABLE containers ADD COLUMN desktop_type VARCHAR(50);
        RAISE NOTICE 'Added desktop_type column to containers table';
    ELSE
        RAISE NOTICE 'desktop_type column already exists in containers table';
    END IF;
END $$;
```

### 3. Key Features

- **Idempotent**: Safe to run multiple times (checks if column exists first)
- **PostgreSQL-specific**: Uses DO $$ blocks for procedural logic
- **Schema-aware**: Includes `table_schema` check for security
- **Automatic**: Runs on every application startup

## Testing

Created `scripts/test_migration.py` to validate:
- ✓ Migration file syntax is correct
- ✓ Migration discovery works
- ✓ Container model includes desktop_type field
- ✓ Migration runner is properly configured

## Deployment

When the application is restarted:
1. It will execute `run_migrations()`
2. The migration will check if `desktop_type` column exists
3. If missing, it will add the column with `VARCHAR(50)` type
4. If already exists, it will skip (idempotent)

No manual database intervention required - just restart the application.

## Files Changed

- `run.py`: Added `run_migrations()` function
- `migrations/001_add_desktop_type_column.sql`: Migration to add column
- `migrations/README.md`: Documentation for migration system
- `scripts/test_migration.py`: Validation test script

## Verification

After deploying this fix, verify by:
1. Checking application logs for "✓ Executed migration: 001_add_desktop_type_column.sql"
2. Accessing the desktop selection page - it should load without errors
3. Creating a new container - `desktop_type` should be properly stored

## Future Migrations

To add more migrations:
1. Create `migrations/002_your_migration.sql`
2. Write idempotent PostgreSQL SQL
3. Restart the application
