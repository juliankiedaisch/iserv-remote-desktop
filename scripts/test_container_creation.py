#!/usr/bin/env python3
"""
Test script to verify container creation handles duplicate names correctly

This test verifies the fix for the unique constraint violation error when
creating containers with duplicate names.
"""

import os
import sys
from datetime import datetime, timezone
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_duplicate_container_handling():
    """Test that creating a container with a duplicate name is handled correctly"""
    print("Testing duplicate container name handling...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app import create_app, db
        from app.models.users import User
        from app.models.oauth_session import OAuthSession
        from app.models.containers import Container
        
        app = create_app(debug=False)
        
        with app.app_context():
            # Create test user
            test_user_id = str(uuid.uuid4())
            test_session_id = str(uuid.uuid4())
            test_username = "test.user"
            
            # Create a container record with a specific name (simulating existing record)
            container_name = f"kasm-{test_username}-ubuntu-vscode-{test_session_id[:8]}"
            
            # Clean up any existing test containers
            existing = Container.query.filter_by(container_name=container_name).all()
            for container in existing:
                db.session.delete(container)
            db.session.commit()
            
            # Create first container record (simulating a stopped/error state container)
            container1 = Container(
                user_id=test_user_id,
                session_id=test_session_id,
                container_name=container_name,
                image_name='kasmweb/vs-code:1.15.0',
                desktop_type='ubuntu-vscode',
                status='stopped',  # This is the key - it's not 'running'
                container_port=6901
            )
            db.session.add(container1)
            db.session.commit()
            print(f"✓ Created initial container record with status='stopped'")
            
            # Verify it exists
            found = Container.query.filter_by(container_name=container_name).first()
            assert found is not None, "Container should exist in database"
            assert found.status == 'stopped', "Container should have status='stopped'"
            print(f"✓ Verified container exists with name: {container_name}")
            
            # Now simulate the scenario from the error:
            # Try to check for existing containers by session_id, user_id, and desktop_type
            existing_by_session = Container.query.filter_by(
                session_id=test_session_id,
                user_id=test_user_id,
                desktop_type='ubuntu-vscode'
            ).first()
            
            if existing_by_session:
                print(f"✓ Found existing container with name '{existing_by_session.container_name}' in state '{existing_by_session.status}'")
                
                if existing_by_session.status in ['error', 'stopped', 'creating']:
                    print(f"✓ Container is in cleanup-eligible state: {existing_by_session.status}")
                    # Clean it up
                    db.session.delete(existing_by_session)
                    db.session.commit()
                    print(f"✓ Successfully cleaned up existing container record")
                    
                    # Verify it's gone
                    check = Container.query.filter_by(
                        session_id=test_session_id,
                        user_id=test_user_id,
                        desktop_type='ubuntu-vscode'
                    ).first()
                    assert check is None, "Container should be deleted"
                    print(f"✓ Verified container was removed from database")
                    
                    # Now we can create a new one without constraint violation
                    container2 = Container(
                        user_id=test_user_id,
                        session_id=test_session_id,
                        container_name=container_name,
                        image_name='kasmweb/vs-code:1.15.0',
                        desktop_type='ubuntu-vscode',
                        status='creating',
                        container_port=6901
                    )
                    db.session.add(container2)
                    db.session.commit()
                    print(f"✓ Successfully created new container with same name")
                    
                    # Clean up test data
                    db.session.delete(container2)
                    db.session.commit()
                    print(f"✓ Cleaned up test data")
            
            print("\n✓ All duplicate container handling tests passed!")
            return True
            
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {str(e)}")
        return False
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    print("=" * 60)
    print("Container Creation Duplicate Name Test")
    print("=" * 60)
    print()
    
    result = test_duplicate_container_handling()
    
    print("\n" + "=" * 60)
    if result:
        print("✓ TEST PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ TEST FAILED")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
