import os
import sys

# Must be set before ANY PyQt6 WebEngine imports
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")