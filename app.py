import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from slackeventsapi import SlackEventAdapter
from flask import Flask, request, Response
from dotenv import load_dotenv
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import pytz
import random
import string
import json
import time
load_dotenv()

free_time_history = []
busy_time_history = []
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(
    os.environ['SLACK_SIGNING_SECRET'], '/slack/events', app)

def create_time_extraction_model():

    generation_config = {
        "temperature": 0.3,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        tools=[
            genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name="extract_availability",
                        description=" Extracts free and busy times from a natural language message, strictly follow the message requirements. Times should be in 12-hour format with AM/PM suffix. For early morning preferences, use 8:00 AM as default start time. For unspecified end times, use 12:00 PM (noon) as default.",
                        parameters=content.Schema(
                            type=content.Type.OBJECT,
                            required=["free_time", "busy_time"],  
                            properties={
                                "free_time": content.Schema(
                                    type=content.Type.ARRAY,
                                    items=content.Schema(
                                        type=content.Type.OBJECT,
                                        required=["days", "start_time", "end_time"], 
                                        properties={
                                            "days": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                            "start_time": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                            "end_time": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                        },
                                    ),
                                ),
                                "busy_time": content.Schema(
                                    type=content.Type.ARRAY,
                                    items=content.Schema(
                                        type=content.Type.OBJECT,
                                        required=["days", "start_time", "end_time"],  
                                        properties={
                                            "days": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                            "start_time": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                            "end_time": content.Schema(
                                                type=content.Type.STRING,
                                            ),
                                        },
                                    ),
                                ),
                            },
                        ),
                    ),
                ],
            ),
        ],
        tool_config={'function_calling_config': 'ANY'},
    )
    return model
def create_general_model():
    generation_config = {
        "temperature": 0.1,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config)
    return model

def load_google_calendar_credentials():
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return creds

extract_model = create_time_extraction_model()
general_model = create_general_model()

def parse_time(day, time_str):
    """Parses day name and time strings into datetime objects."""
    day_offset = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    reference_date = datetime.strptime("2024-11-04", "%Y-%m-%d")  
    day_index = day_offset.index(day)
    day_date = reference_date + timedelta(days=day_index)
    return datetime.combine(day_date, datetime.strptime(time_str, "%I:%M %p").time())

