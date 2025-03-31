import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, url_for, request
import os
import requests
import json
from slack_sdk import WebClient
from slackeventsapi import SlackEventAdapter


load_dotenv()

app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], '/slack/command', app)
client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
config_url = os.environ['CONFIG_URL']
person20020 = os.environ['PERSON20020']


def get_faqs(channel_id):
    url = f"{config_url}{channel_id}.json"
    try:
        request = requests.get(url)
        if request.status_code != 200:
            print(f"Error fetching FAQs: {request.status_code}")
            return False
        faq = json.loads(request.content)
        return faq
    except Exception as e:
        print(f"Error fetching FAQs: {e}")
        print(f"URL: {url}")
        return False

def get_answer(text, faq):
    global trigger_found
    try:
        for item in faq["questions"]:
            if item["trigger"] == text:
                trigger_found = True
                answer = item["answer"]
                return answer
        trigger_found = False
        print(f"Trigger word not found: {text}")
        return False
    except Exception as e:
        print(f"Error getting answer: {e}")
        return False
    
def get_question(text, faq):
    try:
        for item in faq["questions"]:
            if item["trigger"] == text:
                question = item["question"]
                return question
        return False
    except Exception as e:
        print(f"Error getting question: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/slack/command/faq', methods=['POST'])
def slack_command():
    data = request.form
    command = data.get('command')
    text = data.get('text')
    channel_id = data.get('channel_id')
    user_id = data.get('user_id')
    user = data.get('user_name')

    faq = get_faqs(channel_id)

    if not faq:
        response = {
            "response_type": "ephemeral",
            "text": f"Could not find the FAQ for this channel. If a FAQ configuration file for this channel doesn't exist, please create it by forking the GitHub repo for this app. If it does exist, please contact <@{person20020}>.",
        }
        return jsonify(response)
    
    if not text:
        response = {
            "response_type": "ephemeral",
            "text": f"Please provide a trigger word to search for in the FAQ.",
        }
        return jsonify(response)

    answer = get_answer(text, faq)

    if not trigger_found:
        response = {
            "response_type": "ephemeral",
            "text": f"The trigger word you used could not be found in the repository. You can add new responses by making a pull request to the repository, or if this trigger is already there, you can report this error to <@{person20020}>.",
        }
        return jsonify(response)
    
    if not answer:
        response = {
            "response_type": "ephemeral",
            "text": f"The answer for the trigger word you used could not be found in the repository. You can add new responses by making a pull request to the repository, or if this answer is already there, you can report this error to <@{person20020}>.",
        }
        return jsonify(response)
    
    question = get_question(text, faq)
    
    if not question:
        client.chat_postEphemeral(
            user=user_id,
            channel=channel_id,
            text=f"Could not find the question for the trigger word `{text}`. Please make sure it is in the section of the configuration file for this response.",
        )
        response = {
            "response_type": "in_channel",
            "text": f"`invoked by <@{user_id}>`\n*Answer:* \n{answer}",
        }
        return jsonify(response)
    else:
        response = {
            "response_type": "in_channel",
            "text": f"`invoked by <@{user_id}>`\n*Question:* \n{question}\n*Answer:* \n{answer}",
        }
        return jsonify(response)



if __name__ == '__main__':
    app.run(debug=True, port=5000)