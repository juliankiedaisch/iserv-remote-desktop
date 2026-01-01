#!/usr/bin/env python3
"""
Migration 006: Restructure Desktop Images and Assignments

This script migrates the database from the old structure where desktop_types
and desktop_assignments were mixed, to the new structure with separate 
desktop_images and enhanced desktop_assignments with folder paths.

Usage:
    python scripts/migrate_006_desktop_restructure.py
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(env_path)

from app import create_app, db
from app.models.users import User
from app.models.groups import Group
from sqlalchemy import text


def migrate_desktop_structure():
    """Migrate the desktop structure from old to new format"""
    app = create_app()
    
    with app.app_context():
        print("Starting migration 006: Restructure Desktop Images and Assignments")
        print("=" * 70)
        
        try:
            # Step 1: Rename desktop_types to desktop_images
            print("\n[1/11] Renaming desktop_types table to desktop_images...")
            db.session.execute(text("""
                ALTER TABLE desktop_types RENAME TO desktop_images;
            """))
            db.session.commit()
            print("✓ Table renamed successfully")
            
            # Step 2: Add new columns to desktop_images
            print("\n[2/11] Adding new columns to desktop_images...")
            db.session.execute(text("""
                ALTER TABLE desktop_images 
                ADD COLUMN IF NOT EXISTS created_by VARCHAR(128),
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """))
            db.session.commit()
            print("✓ New columns added")
            
            # Step 3: Add foreign key for created_by in desktop_images
            print("\n[3/11] Adding foreign key constraints to desktop_images...")
            db.session.execute(text("""
                ALTER TABLE desktop_images
                ADD CONSTRAINT fk_desktop_images_created_by
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;
            """))
            db.session.commit()
            print("✓ Foreign keys added")
            
            # Step 4: Add new columns to desktop_assignments
            print("\n[4/11] Adding new columns to desktop_assignments...")
            db.session.execute(text("""
                ALTER TABLE desktop_assignments
                ADD COLUMN IF NOT EXISTS desktop_image_id INTEGER,
                ADD COLUMN IF NOT EXISTS group_id INTEGER,
                ADD COLUMN IF NOT EXISTS assignment_folder_path VARCHAR(512),
                ADD COLUMN IF NOT EXISTS assignment_folder_name VARCHAR(128),
                ADD COLUMN IF NOT EXISTS created_by VARCHAR(128),
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """))
            db.session.commit()
            print("✓ New columns added to desktop_assignments")
            
            # Step 5: Migrate desktop_type_id to desktop_image_id
            print("\n[5/11] Migrating desktop_type_id to desktop_image_id...")
            result = db.session.execute(text("""
                UPDATE desktop_assignments 
                SET desktop_image_id = desktop_type_id
                WHERE desktop_type_id IS NOT NULL;
            """))
            db.session.commit()
            print(f"✓ Migrated {result.rowcount} assignment records")
            
            # Step 6: Migrate group_name to group_id
            print("\n[6/11] Migrating group_name to group_id...")
            # Get all unique group names from assignments
            result = db.session.execute(text("""
                SELECT DISTINCT group_name 
                FROM desktop_assignments 
                WHERE group_name IS NOT NULL;
            """))
            group_names = [row[0] for row in result]
            
            if group_names:
                print(f"   Found {len(group_names)} unique group names to migrate")
                migrated = 0
                not_found = []
                
                for group_name in group_names:
                    # Try to find matching group
                    group = Group.query.filter_by(name=group_name).first()
                    if group:
                        db.session.execute(text("""
                            UPDATE desktop_assignments
                            SET group_id = :group_id
                            WHERE group_name = :group_name;
                        """), {'group_id': group.id, 'group_name': group_name})
                        migrated += 1
                    else:
                        not_found.append(group_name)
                
                db.session.commit()
                print(f"✓ Migrated {migrated} group assignments")
                if not_found:
                    print(f"⚠ Warning: Could not find groups for: {', '.join(not_found)}")
                    print(f"   These assignments will need to be recreated manually")
            else:
                print("✓ No group names to migrate")
            
            # Step 7: Set default created_by for existing assignments
            print("\n[7/11] Setting default created_by for existing assignments...")
            # Try to find an admin user
            admin_user = User.query.filter_by(role='admin').first()
            if admin_user:
                db.session.execute(text("""
                    UPDATE desktop_assignments
                    SET created_by = :admin_id
                    WHERE created_by IS NULL;
                """), {'admin_id': admin_user.id})
                db.session.commit()
                print(f"✓ Set created_by to admin user: {admin_user.username}")
            else:
                print("⚠ Warning: No admin user found, using 'system' as default")
                db.session.execute(text("""
                    UPDATE desktop_assignments
                    SET created_by = 'system'
                    WHERE created_by IS NULL;
                """))
                db.session.commit()
            
            # Step 8: Add constraints and foreign keys to desktop_assignments
            print("\n[8/11] Adding constraints to desktop_assignments...")
            
            # Make desktop_image_id NOT NULL
            db.session.execute(text("""
                ALTER TABLE desktop_assignments
                ALTER COLUMN desktop_image_id SET NOT NULL;
            """))
            
            # Make created_by NOT NULL
            db.session.execute(text("""
                ALTER TABLE desktop_assignments
                ALTER COLUMN created_by SET NOT NULL;
            """))
            
            # Add foreign key constraints
            db.session.execute(text("""
                ALTER TABLE desktop_assignments
                ADD CONSTRAINT fk_desktop_assignments_desktop_image 
                    FOREIGN KEY (desktop_image_id) REFERENCES desktop_images(id) ON DELETE CASCADE,
                ADD CONSTRAINT fk_desktop_assignments_group
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                ADD CONSTRAINT fk_desktop_assignments_user
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                ADD CONSTRAINT fk_desktop_assignments_created_by
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE;
            """))
            db.session.commit()
            print("✓ Constraints added")
            
            # Step 9: Drop old columns
            print("\n[9/11] Dropping old columns...")
            db.session.execute(text("""
                ALTER TABLE desktop_assignments
                DROP COLUMN IF EXISTS desktop_type_id,
                DROP COLUMN IF EXISTS group_name;
            """))
            db.session.commit()
            print("✓ Old columns dropped")
            
            # Step 10: Add desktop_image_id to containers
            print("\n[10/11] Adding desktop_image_id to containers...")
            db.session.execute(text("""
                ALTER TABLE containers
                ADD COLUMN IF NOT EXISTS desktop_image_id INTEGER;
                
                ALTER TABLE containers
                ADD CONSTRAINT fk_containers_desktop_image
                    FOREIGN KEY (desktop_image_id) REFERENCES desktop_images(id) ON DELETE SET NULL;
            """))
            db.session.commit()
            print("✓ Column added to containers")
            
            # Step 11: Create indexes
            print("\n[11/11] Creating indexes...")
            db.session.execute(text("""
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
            """))
            db.session.commit()
            print("✓ Indexes created")
            
            print("\n" + "=" * 70)
            print("✓ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Review desktop images and set created_by if needed")
            print("2. Review assignments that couldn't find matching groups")
            print("3. Test the new structure with admin and teacher roles")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            db.session.rollback()
            raise


def rollback_migration():
    """Rollback the migration (if needed)"""
    app = create_app()
    
    with app.app_context():
        print("Rolling back migration 006...")
        print("=" * 70)
        
        try:
            # Note: This is a simplified rollback and may not be complete
            print("⚠ Warning: Rollback will restore table name but data may be lost")
            print("Please ensure you have a database backup before proceeding")
            
            response = input("Continue with rollback? (yes/no): ")
            if response.lower() != 'yes':
                print("Rollback cancelled")
                return
            
            db.session.execute(text("""
                ALTER TABLE desktop_images RENAME TO desktop_types;
            """))
            db.session.commit()
            print("✓ Rollback completed")
            
        except Exception as e:
            print(f"✗ Rollback failed: {e}")
            db.session.rollback()
            raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate desktop structure')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.rollback:
        rollback_migration()
    else:
        migrate_desktop_structure()
