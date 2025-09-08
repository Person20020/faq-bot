import copy
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import os
import slackeventsapi
from slack_sdk import WebClient
import sqlite3
import warnings


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

slack_api_app_id = os.getenv("SLACK_API_APP_ID")
if not slack_api_app_id:
    warnings.warn("SLACK_API_APP_ID environment variable is not set.")


# Database
db_path = os.getenv("DATABASE_PATH")
if not db_path:
    raise ValueError("DATABASE_PATH environment variable is not set.")

# Test database connection
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
except sqlite3.Error as e:
    raise ValueError(f"Failed to connect to database: {e}")
finally:
    conn.close()


admin = os.getenv("ADMIN_ID")
if not admin:
    raise ValueError("ADMIN_ID environment variable is not set.")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM reviewers")

    rows = cursor.fetchall()

    for row in rows:
        if row[0] == admin:
            db_configured_admin = True
            break
    else:
        db_configured_admin = False

    if not db_configured_admin:
        cursor.execute("INSERT INTO reviewers (user_id, admin) VALUES (?, ?)", (admin, True))
        conn.commit()
        print(f"Admin user {admin} added to reviewers table.")

except sqlite3.Error as e:
    raise ValueError(f"Error connecting to database: {e}")
finally:
    conn.close()


review_channel_id = os.getenv("FAQ_SUBMISSION_REVIEW_CHANNEL")
if not review_channel_id:
    raise ValueError("FAQ_SUBMISSION_REVIEW_CHANNEL environment variable is not set.")


with open("faq-submission.json", "r") as f:
    faq_submission_view = json.load(f)

with open("faq-trigger-form.json", "r") as f:
    faq_trigger_form = json.load(f)

@app.route("/")
def index():
    return "Hello, this is the FAQ Bot! Check it out in Slack."


@app.route("/slack/command", methods=["POST"])
def slack_command():
    data = request.form
    command = data.get("command")
    user_id = data.get("user_id")
    command_text = data.get("text")
    
    if command == "/add-faq":
        trigger_id = data.get("trigger_id")
        slack_client.views_open(
            view=faq_submission_view,
            trigger_id=trigger_id
        )
    
    elif command == "/add-faq-reviewer":
        if user_id != admin:
            return jsonify({"response_type": "ephemeral", "text": "You are not allowed to use this command."}), 200
        
        if command_text.startswith("<@") and command_text.endswith(">"):
            new_reviewer_id = command_text[2:-1]
        else:
            return jsonify({"response_type": "ephemeral", "text": "The command text must be just a mention of the user."}), 200

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO reviewers (user_id, admin) VALUES (?, ?)", (new_reviewer_id, False))
            conn.commit()
        except sqlite3.Error as e:
            raise ValueError(f"Error connecting to database: {e}")
        finally:
            conn.close()

    return "", 200

