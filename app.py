"""Top-level app shim.

The real Streamlit app lives at `backend.app`. This shim keeps the
previous invocation `streamlit run app.py` working while the project
is reorganized into team folders.
"""

import os

# Streamlit requires the main script to contain the UI execution code.
# Simply importing the module will cache it in sys.modules and prevent UI
# updates, causing a blank screen or broken interactivity.
# We execute the file directly to preserve the `streamlit run app.py` entrypoint.

backend_app_path = os.path.join(os.path.dirname(__file__), "backend", "app.py")
g = globals()
g["__file__"] = backend_app_path
with open(backend_app_path) as f:
    exec(f.read(), g)
