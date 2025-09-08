# FAQ Bot

A simple FAQ bot that allows people to submit new questions/answers and allows responding to frequently asked questions with a detailed answer.

## Usage

### Commands

`/add-faq` Opens a modal window where you can submit a new FAQ.

### Message Shortcuts

`Trigger FAQ` Open a modal window where you can select the response to the message you ran the shortcut on.

`faq_bot_test` Make the bot wave. (Just a test to make sure it is running.)

## Getting Started

1. Clone the repository:
    ```bash
    git clone https://github.com/Person20020/faq-bot.git
    cd faq-bot
    ```
2. Run setup script:
    ```bash
    ./setup.sh
    ```
3. Fill in .env
4. Run the bot:
    ```bash
    . ./venv/bin/activate
    python app.py
    ```