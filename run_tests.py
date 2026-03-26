import pytest
import sys

if __name__ == "__main__":
    with open("report_all_tests.txt", "w", encoding="utf-8") as f:
        sys.stdout = f
        sys.stderr = f
        pytest.main(["-v", "--tb=short", "tests/"])
