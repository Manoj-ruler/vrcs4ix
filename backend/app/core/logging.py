import logging
import os


def configure_logging() -> None:
    """Single-line key=value logs; no request bodies or environment values are logged."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="ts=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
    )
