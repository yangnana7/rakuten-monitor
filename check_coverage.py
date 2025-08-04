#!/usr/bin/env python3
"""Coverage check script for local development"""

import subprocess
import sys
import os

def run_coverage():
    """Run tests with coverage and check if it meets requirements"""
    print("🧪 Running tests with coverage...")
    
    try:
        # Run pytest with coverage
        result = subprocess.run([
            'pytest', '-v', 
            '--cov=.', 
            '--cov-report=term-missing',
            '--cov-report=xml',
            '--cov-config=.coveragerc',
            '--cov-fail-under=70'
        ], capture_output=False, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print("\n✅ All tests passed and coverage requirements met!")
            print("📊 Coverage report saved to coverage.xml")
            return True
        else:
            print(f"\n❌ Tests failed or coverage below 70% (exit code: {result.returncode})")
            return False
            
    except FileNotFoundError:
        print("❌ pytest not found. Please install: pip install pytest pytest-cov")
        return False
    except Exception as e:
        print(f"❌ Error running coverage: {e}")
        return False

def show_coverage_summary():
    """Show coverage summary using coverage command"""
    try:
        print("\n📊 Coverage Summary:")
        subprocess.run(['coverage', 'report', '--show-missing'], check=False)
    except FileNotFoundError:
        print("Coverage command not found. Install with: pip install coverage")

if __name__ == "__main__":
    success = run_coverage()
    show_coverage_summary()
    
    print(f"\n{'='*50}")
    if success:
        print("🎉 Ready for CI! Coverage requirements met.")
        sys.exit(0)
    else:
        print("⚠️  Fix tests or improve coverage before pushing to CI.")
        sys.exit(1)