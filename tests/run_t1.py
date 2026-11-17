"""T1 runner: discover and run all plain-interpreter unit tests."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    loader = unittest.TestLoader()
    suite = loader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
