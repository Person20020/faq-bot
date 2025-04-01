#!/bin/bash
source /home/person20020/faq-bot-venv/bin/activate
cd /home/person20020/faq-bot-venv/faq-bot
exec /home/person20020/faq-bot-venv/bin/gunicorn --workers 1 --bind 127.0.0.1:35227 app:app --access-logfile /home/person20020/faq-bot-venv/logs/access.log --error-logfile /home/person20020/faq-bot-venv/logs/error.log