def create_event_from_slot(selected_slot):
    """
    Transforms the selected_slot into an event dictionary suitable for Google Calendar API.

    Parameters:
        selected_slot (dict): A dictionary containing 'days', 'start_time', and 'end_time'.

    Returns:
        dict: An event dictionary formatted for Google Calendar API.
    """
    day_name_to_weekday = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6
    }
    
    today = datetime.now().date()
    today_weekday = today.weekday()
    
    target_weekday = day_name_to_weekday[selected_slot['days']]
    
    days_ahead = (target_weekday - today_weekday) % 7
    if days_ahead == 0:
        days_ahead = 7  
    
    event_date = today + timedelta(days=days_ahead)
    
    start_time_str = selected_slot['start_time']
    end_time_str = selected_slot['end_time']
    
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    start_datetime = datetime.strptime(f"{event_date} {start_time_str}", "%Y-%m-%d %I:%M %p")
    end_datetime = datetime.strptime(f"{event_date} {end_time_str}", "%Y-%m-%d %I:%M %p")
    
    start_datetime = tz.localize(start_datetime)
    end_datetime = tz.localize(end_datetime)
    
    start_datetime_str = start_datetime.isoformat()
    end_datetime_str = end_datetime.isoformat()
    
    request_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    
    event = {
        'summary': 'Meeting with Google Meet',
        'description': 'The Best Suite Appointment',
        'start': {
            'dateTime': start_datetime_str,
            'timeZone': 'Asia/Ho_Chi_Minh',
        },
        'end': {
            'dateTime': end_datetime_str,
            'timeZone': 'Asia/Ho_Chi_Minh',
        },
        'conferenceData': {
            'createRequest': {
                'requestId': request_id,
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        },
        'attendees': [
            {'email': '21522082@gm.uit.edu.vn'},
        ],
    }
    
    return event

import json
def normalize_best_schedule_time(input_string):
    cleaned_string = input_string.strip("'").strip()  
    try:
        result_dict = json.loads(cleaned_string)
        return result_dict
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        return None

processed_events = set()  # A set to store processed message timestamps

@slack_event_adapter.on('message')
def slack_events(payload):
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Request verification failed", 400
    
    event = payload.get('event', {})
    channel_id = event.get('channel')
    message_text = event.get('text')
    user_id = event.get('user')
    message_ts = event.get('ts')  
    
    logger.info(f"Received message from user {user_id} in channel {channel_id}: {message_text} have subtype {event.get('subtype')}")
    
    if message_ts in processed_events:
        logger.info(f"Skipping duplicate event with timestamp {message_ts}")
        return Response(), 200 
    
    processed_events.add(message_ts)
    
    conversation_agent = start_scheduled_agent(message_text, general_model)

    if (user_id != "U07U9GJB8AX") and ("SCHEDULE" in conversation_agent): 
        busy_time, free_time = agent(message_text, extract_model)
        free_time_history.append(free_time)
        busy_time_history.append(busy_time)
        try:
            client.reactions_add(
                channel=channel_id,
                name="eyes",
                timestamp=message_ts
            )
        except SlackApiError as e:
            print(f"Error adding reaction: {e.response['error']}")
        return Response(), 200
    elif (user_id != "U07U9GJB8AX") and ("CONFIRM" in conversation_agent):
        try:
            client.reactions_add(
                channel=channel_id,
                name="white_check_mark",
                timestamp=message_ts
            )
        except SlackApiError as e:
            print(f"Error adding reaction: {e.response['error']}")
        meeting_link = find_best_available_time(general_model, free_time_history, busy_time_history)
        push_message(channel_id, f"The meeting is scheduled here: {meeting_link}")
        return Response(), 200
    else:
        return Response(), 200


def push_message(channel_id, message):
    try:
        client.chat_postMessage(channel=channel_id, text=message)
    except SlackApiError as e:
        logger.error(f"Error posting message to Slack: {e}")

def normalize_best_schedule_time(input_string):
    cleaned_string = input_string.strip("'").strip()
    try:
        return json.loads(cleaned_string)
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        return None

def agent(message=None, model=None):
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(message)
    return clear_response_agent(response)

def start_scheduled_agent(message=None, model=None):
    prompt = """Analyze the following message and determine if it's:
        1. A general chat/conversation message (CHAT)
        2. A message related to schedule (free time/busy time) (SCHEDULE)
        3. A message related to confirm a meeting schedule  (CONFIRM)
        Message: "{message}"

        Classify as either "CHAT" or "SCHEDULE" or "CONFIRM". 
        Respond in the format:
        Classification: [CHAT/SCHEDULE/CONFIRM]"""
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(prompt.format(message=message))
    return response.text

def clear_response_agent(response):
    free_time = {}
    busy_time_dict = {}
    for part in response.parts:
        if fn := part.function_call:
            for key, val in fn.args.items():
                if key == "busy_time":
                    for item in val:
                        busy_time_dict = {k: v for k, v in item.items()}
                elif key == "free_time":
                    for item in val:
                        free_time = {k: v for k, v in item.items()}
    return busy_time_dict,free_time

def find_best_available_time(model,Free_time_history,Busy_time_history):
    prompt = """Based on the available time slots, please select the best time slot for the meeting. Here are the available time slots:
    - Free time: {free_time}
    - Busy time: {busy_time}
    - Appointment Duration: 1 hours (If not specified, the default duration is 1 hour)
    Please only response the day and time in the exact following JSON format, without any additional text:
    {{"days": "...", "start_time": "...", "end_time": "..."}}"""
    chat_session = model.start_chat(
    history=[
    ]
    )
    Best_time_Agent = chat_session.send_message(prompt.format(free_time = Free_time_history,busy_time = Busy_time_history))
    result = normalize_best_schedule_time(Best_time_Agent.text)
    event = create_event_from_slot(result)
    event_scheduled = create_meeting(event)
    return event_scheduled

def create_meeting(event):
  event = calendar_service.events().insert(calendarId='primary',  
                                  body=event,  
                                  conferenceDataVersion=1).execute()  
  print(f"Event created: {event.get('htmlLink')}")
  return event.get('htmlLink')

signature_verifier = SignatureVerifier(os.environ["SLACK_SIGNING_SECRET"])

slack_token = os.environ["SLACK_BOT_TOKEN"]
client = WebClient(token=slack_token)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    calendar_service = build("calendar", "v3", credentials=load_google_calendar_credentials())
    app.run(port=3000,debug=True)
