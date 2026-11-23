"""Run EiVORAK locally."""

import logging

from .app import create_app
from .config import load_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    app = create_app(settings)
    app.run(port=settings.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
