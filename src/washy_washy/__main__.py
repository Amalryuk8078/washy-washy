"""Local entrypoint: ``python -m washy_washy``.

Starts the ASGI application via Uvicorn. Does not duplicate application
construction — that lives entirely in ``washy_washy.main``.
"""

import uvicorn

from washy_washy.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "washy_washy.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
