import sys
from mapfree.api.controller import MapFreeController
from mapfree.profiles.mx150 import MX150_PROFILE


def print_event(event):
    if event.type == "step":
        print(f"[{int(event.progress*100)}%] {event.message}")
    elif event.type == "complete":
        print("DONE:", event.message)
    elif event.type == "error":
        print("ERROR:", event.message)
    else:
        print(event.message)


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m cli.main <image_path> <project_path>")
        sys.exit(1)

    controller = MapFreeController(MX150_PROFILE)
    controller.run_project(sys.argv[1], sys.argv[2], print_event)


if __name__ == "__main__":
    main()
