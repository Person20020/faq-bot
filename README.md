# FAQ Bot

This Slack bot helps you quickly access frequently asked questions. By running the command, it will output the answer to the section that you trigger.

## Commands

**Command:** Run `/faq` command followed by the `trigger` word. For example: `/faq about`.

## Configuration 

The bot fetches FAQ data from JSON configuration files stored in the config directory of this repository. Each channel gets its own dedicated FAQ file. These files contain a list of questions, each with a `trigger` word and a corresponding `answer`. Optionally, each entry can also include the full `question` text.

The file for the channel is named with the channel ID. For easy reading, they should have a comments section with the channel name.

### Example:
```json
{
  "comments": [
    {
      "channel": "#channel-name"
    }
  ],
  "questions": [
    {
      "trigger": "Trigger",
      "question: "Question",
      "answer": "Answer"
    },
    ... more questions
  ]
}
```
* `trigger`: The keyword(s) users will type after `/faq` to find this answer. Keep these concise and relevant.
* `question` (optional): The full question being asked. If provided, this will be displayed along with the answer.
* `answer`: The detailed answer to the question.
