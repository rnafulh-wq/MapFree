"""Entry point for python -m mapfree.cli (avoids runpy warning when using mapfree.cli.main)."""
if __name__ == "__main__":
    from mapfree.cli.main import main
    main()
