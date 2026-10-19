"""Standalone entry point for the packaged Karmed Export app.

Double-clicking the built executable runs this: it starts the local server and
opens the browser. No Python install required on the target machine.
"""
from karmed.web import main

if __name__ == "__main__":
    main()
