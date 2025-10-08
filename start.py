#!/usr/bin/env python3
"""
Simple Production Starter Script
Just run: python start.py
"""

import os
import sys
import subprocess
import secrets

def install_dependencies():
    """Install required dependencies"""
    print("📦 Checking dependencies...")
    try:
        import fastapi
        import uvicorn
        import yfinance
        import pandas
        print("✅ Dependencies already installed\n")
    except ImportError:
        print("📦 Installing dependencies... This may take a few minutes.")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])
        print("✅ Dependencies installed\n")

def set_environment():
    """Set production environment variables"""
    os.environ["APP_ENV"] = "production"
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = "8000"
    os.environ["DEBUG"] = "False"
    os.environ["ALLOWED_HOSTS"] = "*"
    os.environ["CORS_ORIGINS"] = "*"
    
    # Generate secret key if not set
    if "SECRET_KEY" not in os.environ:
        os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)

def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "YOUR_IP"

def main():
    """Main starter function"""
    print("=" * 80)
    print("🚀 Smart Option Trading Analytics - Production Starter")
    print("=" * 80)
    print()
    
    # Install dependencies
    install_dependencies()
    
    # Set environment
    set_environment()
    
    # Get IP
    local_ip = get_local_ip()
    
    # Display access info
    print("🌐 Server will be accessible at:")
    print(f"   • Local:    http://localhost:8000")
    print(f"   • Network:  http://{local_ip}:8000")
    print(f"   • External: http://YOUR_PUBLIC_IP:8000 (if port forwarded)")
    print()
    print("🔐 Demo Login:")
    print("   • Email:    demo@example.com")
    print("   • Password: demo123")
    print()
    print("✅ Production Features:")
    print("   • Full Profile Access")
    print("   • Unlimited Analysis")
    print("   • All Valuation Models")
    print("   • CSV Export")
    print("   • Multi-worker (4 workers)")
    print()
    print("=" * 80)
    print()
    print("Starting server... Press Ctrl+C to stop")
    print()
    
    # Import and run
    try:
        import app
        # The app.py will handle the rest
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped. Thank you for using Option Analytics!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the correct directory")
        print("2. Check if port 8000 is available")
        print("3. Ensure Python 3.8+ is installed")
        print("\nFor help, see QUICK_START.md")
        sys.exit(1)

if __name__ == "__main__":
    main()

