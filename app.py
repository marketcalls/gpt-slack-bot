from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from dotenv import load_dotenv
from threading import Thread
import re
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize Slack client
slack_token = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# Get BOT_USER_ID from environment variables
BOT_USER_ID = os.getenv('BOT_USER_ID')

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
model = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key)

# Create an in-memory chat history store
store = {}
last_activity = {}
SESSION_TIMEOUT = timedelta(minutes=30)  # Set session timeout to 30 minutes

def get_session_history(session_id: str):
    current_time = datetime.now()
    if session_id not in store or current_time - last_activity.get(session_id, current_time) > SESSION_TIMEOUT:
        store[session_id] = InMemoryChatMessageHistory()
    last_activity[session_id] = current_time
    return store[session_id]

# Create a prompt template for the chatbot
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Answer all questions to the best of your ability. Format your responses using Slack's markdown syntax: *bold* for bold, _italic_ for italic, `code` for code, and use • for bullet points."),
    MessagesPlaceholder(variable_name="messages")
])

# Combine the model with the prompt and message history
chain = prompt | model

with_message_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="messages"
)

processed_ids = set()

def format_for_slack(text):
    # Replace ### with *bold* for headers
    text = re.sub(r'###\s*(.*)', r'*\1*', text)
    
    # Replace bullet points (assuming they start with '- ')
    text = re.sub(r'^-\s', '• ', text, flags=re.MULTILINE)
    
    # Replace **bold** with *bold* for Slack
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # Remove any remaining Markdown syntax that Slack doesn't support
    text = re.sub(r'[#_`]', '', text)
    
    return text

def handle_event_async(data):
    thread = Thread(target=handle_event, args=(data,), daemon=True)
    thread.start()

def handle_event(data):
    event = data["event"]
    
    if "text" in event and event["type"] == "message" and event.get("subtype") is None:
        # Ignore messages from the bot itself
        if event.get("user") == BOT_USER_ID:
            return

        # Handle direct message or app mention
        if event["channel"].startswith('D') or event.get("channel_type") == 'im' or event["type"] == "app_mention":
            current_time = datetime.now().strftime("%Y%m%d%H%M")
            session_id = f"{event['channel']}_{event['user']}_{current_time}"
            
            # Print the user's message to the console
            print(f"User ({event['user']} in {event['channel']}): {event['text']}")
            print(f"Session ID: {session_id}")
            
            try:
                # Stream response from the model
                response_text = ""
                for r in with_message_history.stream(
                    {"messages": [HumanMessage(content=event["text"])]},
                    config={"configurable": {"session_id": session_id}}
                ):
                    response_text += r.content

                # Format the response for Slack
                formatted_response = format_for_slack(response_text)

                # Print the bot's response to the console
                print(f"Bot (before formatting): {response_text}")
                print(f"Bot (after formatting): {formatted_response}")

                # Send the formatted response back to Slack
                response = client.chat_postMessage(
                    channel=event["channel"],
                    text=formatted_response,
                    mrkdwn=True
                )
                
                if event["type"] == "app_mention":
                    processed_ids.add(event.get("client_msg_id"))
            except SlackApiError as e:
                print(f"Error posting message: {e.response['error']}")

@app.route('/gpt4mini', methods=['GET'])
def helloworld():
    if request.method == 'GET':
        return "Hello, I'm the GPT-4-mini Slack bot!"

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data:
        handle_event_async(data)
    
    return "", 200

if __name__ == "__main__":
    app.run(debug=True)