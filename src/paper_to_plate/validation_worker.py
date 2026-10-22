"""Executed by the configured interpreter with its installed CubOS package.

This worker never calls connect, execute, run_on_hardware, or any instrument.
"""
import contextlib
import io
import json
import sys

from cubos.protocol_engine.setup_validator import run_setup_validation

output = io.StringIO()
with contextlib.redirect_stdout(output):
    result = run_setup_validation(*sys.argv[1:])
print(json.dumps({"passed": result.passed, "stage": result.stage, "errors": list(result.errors), "output": result.output, "mode": "offline", "hardware_contacted": False}))
