from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from dotenv import load_dotenv
from threading import Thread
import re
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from tavily import TavilyClient

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize Slack client
slack_token = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# Get BOT_USER_ID from environment variables
BOT_USER_ID = os.getenv('BOT_USER_ID')

# Initialize OpenAI client (GPT-4o-mini)
openai_api_key = os.getenv("OPENAI_API_KEY")
model = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key)

# Tavily API Key
tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key)

# Create an in-memory chat history store
store = {}
last_activity = {}
SESSION_TIMEOUT = timedelta(minutes=30)

def get_session_history(session_id: str):
    current_time = datetime.now()
    if session_id not in store or current_time - last_activity.get(session_id, current_time) > SESSION_TIMEOUT:
        store[session_id] = InMemoryChatMessageHistory()
    last_activity[session_id] = current_time
    return store[session_id]

# Create a prompt template for the chatbot
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Answer all questions to the best of your ability."),
    MessagesPlaceholder(variable_name="messages")
])

# Combine the model with the prompt and message history
chain = prompt | model

with_message_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="messages"
)

def format_for_slack(text):
    text = re.sub(r'###\s*(.*)', r'*\1*', text)
    text = re.sub(r'^-\s', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    text = re.sub(r'[#_`]', '', text)
    return text

def search_with_tavily(query):
    try:
        response = tavily_client.search(query=query)
        print(response)  # Debug: Print the response structure
        if 'results' in response and response['results']:
            return response['results'][:3]  # Get the top 3 results
        else:
            return []  # Return an empty list if no results
    except Exception as e:
        print(f"Error in Tavily search: {str(e)}")
        return []

def handle_event(data):
    event = data["event"]

    if "text" in event and event["type"] == "message" and event.get("subtype") is None:
        if event.get("user") == BOT_USER_ID:
            return

        # Handle messages with search-related keywords
        if any(keyword in event["text"].lower() for keyword in ["recent", "search", "update", "now", "latest", "news", "current"]):
            search_query = event["text"]
            search_results = search_with_tavily(search_query)

            # Check if results are available and prepare the response
            if search_results:
                documents_text = "\n\n".join([f"Title: {doc['title']}\nURL: {doc['url']}\nContent: {doc['content']}" for doc in search_results])
                
                system_message = SystemMessage(content="""
                You are a helpful assistant tasked with summarizing search results. Follow these steps:
                1. Carefully read through all the search results provided.
                2. Identify the key information that directly answers the user's query.
                3. Summarize this information in a clear, concise manner.
                4. If there are conflicting pieces of information, mention this and provide context.
                5. If the search results don't directly answer the query, provide the most relevant information available.
                6. Always cite your sources by mentioning the title of the article you're referencing.
                7. If you're unsure about any information, express that uncertainty.
                8. Aim for a summary of 3-5 sentences, unless more detail is necessary to properly answer the query.
                """)

                human_message = HumanMessage(content=f"User Query: {search_query}\n\nSearch Results:\n{documents_text}\n\nPlease summarize these search results to answer the user's query.")

                try:
                    response_text = ""
                    for r in with_message_history.stream(
                        {"messages": [system_message, human_message]},
                        config={"configurable": {"session_id": f"{event['channel']}_{event['user']}_{datetime.now().strftime('%Y%m%d%H%M')}"}}
                    ):
                        response_text += r.content

                    if not response_text.strip():
                        raise ValueError("Empty response from the model")

                    formatted_response = format_for_slack(response_text)

                    client.chat_postMessage(
                        channel=event["channel"],
                        text=formatted_response,
                        mrkdwn=True
                    )
                except Exception as e:
                    print(f"Error in processing model response: {str(e)}")
                    client.chat_postMessage(
                        channel=event["channel"],
                        text="I apologize, but I encountered an error while processing the search results. Could you please try asking your question again?",
                        mrkdwn=True
                    )
            else:
                client.chat_postMessage(
                    channel=event["channel"],
                    text="I'm sorry, but I couldn't find any relevant information for your query. Could you please try rephrasing your question or providing more context?",
                    mrkdwn=True
                )
            return

        # Process general conversation
        current_time = datetime.now().strftime("%Y%m%d%H%M")
        session_id = f"{event['channel']}_{event['user']}_{current_time}"
        
        try:
            response_text = ""
            for r in with_message_history.stream(
                {"messages": [HumanMessage(content=event["text"])]},
                config={"configurable": {"session_id": session_id}}
            ):
                response_text += r.content

            formatted_response = format_for_slack(response_text)

            client.chat_postMessage(
                channel=event["channel"],
                text=formatted_response,
                mrkdwn=True
            )
        except SlackApiError as e:
            print(f"Error posting message: {e.response['error']}")

def handle_event_async(data):
    thread = Thread(target=handle_event, args=(data,), daemon=True)
    thread.start()

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