"""Deprecated import shim. Use `stillpoint`."""
from stillpoint import *  # noqa: F401,F403
import warnings
warnings.warn("package name 'steelpoint' is deprecated; import stillpoint", DeprecationWarning, stacklevel=2)
