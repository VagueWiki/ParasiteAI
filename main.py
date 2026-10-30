"""
ParasiteAI - Top-level Application Entry Point.
Delegates to parasite_ai.main:main().
"""
from __future__ import annotations

import sys
from parasite_ai.main import main

if __name__ == "__main__":
    sys.exit(main())
