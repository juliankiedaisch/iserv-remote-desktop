#!/usr/bin/env python3
"""
Test script to verify the installation and basic functionality

This script tests:
1. Database connection
2. Flask app creation
3. Docker connection
4. Model imports
"""

import os
import sys

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from app import create_app, db
        from app.models.users import User
        from app.models.oauth_session import OAuthSession
        from app.models.containers import Container
        from app.services.docker_manager import DockerManager
        from app.routes.auth_routes import auth_bp
        from app.routes.container_routes import container_bp
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {str(e)}")
        return False

def test_env_variables():
    """Test that required environment variables are set"""
    print("\nTesting environment variables...")
    required_vars = [
        'SECRET_KEY',
        'DATABASE_URI',
        'OAUTH_CLIENT_ID',
        'OAUTH_CLIENT_SECRET',
        'OAUTH_AUTHORIZE_URL',
        'OAUTH_TOKEN_URL',
        'OAUTH_USERINFO_URL',
        'OAUTH_JWKS_URI',
        'OAUTH_REDIRECT_URI',
        'FRONTEND_URL',
        'ROLE_ADMIN',
        'ROLE_TEACHER'
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print(f"✗ Missing environment variables: {', '.join(missing)}")
        print("  Please set these in your .env file")
        return False
    else:
        print("✓ All required environment variables set")
        return True

def test_app_creation():
    """Test Flask app creation"""
    print("\nTesting Flask app creation...")
    try:
        from app import create_app
        app = create_app(os.environ.get('DEBUG', 'False') == 'True')
        print(f"✓ Flask app created successfully")
        print(f"  Registered blueprints: {[bp.name for bp in app.blueprints.values()]}")
        return True
    except Exception as e:
        print(f"✗ Failed to create Flask app: {str(e)}")
        return False

def test_database():
    """Test database connection"""
    print("\nTesting database connection...")
    try:
        from app import create_app, db
        app = create_app(os.environ.get('DEBUG', 'False') == 'True')
        with app.app_context():
            db.create_all()
            print("✓ Database connection successful")
            print(f"  Database URI: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'SQLite'}")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {str(e)}")
        return False

def test_docker():
    """Test Docker connection"""
    print("\nTesting Docker connection...")
    try:
        import docker
        client = docker.from_env()
        client.ping()
        
        # Check if Kasm image exists
        kasm_image = os.environ.get('KASM_IMAGE', 'kasmweb/ubuntu-focal-desktop:1.15.0')
        try:
            client.images.get(kasm_image)
            print(f"✓ Docker connection successful")
            print(f"  Kasm image '{kasm_image}' is available")
        except docker.errors.ImageNotFound:
            print(f"✓ Docker connection successful")
            print(f"⚠ Warning: Kasm image '{kasm_image}' not found")
            print(f"  Pull it with: docker pull {kasm_image}")
        
        return True
    except Exception as e:
        print(f"✗ Docker connection failed: {str(e)}")
        print("  Make sure Docker is installed and running")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("IServ Remote Desktop - Installation Test")
    print("=" * 60)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Environment variables loaded from .env\n")
    except:
        print("Warning: Could not load .env file\n")
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Environment Variables", test_env_variables()))
    results.append(("Flask App", test_app_creation()))
    results.append(("Database", test_database()))
    results.append(("Docker", test_docker()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<30} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your installation is ready.")
        return 0
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
