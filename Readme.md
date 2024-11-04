# Slack and Google Calendar Bot

This application integrates with Slack to manage messages related to scheduling and uses Google Calendar API to create events based on available slots. It utilizes Ngrok for public URL exposure.
## Demo 


https://github.com/user-attachments/assets/a08d954f-94fa-4021-a507-19e3e9beb0b8


## Prerequisites

- **Python 3.8+**
- **Ngrok** for exposing local server.
- A Google Cloud project with Calendar API enabled.
- **Google OAuth2 Credentials** file (`credentials.json`) for Google Calendar API.
- **Slack App** with necessary permissions and signing secret.

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/TTHHA/AI-test.git
    cd AI-test
    ```
2. **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate   # On Windows use `venv\Scripts\activate`
    ```

3. **Install required packages**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Create a `.env` file** in the root directory and add the following environment variables:
    ```plaintext
    SLACK_SIGNING_SECRET=your_slack_signing_secret
    SLACK_BOT_TOKEN=your_slack_bot_token
    SCHEDULE_CHANNEL_ID=channel_id
    GEMINI_API_KEY=your_api_key
    ```

5. **Set up Google OAuth2 Credentials**:
   Download the `credentials.json` file from Google Cloud Console and place it in the root directory of your project.

## Usage

1. **Start Ngrok**:
   ```bash
   ngrok http 3000
   ```

⚠️ **Note:** Copy the generated HTTPS URL and set it in your Slack app's event subscription settings. 
Example: (https://abcd-efgh-ijkl.ngrok-free.app/slack/events).

2. **Run the Application**
   ```bash
   python app.py
   ```


## Usage
1. When running the app for the first time, you will be prompted to authenticate with your Google account. Follow the instructions in the console to complete the authentication process.
1. Ensure your Slack app is subscribed to events of type message.
1. Update the permissions (scopes) of Slack.
