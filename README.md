# GPT Slack Bot

This project is a Slack bot powered by GPT (Generative Pre-trained Transformer) technology, with additional features like web search capabilities using the Tavily API.

## Features

- Conversational AI using GPT-4o-mini model
- Web search functionality for up-to-date information
- Session management with timeout
- Slack message formatting

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.sample` to `.env` and fill in your actual API keys and tokens:
   - OPENAI_API_KEY: Your OpenAI API key
   - SLACK_BOT_TOKEN: Your Slack bot token
   - BOT_USER_ID: Your Slack bot user ID
   - TAVILY_API_KEY: Your Tavily API key for web search functionality
4. Run the bot:
   ```
   python app.py
   ```

## Usage

The bot can handle general conversations and perform web searches when keywords like "recent", "search", "update", "now", "latest", "news", or "current" are detected in the message.

## Files

- `app.py`: Main application file containing the Slack bot logic and API integrations
- `requirements.txt`: List of Python dependencies
- `.env`: Configuration file for API keys and tokens (not tracked in git)
- `.env.sample`: Sample configuration file
- `test.py`: Test file for the application

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.