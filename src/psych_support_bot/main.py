from psych_support_bot.app import create_app


def main() -> None:
    app = create_app()
    print(f"App ready: {app.title}")
