import pytest
import sys
import os

if __name__ == "__main__":
    # Add the current directory to sys.path so that main can be imported in tests
    sys.path.append(os.getcwd())
    
    print("Running all backend tests...")
    # Run pytest and capture results
    exit_code = pytest.main(["-v", "--tb=short", "tests/"])
    
    if exit_code == 0:
        print("\nAll tests passed successfully!")
    else:
        print(f"\nTests failed with exit code: {exit_code}")
    
    sys.exit(exit_code)
