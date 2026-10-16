"""Allow ``python -m esrgan_upscaler``."""

from .gui import main

if __name__ == "__main__":
    raise SystemExit(main())
