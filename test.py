import os
from slack_sdk import WebClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize a Web Client with the Slack bot token from the environment variables
slack_token = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# Call the auth.test method to get the bot's user ID
response = client.auth_test()

# Extract the bot user ID
bot_user_id = response["user_id"]
print(f"Bot User ID: {bot_user_id}")