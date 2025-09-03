from dotenv import load_dotenv
from flask import Flask, request, jsonify
import os
import slackeventsapi
from slack_sdk import WebClient
import sqlite3


load_dotenv()

app = Flask(__name__)

slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
if not slack_bot_token:
    raise ValueError("SLACK_BOT_TOKEN environment variable is not set.")

slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
if not slack_signing_secret:
    raise ValueError("SLACK_SIGNING_SECRET environment variable is not set.")

slack_client = WebClient(token=slack_bot_token)
slack_events_adapter = slackeventsapi.SlackEventAdapter(slack_signing_secret, "/slack/events", app)


@app.route("/")
def index():
    return "Hello, this is the FAQ Bot! Check it out in Slack."


@app.route("/slack/command", methods=["POST"])
def slack_command():
    data = request.form
    user_id = data.get("user_id")
    command_text = data.get("text")

    return "", 200


@slack_events_adapter.on("app_mention")
def handle_app_mention(event_data):
    channel_id = event_data["event"]["channel"]
    timestamp = event_data["event"]["ts"]

    slack_client.reactions_add(
        channel=channel_id,
        name="hyper-dino-wave",
        timestamp=timestamp
    )

    return "", 200


if __name__ == "__main__":
    app.run(port=os.getenv("PORT", 5000))
