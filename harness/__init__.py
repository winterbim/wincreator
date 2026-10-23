"""Harness Engineering Runtime for WinCreator (G01).

The runtime owns task state, proof persistence and crash-safe resume. It never
re-implements capture, attestation or review: those stay in the WinCreator
proof kernel under ``skill/wincreator/scripts``.
"""

RUNTIME_VERSION = "0.1.0"
EVENT_SCHEMA = "wincreator.harness.event/v1"
