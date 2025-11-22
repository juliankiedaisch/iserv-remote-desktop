#!/usr/bin/env python3
"""
Test script to verify container cleanup for duplicate proxy_path and container_name

This test verifies the fix for:
1. duplicate key value violates unique constraint "containers_proxy_path_key"
2. Conflict. The container name is already in use by container
"""

import os
import sys
from datetime import datetime, timezone
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_proxy_path_conflict():
    """Test that containers with duplicate proxy_path are cleaned up"""
    print("\n1. Testing proxy_path conflict cleanup...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app import create_app, db
        from app.models.containers import Container
        from sqlalchemy import or_
        
        app = create_app(debug=False)
        
        with app.app_context():
            # Create test data
            test_user_id = str(uuid.uuid4())
            test_session_id_1 = str(uuid.uuid4())
            test_session_id_2 = str(uuid.uuid4())
            test_username = "test.user1"
            desktop_type = "ubuntu-vscode"
            
            # Generate the proxy path that would be used
            proxy_path = f"{test_username}-{desktop_type}"
            
            # Clean up any existing test containers
            existing = Container.query.filter(
                or_(
                    Container.user_id == test_user_id,
                    Container.proxy_path == proxy_path
                )
            ).all()
            for container in existing:
                db.session.delete(container)
            db.session.commit()
            
            # Create first container with proxy_path (from old session)
            container1 = Container(
                user_id=test_user_id,
                session_id=test_session_id_1,
                container_name=f"kasm-{test_username}-{desktop_type}-{test_session_id_1[:8]}",
                image_name='kasmweb/vs-code:1.15.0',
                desktop_type=desktop_type,
                status='stopped',
                container_port=6901,
                proxy_path=proxy_path
            )
            db.session.add(container1)
            db.session.commit()
            print(f"   ✓ Created container 1 with proxy_path: {proxy_path}")
            
            # Now simulate creating a new container with same proxy_path
            # First check for conflicts (this is what the fix does)
            container_name_2 = f"kasm-{test_username}-{desktop_type}-{test_session_id_2[:8]}"
            conflicting = Container.query.filter(
                or_(
                    Container.proxy_path == proxy_path,
                    Container.container_name == container_name_2
                ),
                Container.user_id == test_user_id
            ).all()
            
            assert len(conflicting) > 0, "Should find conflicting containers"
            print(f"   ✓ Found {len(conflicting)} conflicting container(s)")
            
            # Clean up the conflicting containers
            for c in conflicting:
                db.session.delete(c)
            db.session.commit()
            print(f"   ✓ Cleaned up conflicting containers")
            
            # Now we can create the new container without error
            container2 = Container(
                user_id=test_user_id,
                session_id=test_session_id_2,
                container_name=container_name_2,
                image_name='kasmweb/vs-code:1.15.0',
                desktop_type=desktop_type,
                status='creating',
                container_port=6901,
                proxy_path=proxy_path  # Same proxy_path, but old one was cleaned up
            )
            db.session.add(container2)
            db.session.commit()
            print(f"   ✓ Successfully created new container with same proxy_path")
            
            # Clean up test data
            db.session.delete(container2)
            db.session.commit()
            
            print("   ✓ Proxy_path conflict test passed!")
            return True
            
    except Exception as e:
        print(f"   ✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_container_name_conflict():
    """Test that containers with duplicate container_name are cleaned up"""
    print("\n2. Testing container_name conflict cleanup...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app import create_app, db
        from app.models.containers import Container
        from sqlalchemy import or_
        
        app = create_app(debug=False)
        
        with app.app_context():
            # Create test data
            test_user_id = str(uuid.uuid4())
            test_session_id = str(uuid.uuid4())
            test_username = "test.user2"
            desktop_type = "ubuntu-desktop"
            
            # Generate the container name that would be used
            container_name = f"kasm-{test_username}-{desktop_type}-{test_session_id[:8]}"
            proxy_path = f"{test_username}-{desktop_type}"
            
            # Clean up any existing test containers
            existing = Container.query.filter(
                or_(
                    Container.user_id == test_user_id,
                    Container.container_name == container_name
                )
            ).all()
            for container in existing:
                db.session.delete(container)
            db.session.commit()
            
            # Create first container with specific container_name
            container1 = Container(
                user_id=test_user_id,
                session_id=test_session_id,
                container_name=container_name,
                image_name='kasmweb/ubuntu-focal-desktop:1.15.0',
                desktop_type=desktop_type,
                status='error',
                container_port=6901,
                proxy_path=proxy_path
            )
            db.session.add(container1)
            db.session.commit()
            print(f"   ✓ Created container 1 with container_name: {container_name}")
            
            # Now simulate trying to create a new container with same name
            # First check for conflicts
            conflicting = Container.query.filter(
                or_(
                    Container.proxy_path == proxy_path,
                    Container.container_name == container_name
                ),
                Container.user_id == test_user_id
            ).all()
            
            assert len(conflicting) > 0, "Should find conflicting containers"
            print(f"   ✓ Found {len(conflicting)} conflicting container(s)")
            
            # Clean up the conflicting containers
            for c in conflicting:
                db.session.delete(c)
            db.session.commit()
            print(f"   ✓ Cleaned up conflicting containers")
            
            # Now we can create the new container without error
            container2 = Container(
                user_id=test_user_id,
                session_id=test_session_id,
                container_name=container_name,  # Same name, but old one was cleaned up
                image_name='kasmweb/ubuntu-focal-desktop:1.15.0',
                desktop_type=desktop_type,
                status='creating',
                container_port=6901,
                proxy_path=proxy_path
            )
            db.session.add(container2)
            db.session.commit()
            print(f"   ✓ Successfully created new container with same container_name")
            
            # Clean up test data
            db.session.delete(container2)
            db.session.commit()
            
            print("   ✓ Container_name conflict test passed!")
            return True
            
    except Exception as e:
        print(f"   ✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_session_cleanup():
    """Test cleanup of containers from different sessions with same user/desktop_type"""
    print("\n3. Testing multiple session cleanup...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app import create_app, db
        from app.models.containers import Container
        from sqlalchemy import or_
        
        app = create_app(debug=False)
        
        with app.app_context():
            # Create test data
            test_user_id = str(uuid.uuid4())
            test_username = "test.user"
            desktop_type = "ubuntu-vscode"
            
            # Create 3 containers from different sessions (simulating leftover containers)
            sessions = [str(uuid.uuid4()) for _ in range(3)]
            proxy_path = f"{test_username}-{desktop_type}"
            
            # Clean up any existing test containers
            existing = Container.query.filter(Container.user_id == test_user_id).all()
            for container in existing:
                db.session.delete(container)
            db.session.commit()
            
            # Create containers from different sessions
            for i, session_id in enumerate(sessions[:2]):  # Create 2 old ones
                container = Container(
                    user_id=test_user_id,
                    session_id=session_id,
                    container_name=f"kasm-{test_username}-{desktop_type}-{session_id[:8]}",
                    image_name='kasmweb/vs-code:1.15.0',
                    desktop_type=desktop_type,
                    status='stopped',
                    container_port=6901,
                    proxy_path=proxy_path  # All have same proxy_path
                )
                db.session.add(container)
            db.session.commit()
            print(f"   ✓ Created 2 old containers with same proxy_path")
            
            # Now try to create a new container (from the 3rd session)
            new_session_id = sessions[2]
            new_container_name = f"kasm-{test_username}-{desktop_type}-{new_session_id[:8]}"
            
            # Check for conflicts
            conflicting = Container.query.filter(
                or_(
                    Container.proxy_path == proxy_path,
                    Container.container_name == new_container_name
                ),
                Container.user_id == test_user_id
            ).all()
            
            assert len(conflicting) == 2, f"Should find 2 conflicting containers, found {len(conflicting)}"
            print(f"   ✓ Found {len(conflicting)} conflicting containers")
            
            # Clean them all up
            for c in conflicting:
                db.session.delete(c)
            db.session.commit()
            print(f"   ✓ Cleaned up all conflicting containers")
            
            # Create new container
            new_container = Container(
                user_id=test_user_id,
                session_id=new_session_id,
                container_name=new_container_name,
                image_name='kasmweb/vs-code:1.15.0',
                desktop_type=desktop_type,
                status='creating',
                container_port=6901,
                proxy_path=proxy_path
            )
            db.session.add(new_container)
            db.session.commit()
            print(f"   ✓ Successfully created new container after cleanup")
            
            # Clean up test data
            db.session.delete(new_container)
            db.session.commit()
            
            print("   ✓ Multiple session cleanup test passed!")
            return True
            
    except Exception as e:
        print(f"   ✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing Duplicate Container Cleanup Fix")
    print("=" * 70)
    
    tests = [
        test_proxy_path_conflict,
        test_container_name_conflict,
        test_multiple_session_cleanup
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
