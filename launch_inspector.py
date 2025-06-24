#!/usr/bin/env python3
"""
🥪 Sandwich Inspector Launcher
=============================

Launch script for the Sandwich Inspector app with setup validation.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import streamlit
        import pandas
        import fitz  # PyMuPDF
        print("✅ Core dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements_inspector.txt")
        return False

def check_pbj_pipeline():
    """Check if PB&J pipeline is available"""
    pbj_path = Path("peanut_butter_jelly/src")
    if pbj_path.exists():
        print("✅ PB&J pipeline found")
        return True
    else:
        print("❌ PB&J pipeline not found")
        print("Please ensure the peanut_butter_jelly directory is present")
        return False

def check_api_keys():
    """Check if API keys are configured using PB&J config system"""
    try:
        # Add PB&J to path temporarily
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path("peanut_butter_jelly/src")))
        
        from pbj.config import create_config
        
        # Try to create config - this will validate API keys
        config = create_config()
        print("✅ API keys configured via PB&J config system")
        return True
        
    except ValueError as e:
        if "API key" in str(e):
            print("❌ API keys not configured")
            print("Configure your keys in peanut_butter_jelly/config.yaml or set environment variables")
            print("See README.md Step 4 for detailed instructions")
            return False
        else:
            print(f"⚠️ Config validation issue: {e}")
            return False
    except Exception as e:
        print(f"⚠️ Could not check API keys: {e}")
        print("The app will still launch but may need manual config verification")
        return False

def launch_app():
    """Launch the Streamlit app"""
    print("\n🚀 Launching Sandwich Inspector...")
    print("Opening browser at http://localhost:8501")
    print("Press Ctrl+C to stop the app")
    print("-" * 50)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "sandwich_inspector_app.py",
            "--server.headless", "false",
            "--server.address", "localhost",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n👋 Sandwich Inspector stopped")
    except Exception as e:
        print(f"\n❌ Error launching app: {e}")

def main():
    """Main launcher function"""
    print("🥪 Sandwich Inspector Setup Check")
    print("=" * 40)
    
    # Check all requirements
    checks_passed = 0
    total_checks = 3
    
    if check_requirements():
        checks_passed += 1
    
    if check_pbj_pipeline():
        checks_passed += 1
    
    if check_api_keys():
        checks_passed += 1
    
    print(f"\n📊 Setup Status: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed >= 2:  # Can run with just requirements and pipeline
        print("✅ Ready to launch!")
        
        # Ask user if they want to proceed
        try:
            response = input("\nPress Enter to launch the app (or 'q' to quit): ")
            if response.lower() != 'q':
                launch_app()
            else:
                print("👋 Goodbye!")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
    else:
        print("❌ Cannot launch - please fix the issues above")
        sys.exit(1)

if __name__ == "__main__":
    main() 