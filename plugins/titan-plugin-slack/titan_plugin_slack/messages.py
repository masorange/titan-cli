class Messages:
    class Plugin:
        SLACK_CLIENT_NOT_AVAILABLE: str = (
            "SlackPlugin not initialized. Slack client may not be available."
        )

    class Slack:
        CLIENT_REQUIRES_BOT_TOKEN: str = "Slack client requires a bot token."


msg = Messages()
