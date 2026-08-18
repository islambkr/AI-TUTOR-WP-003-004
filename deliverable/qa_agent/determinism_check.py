"""determinism_check.py -- prove the graph service is reproducible across processes.

The unit tests check that repeated calls agree within one process. That cannot
catch anything that varies per interpreter, such as hash-based set ordering, so
this runs the same calls in several fresh subprocesses and compares a digest.

Run it:  .venv/bin/python determinism_check.py
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
RUNS = 3

SNIPPET = """
import hashlib, json, graph_service as gs
payload = {
    "classes": gs.list_classes(),
    "methods": gs.list_entities_by_type("Method"),
    "found": gs.find_entity("abstract"),
    "described": gs.describe_entity("Encapsulation"),
    "relations": gs.get_relations("__repr__"),
    "named": gs.get_relations_by_name("Encapsulation", "hasPart"),
    "deps": gs.get_dependencies("Data Hiding", transitive=True),
    "path": gs.find_path("Class", "Data Hiding"),
}
blob = json.dumps(payload, sort_keys=True)
print(hashlib.md5(blob.encode()).hexdigest(), len(blob))
"""

digests = []
for run in range(RUNS):
    result = subprocess.run(
        [sys.executable, "-c", SNIPPET],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    )
    digest, size = result.stdout.split()
    digests.append(digest)
    print(f"  run {run + 1}: {digest}  ({size} bytes)")

if len(set(digests)) == 1:
    print(f"\nPASS -- identical output across {RUNS} separate processes")
else:
    print(f"\nFAIL -- {len(set(digests))} different results")
    sys.exit(1)
