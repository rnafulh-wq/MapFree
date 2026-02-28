"""Legacy CLI entry: python -m cli.main <image_path> <project_path>."""
import logging
import sys

from mapfree.api.controller import MapFreeController
from mapfree.profiles.mx150 import MX150_PROFILE

logger = logging.getLogger("mapfree.cli.legacy")


def _emit_event(event):
    if event.type == "step":
        logger.info("[%d%%] %s", int(event.progress * 100), event.message)
    elif event.type == "complete":
        logger.info("DONE: %s", event.message)
    elif event.type == "error":
        logger.error("ERROR: %s", event.message)
    else:
        if event.message:
            logger.info("%s", event.message)


def main():
    if len(sys.argv) < 3:
        logger.error("Usage: python -m cli.main <image_path> <project_path>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    controller = MapFreeController(MX150_PROFILE)
    controller.run_project(sys.argv[1], sys.argv[2], _emit_event)


if __name__ == "__main__":
    main()
