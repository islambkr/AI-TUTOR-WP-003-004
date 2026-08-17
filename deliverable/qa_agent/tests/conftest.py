"""Make graph_service.py importable from the tests folder.

pytest does not add the parent directory to sys.path on its own, so this file
does it. conftest.py is loaded automatically before any test runs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