@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():

    payload = json.loads(request.form["payload"])

    if payload.get("type") == "message_action":
        trigger_id = payload.get("trigger_id")
        callback_id = payload.get("callback_id")
        
        if callback_id == "faq_bot_test":
            channel_id = payload["channel"]["id"]
            user_id = payload["user"]["id"]
            slack_client.chat_postMessage(
                channel=channel_id,
                text=f":hyper-dino-wave: <@{user_id}>"
            )
            return "", 200

        # User opens the FAQ response trigger form
        elif callback_id == "faq_trigger_form_open":
            channel_id = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            resp = slack_client.views_open(
                view=generate_faq_form(channel_id, message_ts),
                trigger_id=trigger_id
            )

            print("views_open response:", resp)

        else:
            return "", 200


    elif payload.get("type") == "view_submission":
        user_id = payload["user"]["id"]
        callback_id = payload.get("view").get("callback_id")

        # User submits a new FAQ
        if callback_id == "faq_submission":
            values = payload["view"]["state"]["values"]
            is_global = values["global_block"]["global"]["selected_option"]["value"] == "1"
            question = values["question_block"]["question"]["value"]
            answer = values["answer_block"]["answer"]["value"]

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO faq_pending (global, question, answer, created_by)
                    VALUES (?, ?, ?, ?)
                """, (is_global, question, answer, user_id))
                
                faq_id = cursor.lastrowid

                if not is_global:
                    channels = values["channel_block"]["channels"]["selected_channels"]
                    
                    for channel_id in channels:
                        cursor.execute("""
                            INSERT INTO faq_pending_channels (faq_id, channel_id)
                            VALUES (?, ?)
                        """, (faq_id, channel_id))

                conn.commit()

            except sqlite3.Error as e:
                raise ValueError(f"Failed to insert FAQ into database: {e}")
            finally:
                cursor.close()
                conn.close()

            
            slack_client.chat_postMessage(
                channel=review_channel_id,
                text="New FAQ submitted.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"New FAQ submitted by <@{user_id}>.\n"
                                f"Global: `{is_global}`"
                                + (
                                    f"\nFor the following channels:\n{', '.join(f'<#{channel_id}>' for channel_id in channels)}."
                                    if not is_global else ""
                                )
                                + f"\n*Question:*\n```{question}```\n*Answer:*\n```{answer}```"
                            )
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                                "value": str(faq_id),
                                "action_id": "approve_faq"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": ":x: Reject"},
                                "value": str(faq_id),
                                "action_id": "reject_faq"
                            }
                        ]
                    }
                ]
            )
            
            return "", 200


        # User submits the FAQ response trigger form
        elif callback_id == "faq_trigger_form_submitted":
            private_metadata = json.loads(payload["view"]["private_metadata"])
            channel_id = private_metadata["channel_id"]
            message_ts = private_metadata["message_ts"]
            values = payload["view"]["state"]["values"]
            faq_id = values["faq_selection_block"]["faq_selection"]["selected_option"]["value"]

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT question, answer FROM faqs WHERE id = ?", (faq_id,))
            faq = cursor.fetchone()
            conn.close()

            slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=f"<@{user_id}> has triggered a FAQ response.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Question:*\n```{faq[0]}```\n*Answer:*\n```{faq[1]}```"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"I am a bot. This response triggered by <@{user_id}>"
                            }
                        ]
                    }
                ]
            )
            return "", 200


    elif payload.get("type") == "block_actions":

        if payload["api_app_id"] != slack_api_app_id:
            return "", 200 # Faked request
        
        # Transfer faq from pending to normal
        actions = payload.get("actions")
        if actions and actions[0]["action_id"] == "approve_faq":
            # Move to main table
            pending_faq_id = payload["actions"][0]["value"]
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT global, question, answer, created_by FROM faq_pending WHERE id = ?", (pending_faq_id,))
            faq = cursor.fetchone()
            if faq:
                # Get channels
                cursor.execute("SELECT channel_id FROM faq_pending_channels WHERE faq_id = ?", (pending_faq_id,))
                channel_ids = cursor.fetchall()
                
                # Add the faq into the approved table
                cursor.execute("INSERT INTO faqs (global, question, answer, created_by) VALUES (?, ?, ?, ?)", faq)
                new_faq_id = cursor.lastrowid

                # Map channels to the new FAQ
                for (channel_id,) in channel_ids:
                    cursor.execute("INSERT INTO faq_channels (faq_id, channel_id) VALUES (?, ?)", (new_faq_id, channel_id))

                cursor.execute("DELETE FROM faq_pending WHERE id = ?", (payload["actions"][0]["value"],))
                cursor.execute("DELETE FROM faq_pending_channels WHERE faq_id = ?", (pending_faq_id,))
            conn.commit()
            conn.close()

            reviewer_id = payload["user"]["id"]
            is_global = faq[0]
            question = faq[1]
            answer = faq[2]
            user_id = faq[3]
            channels = [channel_id for (channel_id,) in channel_ids]

            slack_client.chat_update(
                channel=review_channel_id,
                ts=payload["message"]["ts"],
                text="New FAQ submitted.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"New FAQ submitted by <@{user_id}>.\n"
                                f"Global: `{is_global}`"
                                + (
                                    f"\nFor the following channels:\n{', '.join(f'<#{channel_id}>' for channel_id in channels)}."
                                    if not is_global else ""
                                )
                                + f"\n*Question:*\n```{question}```\n*Answer:*\n```{answer}```"
                            )
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":white_check_mark: Approved by <@{reviewer_id}>"
                            }
                        ]
                    }
                ]
            )

            return "", 200


        elif actions and actions[0]["action_id"] == "reject_faq":
            # Move to rejected table
            pending_faq_id = payload["actions"][0]["value"]
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT global, question, answer, created_by FROM faq_pending WHERE id = ?", (pending_faq_id,))
            faq = cursor.fetchone()
            if faq:
                # Get channels
                cursor.execute("SELECT channel_id FROM faq_pending_channels WHERE faq_id = ?", (pending_faq_id,))
                channel_ids = cursor.fetchall()
                
                # Add the faq into the rejected table
                cursor.execute("INSERT INTO faq_rejected (global, question, answer, created_by, rejected_by, reason) VALUES (?, ?, ?, ?, ?, ?)", (faq[0], faq[1], faq[2], faq[3], payload["user"]["id"], "PLACEHOLDER REASON CHANGE THIS LATER"))# PLACEHOLDER REASON CHANGE THIS LATER WHEN ADDING REASON POPUP
                rejected_faq_id = cursor.lastrowid

                # Map channels to the new FAQ
                for (channel_id,) in channel_ids:
                    cursor.execute("INSERT INTO faq_rejected_channels (faq_id, channel_id) VALUES (?, ?)", (rejected_faq_id, channel_id))

                cursor.execute("DELETE FROM faq_pending WHERE id = ?", (payload["actions"][0]["value"],))
            conn.commit()
            conn.close()

            reviewer_id = payload["user"]["id"]
            is_global = faq[0]
            question = faq[1]
            answer = faq[2]
            user_id = faq[3]
            channels = [channel_id for (channel_id,) in channel_ids]

            slack_client.chat_update(
                channel=review_channel_id,
                ts=payload["message"]["ts"],
                text="New FAQ submitted.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"New FAQ submitted by <@{user_id}>.\n"
                                f"Global: `{is_global}`"
                                + (
                                    f"\nFor the following channels:\n{', '.join(f'<#{channel_id}>' for channel_id in channels)}."
                                    if not is_global else ""
                                )
                                + f"\n*Question:*\n```{question}```\n*Answer:*\n```{answer}```"
                            )
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":x: Rejected by <@{reviewer_id}>"
                            }
                        ]
                    }
                ]
            )

            return "", 200

        
    return "", 200


@app.route("/slack/external_options_load", methods=["POST"])
def slack_external_options_load():
    payload = json.loads(request.form["payload"])
    channel_id = json.loads(payload["view"]["private_metadata"])["channel_id"]

    options = get_faq_options(channel_id)
    return options, 200



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





def generate_faq_form(channel_id, message_ts):
    form = copy.deepcopy(faq_trigger_form)
    form["private_metadata"] = json.dumps({
        "channel_id": channel_id,
        "message_ts": message_ts
    })
    return form


def get_faq_options(channel_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT faqs.id, faqs.question 
        FROM faqs 
        LEFT JOIN faq_channels ON faqs.id = faq_channels.faq_id
        WHERE faqs.global = 1
        OR faq_channels.channel_id = ?
    """, (channel_id,))

    faqs = cursor.fetchall()

    options = []

    for row in faqs:
        options.append({
            "text": {
                "type": "plain_text",
                "text": (row[1][:72] + "...") if len(row[1]) > 75 else row[1]
            },
            "value": str(row[0])
        })

    return jsonify({"options": options})











if __name__ == "__main__":
    app.run(port=os.getenv("PORT", 5000))
