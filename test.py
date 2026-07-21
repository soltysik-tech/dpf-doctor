#!/usr/bin/env python3
"""Discover and run the unittest suite under tests/."""
import sys
import unittest


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", top_level_dir=".")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
