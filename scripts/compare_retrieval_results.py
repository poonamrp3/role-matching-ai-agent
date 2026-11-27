#!/usr/bin/env python3
"""Create an HTML comparison from baseline and structured workflow JSON files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from role_matching.tools.retrieval_comparison import main


if __name__ == "__main__":
    main()
