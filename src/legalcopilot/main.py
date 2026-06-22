"""LegalCoPilot v2 — application entry point."""

from legalcopilot.api.app import create_app

app = create_app()

if __name__ == "__main__":
    app.start()
