# SPDX-FileCopyrightText: 2026 SKBlacksmith (CrossNetwork)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Allow ``python -m esrgan_upscaler``."""

from .gui import main

if __name__ == "__main__":
    raise SystemExit(main())
