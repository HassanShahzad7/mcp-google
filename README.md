# MCP Google Server

A Model Context Protocol (MCP) server that integrates with Google services (Gmail, Calendar, and Chat) to provide AI assistants with access to your Google workspace.

## Features

### Gmail Integration
- **Message Management**
  - `create_message` - Create a message for the Gmail API
  - `create_multipart_message` - Create a multipart MIME message (text and HTML)
  - `send_email` - Compose and send an email
  - `get_message` - Get a specific message by ID
  - `list_messages` - List messages in the user's mailbox
  - `search_messages` - Search for messages using various criteria
  - `modify_message_labels` - Modify the labels on a message
  - `trash_message` - Move a message to trash
  - `untrash_message` - Remove a message from trash

- **Draft Management**
  - `create_draft` - Create a draft email
  - `list_drafts` - List draft emails in the user's mailbox
  - `send_draft` - Send an existing draft email

- **Label Management**
  - `get_labels` - Get all labels for the specified user
  - `create_label` - Create a new label
  - `update_label` - Update an existing label
  - `delete_label` - Delete a label

### Google Calendar Integration
- **Calendar Management**
  - `find_calendars` - List the calendars on user's calendar list
  - `create_calendar` - Create a new calendar

- **Event Management**
  - `find_events` - Find events in a specified calendar based on various criteria
  - `create_event` - Create a new event in the specified calendar
  - `quick_add_event` - Create an event based on a simple text string using Google's parser
  - `update_event` - Update an existing event using patch semantics
  - `delete_event` - Delete an event
  - `get_event` - Get a specific event by ID

- **Advanced Features**
  - `project_recurring_events` - Find recurring events and project their occurrences within a time window
  - `analyze_busyness` - Analyze event count and total duration per day within a time window
  - `find_availability` - Find free/busy information for a list of calendars

### Google Chat Integration
- `list_chat_spaces` - List all Google Chat spaces the authenticated user has access to
- `get_space_details` - Get details for a specific Google Chat space
- `list_space_messages` - List messages from a specific Google Chat space with optional time filtering
- `get_message_details` - Get details for a specific Google Chat message
- `send_message` - Send a message to a Google Chat space
- `list_space_members` - List members of a specific Google Chat space

## Installation

### Prerequisites
- Python 3.8+
- uv (Python package manager)
- Google Cloud account with appropriate APIs enabled

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/HassanShahzad7/mcp-google
   cd mcp-google
   ```

2. **Create and activate virtual environment**
   
   Using uv:
   ```bash
   uv venv
   ```
   
   Activate the environment:
   - **Windows**: `.venv\Scripts\activate`
   - **macOS/Linux**: `source .venv/bin/activate`

3. **Install dependencies**
   ```bash
   uv sync
   ```

## Google Cloud Setup

1. **Create a new Google Cloud project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable required APIs**
   - Enable Gmail API
   - Enable Google Calendar API
   - Enable Google Chat API

3. **Configure OAuth consent screen**
   - Navigate to "APIs & Services" > "OAuth consent screen"
   - Select "External" user type
   - Add your email as a test user
   - Add necessary scopes:
     - Gmail: `https://www.googleapis.com/auth/gmail.modify`
     - Calendar: `https://www.googleapis.com/auth/calendar`
     - Google Chat: `https://www.googleapis.com/auth/chat.messages`

4. **Create OAuth 2.0 credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the JSON credentials file

## Configuration

1. **Store credentials securely**
   ```bash
   # Create directory for credentials
   mkdir -p ~/.gmail-mcp
   
   # Move your downloaded credentials file
   mv ~/Downloads/client_secret_*.json ~/.gmail-mcp/credentials.json
   ```

2. **Generate authentication tokens**
   
   Run the following setup scripts to authenticate and generate tokens:
   ```bash
   uv run python scripts/test_gmail_setup.py
   uv run python scripts/test_calendar_setup.py
   uv run python scripts/test_google_chat_setup.py
   ```
   
   These scripts will create the necessary token files required for the service.

## Usage

### Option 1: Claude Inspector

Run the server with Claude Inspector for development and testing:
```bash
uv run mcp dev mcp_google/server.py
```

### Option 2: Claude Desktop

1. **Create configuration file**
   
   Create a `claude_desktop_config.json` file with the following content:
   ```json
   {
     "mcpServers": {
       "gmail": {
         "command": "uv",
         "args": [
           "run",
           "--with",
           "mcp[cli]",
           "--with-editable",
           "/path/to/mcp-google",
           "mcp",
           "run",
           "/path/to/mcp-google/mcp_google/server.py"
         ],
         "env": {
           "MCP_GMAIL_CREDENTIALS_PATH": "/path/to/mcp-google/credentials.json",
           "MCP_GMAIL_TOKEN_PATH": "/path/to/mcp-google/token.json",
           "MCP_CALENDAR_CREDENTIALS_PATH": "/path/to/mcp-google/credentials.json",
           "MCP_CALENDAR_TOKEN_PATH": "/path/to/mcp-google/calendar_token.json",
           "MCP_GOOGLE_CHAT_CREDENTIALS_PATH": "/path/to/mcp-google/credentials.json",
           "MCP_GOOGLE_CHAT_TOKEN_PATH": "/path/to/mcp-google/google_chat_token.json"
         }
       }
     }
   }
   ```
   
   **Note**: Replace `/path/to/mcp-google` with the actual path to your mcp-google directory.

2. **Place the configuration file**
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Example Prompts

Once the server is running and connected to Claude, you can use natural language prompts like:

### Gmail
- "Show me my unread emails"
- "Read the email from XYZ"
- "Reply to XYZ that I would be there at 7pm"
- "Archive all emails from xyz@gmail.com"

### Google Calendar
- "Create a calendar invite with XYZ for tomorrow at 3PM"
- "Update the calendar invite with XYZ to change it to day after tomorrow for 1 hour between 12pm - 5pm, checking the free slot available"
- "Return all the events for June 30"

### Google Chat
- "Show the chat messages from Google Chat"
- "Send a message to XYZ that I am joining the meeting, hang on a second"

## Troubleshooting

- **Authentication issues**: Make sure you've run all three setup scripts to generate the necessary tokens
- **Permission errors**: Ensure your Google Cloud project has the appropriate APIs enabled and OAuth scopes configured
- **Path issues**: Verify that all paths in your configuration files are absolute paths and correctly point to your credentials and token files

## License

Contributions are welcome! Please feel free to submit a Pull Request.

- Fork the repository
- Create your feature branch (git checkout -b feature/amazing-feature)
- Commit your changes (git commit -m 'Add some amazing feature')
- Push to the branch (git push origin feature/amazing-feature)
- Open a Pull Request

## Contributing

[Add contribution guidelines if applicable]