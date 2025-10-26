"""
Legacy presets.py - Deprecated
This file is kept for backward compatibility during migration.
All functionality has been moved to the utils/ package.
"""

# This file is deprecated - DO NOT USE
# All functionality has been moved to:
# - utils/database.py - Database operations
# - utils/enums.py - Enumerations
# - utils/errors.py - Error handling
# - utils/formatting.py - Discord formatting
# - utils/helpers.py - Helper functions
# - utils/permissions.py - Permission checking

import warnings
warnings.warn(
    "presets.py is deprecated. Use the utils package instead.",
    DeprecationWarning,
    stacklevel=2
)

