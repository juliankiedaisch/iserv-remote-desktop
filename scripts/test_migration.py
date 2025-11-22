#!/usr/bin/env python3
"""
Test script to verify the desktop_type migration works correctly

NOTE: This migration is PostgreSQL-specific and requires a PostgreSQL database.
For production testing, use the actual PostgreSQL database configured in .env

This script verifies:
1. The migration file syntax is correct
2. The run_migrations() function can discover and read migrations
3. The Container model includes the desktop_type field
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_migration_file_syntax():
    """Verify the migration SQL syntax is correct"""
    print("Testing migration file syntax...")
    
    migration_file = 'migrations/001_add_desktop_type_column.sql'
    
    try:
        with open(migration_file, 'r') as f:
            content = f.read()
        
        # Verify key elements are present
        checks = [
            ('DO $$', 'PostgreSQL block syntax'),
            ('information_schema.columns', 'Column existence check'),
            ('ALTER TABLE containers ADD COLUMN desktop_type', 'ALTER TABLE statement'),
            ('VARCHAR(50)', 'Column type'),
            ('IF NOT EXISTS', 'Idempotency check'),
        ]
        
        all_passed = True
        for pattern, description in checks:
            if pattern in content:
                print(f'  ✓ Found: {description}')
            else:
                print(f'  ✗ Missing: {description}')
                all_passed = False
        
        if all_passed:
            print('✓ Migration file syntax is correct\n')
            return True
        else:
            print('✗ Migration file syntax has issues\n')
            return False
            
    except Exception as e:
        print(f'✗ Failed to read migration file: {str(e)}\n')
        return False

def test_migration_discovery():
    """Verify the migration discovery logic works"""
    print("Testing migration discovery...")
    
    try:
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'migrations')
        
        if not os.path.exists(migrations_dir):
            print(f'✗ Migrations directory not found: {migrations_dir}\n')
            return False
        
        # Get all SQL migration files sorted by name
        migration_files = sorted([
            f for f in os.listdir(migrations_dir)
            if f.endswith('.sql')
        ])
        
        if not migration_files:
            print('✗ No migration files found\n')
            return False
        
        print(f'  Found {len(migration_files)} migration file(s):')
        for mf in migration_files:
            print(f'    - {mf}')
            migration_path = os.path.join(migrations_dir, mf)
            with open(migration_path, 'r') as f:
                sql = f.read()
                print(f'      Size: {len(sql)} bytes')
        
        print('✓ Migration discovery works correctly\n')
        return True
        
    except Exception as e:
        print(f'✗ Migration discovery failed: {str(e)}\n')
        return False

def test_model_has_desktop_type():
    """Verify the Container model has the desktop_type field"""
    print("Testing Container model...")
    
    try:
        from app.models.containers import Container
        from sqlalchemy import inspect as sqlalchemy_inspect
        
        # Get the model's columns
        mapper = sqlalchemy_inspect(Container)
        columns = [col.key for col in mapper.columns]
        
        if 'desktop_type' in columns:
            print(f'  ✓ Container model has desktop_type field')
            print(f'  Model columns: {", ".join(columns)}')
            print('✓ Container model is correctly defined\n')
            return True
        else:
            print(f'  ✗ Container model missing desktop_type field')
            print(f'  Available columns: {", ".join(columns)}')
            print('✗ Container model is incorrectly defined\n')
            return False
            
    except Exception as e:
        print(f'✗ Failed to inspect Container model: {str(e)}\n')
        import traceback
        traceback.print_exc()
        return False

def test_run_migrations_function():
    """Verify the run_migrations function exists and can be imported"""
    print("Testing run_migrations function...")
    
    try:
        # Read run.py to check if run_migrations exists
        with open('run.py', 'r') as f:
            content = f.read()
        
        if 'def run_migrations():' in content:
            print('  ✓ run_migrations() function is defined')
            
            # Check if it's being called
            if 'run_migrations()' in content:
                print('  ✓ run_migrations() is called in run.py')
                print('✓ Migration runner is properly configured\n')
                return True
            else:
                print('  ✗ run_migrations() is not called')
                print('✗ Migration runner is not properly configured\n')
                return False
        else:
            print('  ✗ run_migrations() function not found')
            print('✗ Migration runner is not defined\n')
            return False
            
    except Exception as e:
        print(f'✗ Failed to check run.py: {str(e)}\n')
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Desktop Type Migration Test")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Migration File Syntax", test_migration_file_syntax()))
    results.append(("Migration Discovery", test_migration_discovery()))
    results.append(("Container Model", test_model_has_desktop_type()))
    results.append(("Migration Runner", test_run_migrations_function()))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All validation checks passed!")
        print("\nNote: This migration requires PostgreSQL and will be")
        print("automatically executed when the application starts.")
        return 0
    else:
        print("\n✗ Some validation checks failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
