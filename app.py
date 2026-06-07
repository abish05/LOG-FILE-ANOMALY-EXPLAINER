"""Top-level app shim.

The real Streamlit app lives at `backend.app`. This shim keeps the
previous invocation `streamlit run app.py` working while the project
is reorganized into team folders.
"""

from backend.app import *

