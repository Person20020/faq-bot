#!/bin/bash

source .env

if [ "$(basename "$PWD")" != "faq-bot" ]; then
    echo "Please run this script from the root of the faq-bot directory."
    exit 1
fi

source ./venv/bin/activate

gunicorn -w 2 \
    -b 127.0.0.1:"$PORT" \
    --access-logfile ./logs/access.log \
    --error-logfile ./logs/error.log \
    app:app 