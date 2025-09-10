#!/bin/bash

GREEN='\033[32m'
YELLOW='\033[33m'
NC='\033[0m'

if [ "$(basename "$PWD")" != "faq-bot" ]; then
    echo "Please run this script from the root of the faq-bot directory."
    exit 1
fi

echo -e "${GREEN}Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created.${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
fi

source venv/bin/activate

echo -e "${GREEN}Installing python packages...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}Installing npm packages...${NC}"
npm install

echo -e "${GREEN}Setting up database...${NC}"
sqlite3 database.db <<EOF
CREATE TABLE IF NOT EXISTS faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global BOOLEAN NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faq_channels (
    faq_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (faq_id, channel_id),
    FOREIGN KEY (faq_id) REFERENCES faqs (id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS faq_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global BOOLEAN NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faq_pending_channels (
    faq_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (faq_id, channel_id),
    FOREIGN KEY (faq_id) REFERENCES faq_pending (id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS faq_rejected (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global BOOLEAN NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_by TEXT NOT NULL,
    rejected_by TEXT NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS faq_rejected_channels (
    faq_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (faq_id, channel_id),
    FOREIGN KEY (faq_id) REFERENCES faq_rejected (id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS reviewers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    admin BOOL NOT NULL
);
EOF

if [ ! -d logs ]; then
    echo -e "${GREEN}Creating logs directory...${NC}"
    mkdir logs
else
    echo -e "${YELLOW}Logs directory already exists.${NC}"
fi

if [ ! -f .env ]; then
    cat << EOF > .env
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
PORT=
DATABASE_PATH=$(realpath database.db)
ADMIN_ID=
FAQ_SUBMISSION_REVIEW_CHANNEL=
EOF
    echo -e "${GREEN}Created .env file.${NC}"
    echo -e "${YELLOW}Add your credentials/secrets into the .env file.${NC}"
else
    echo -e "${YELLOW}.env file already exists.${NC}"
fi
