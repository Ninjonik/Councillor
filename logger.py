"""
Logging utility with timestamps and colors
"""
import sys
from datetime import datetime
from enum import Enum

class LogLevel(Enum):
    DEBUG = ("DEBUG", "\033[36m")    # Cyan
    INFO = ("INFO", "\033[32m")      # Green
    WARNING = ("WARNING", "\033[33m") # Yellow
    ERROR = ("ERROR", "\033[31m")    # Red
    SUCCESS = ("SUCCESS", "\033[92m") # Bright Green

class Logger:
    """Simple colored logger with timestamps"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    @staticmethod
    def _format_message(level: LogLevel, message: str) -> str:
        """Format message with timestamp and color"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name, color = level.value

        # Format: [2025-10-18 14:30:45] INFO: Message
        return f"{Logger.DIM}[{timestamp}]{Logger.RESET} {color}{Logger.BOLD}{level_name}{Logger.RESET}: {message}"

    @staticmethod
    def debug(message: str):
        """Log debug message (cyan)"""
        print(Logger._format_message(LogLevel.DEBUG, message))

    @staticmethod
    def info(message: str):
        """Log info message (green)"""
        print(Logger._format_message(LogLevel.INFO, message))

    @staticmethod
    def warning(message: str):
        """Log warning message (yellow)"""
        print(Logger._format_message(LogLevel.WARNING, message))

    @staticmethod
    def error(message: str):
        """Log error message (red)"""
        print(Logger._format_message(LogLevel.ERROR, message), file=sys.stderr)

    @staticmethod
    def success(message: str):
        """Log success message (bright green)"""
        print(Logger._format_message(LogLevel.SUCCESS, message))

# Convenience aliases
log = Logger()

