import os
import json
import weave
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, timedelta, timezone
import dateutil.parser
from dateutil import tz
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarClient:
    def __init__(self):
        self.creds = None
        
        # First try service account (for server/bot usage)
        service_account_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        if service_account_file and os.path.exists(service_account_file):
            self.creds = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=SCOPES)
            # If using service account with delegation
            delegated_user = os.environ.get("GOOGLE_CALENDAR_DELEGATED_USER")
            if delegated_user:
                self.creds = self.creds.with_subject(delegated_user)
        else:
            # Try OAuth2 credentials (for personal usage)
            token_file = os.environ.get("GOOGLE_CALENDAR_TOKEN_FILE", "token.pickle")
            creds_file = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials.json")
            
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    self.creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in.
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                elif os.path.exists(creds_file):
                    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    # Save the credentials for the next run
                    with open(token_file, 'wb') as token:
                        pickle.dump(self.creds, token)
                else:
                    raise ValueError(
                        "No valid Google Calendar credentials found. Please set either:\n"
                        "1. GOOGLE_SERVICE_ACCOUNT_FILE environment variable, or\n"
                        "2. GOOGLE_CALENDAR_CREDENTIALS_FILE for OAuth2 flow"
                    )
        
        self.service = build('calendar', 'v3', credentials=self.creds)
        self.calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

def parse_natural_time(time_str: str, reference_date: datetime = None) -> datetime:
    """Parse natural language time expressions into datetime objects."""
    if reference_date is None:
        reference_date = datetime.now(tz=tz.tzlocal())
    
    time_str = time_str.lower().strip()
    
    # Handle relative day expressions
    if "today" in time_str:
        base_date = reference_date.date()
    elif "tomorrow" in time_str:
        base_date = (reference_date + timedelta(days=1)).date()
    elif "day after tomorrow" in time_str:
        base_date = (reference_date + timedelta(days=2)).date()
    elif "next monday" in time_str:
        days_ahead = 0 - reference_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        base_date = (reference_date + timedelta(days=days_ahead)).date()
    elif "next tuesday" in time_str:
        days_ahead = 1 - reference_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        base_date = (reference_date + timedelta(days=days_ahead)).date()
    elif "next wednesday" in time_str:
        days_ahead = 2 - reference_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        base_date = (reference_date + timedelta(days=days_ahead)).date()
    elif "next thursday" in time_str:
        days_ahead = 3 - reference_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        base_date = (reference_date + timedelta(days=days_ahead)).date()
    elif "next friday" in time_str:
        days_ahead = 4 - reference_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        base_date = (reference_date + timedelta(days=days_ahead)).date()
    else:
        # Try to parse as is
        try:
            return dateutil.parser.parse(time_str)
        except:
            # Default to today if we can't parse
            base_date = reference_date.date()
    
    # Extract time from string
    import re
    time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?'
    time_match = re.search(time_pattern, time_str)
    
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        am_pm = time_match.group(3)
        
        if am_pm == 'pm' and hour < 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        
        result = datetime.combine(base_date, datetime.min.time())
        result = result.replace(hour=hour, minute=minute, tzinfo=reference_date.tzinfo)
        return result
    else:
        # Check for common time expressions
        if "morning" in time_str:
            hour = 9
        elif "afternoon" in time_str:
            hour = 14
        elif "evening" in time_str:
            hour = 18
        elif "noon" in time_str or "midday" in time_str:
            hour = 12
        else:
            hour = 9  # Default to 9 AM
        
        result = datetime.combine(base_date, datetime.min.time())
        result = result.replace(hour=hour, minute=0, tzinfo=reference_date.tzinfo)
        return result

@weave.op(name="calendar-list_events")
def list_events(
    *,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 10,
    search_query: Optional[str] = None,
    calendar_id: Optional[str] = None
) -> List[Dict]:
    """
    List calendar events within a specified time range.
    
    Args:
        time_min: Start time (ISO format or natural language like "today", "tomorrow at 9am")
        time_max: End time (ISO format or natural language)
        max_results: Maximum number of events to return (default 10)
        search_query: Optional text to search in event titles/descriptions
        calendar_id: Calendar ID to query (defaults to primary calendar)
    
    Returns:
        List of event dictionaries with details
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Parse time parameters
        now = datetime.now(tz=tz.tzlocal())
        if time_min:
            time_min_dt = parse_natural_time(time_min) if not time_min.endswith('Z') else dateutil.parser.parse(time_min)
        else:
            time_min_dt = now
        
        if time_max:
            time_max_dt = parse_natural_time(time_max) if not time_max.endswith('Z') else dateutil.parser.parse(time_max)
        else:
            time_max_dt = time_min_dt + timedelta(days=7)
        
        # Convert to RFC3339 format
        time_min_str = time_min_dt.isoformat()
        time_max_str = time_max_dt.isoformat()
        
        # Build query
        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min_str,
            timeMax=time_max_str,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime',
            q=search_query
        ).execute()
        
        events = events_result.get('items', [])
        
        # Format events for easier consumption
        formatted_events = []
        for event in events:
            formatted_event = {
                'id': event['id'],
                'summary': event.get('summary', 'No title'),
                'start': event['start'].get('dateTime', event['start'].get('date')),
                'end': event['end'].get('dateTime', event['end'].get('date')),
                'location': event.get('location', ''),
                'description': event.get('description', ''),
                'attendees': [
                    {
                        'email': attendee['email'],
                        'responseStatus': attendee.get('responseStatus', 'needsAction')
                    } for attendee in event.get('attendees', [])
                ],
                'organizer': event.get('organizer', {}).get('email', ''),
                'htmlLink': event.get('htmlLink', '')
            }
            formatted_events.append(formatted_event)
        
        return formatted_events
        
    except Exception as e:
        print(f"Error listing events: {str(e)}")
        return []

@weave.op(name="calendar-find_free_time")
def find_free_time(
    *,
    duration_minutes: int = 60,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    attendee_emails: Optional[List[str]] = None,
    working_hours_only: bool = True,
    calendar_id: Optional[str] = None
) -> List[Dict]:
    """
    Find available time slots in calendar(s).
    
    Args:
        duration_minutes: Duration of the desired time slot in minutes
        time_min: Start of search window (defaults to now)
        time_max: End of search window (defaults to 7 days from now)
        attendee_emails: List of attendee emails to check availability
        working_hours_only: Only return slots during working hours (9 AM - 5 PM)
        calendar_id: Calendar ID to check (defaults to primary)
    
    Returns:
        List of available time slots with start and end times
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Parse time parameters
        now = datetime.now(tz=tz.tzlocal())
        if time_min:
            search_start = parse_natural_time(time_min)
        else:
            search_start = now
            
        if time_max:
            search_end = parse_natural_time(time_max)
        else:
            search_end = search_start + timedelta(days=7)
        
        # Get busy times
        items = [{"id": cal_id}]
        if attendee_emails:
            items.extend([{"id": email} for email in attendee_emails])
        
        freebusy_query = service.freebusy().query(
            body={
                "timeMin": search_start.isoformat(),
                "timeMax": search_end.isoformat(),
                "items": items
            }
        ).execute()
        
        # Collect all busy periods
        busy_periods = []
        for calendar_data in freebusy_query['calendars'].values():
            for busy in calendar_data.get('busy', []):
                start = dateutil.parser.parse(busy['start'])
                end = dateutil.parser.parse(busy['end'])
                busy_periods.append((start, end))
        
        # Sort and merge overlapping busy periods
        busy_periods.sort()
        merged_busy = []
        for start, end in busy_periods:
            if merged_busy and start <= merged_busy[-1][1]:
                merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], end))
            else:
                merged_busy.append((start, end))
        
        # Find free slots
        free_slots = []
        current_time = search_start
        
        for busy_start, busy_end in merged_busy:
            # Check if there's a gap before this busy period
            if current_time < busy_start:
                # Add free slot
                slot_start = current_time
                slot_end = busy_start
                
                # Split into duration-sized chunks
                while slot_start + timedelta(minutes=duration_minutes) <= slot_end:
                    if working_hours_only:
                        # Check if within working hours
                        if 9 <= slot_start.hour < 17 and slot_start.weekday() < 5:
                            free_slots.append({
                                "start": slot_start.isoformat(),
                                "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                                "duration_minutes": duration_minutes
                            })
                    else:
                        free_slots.append({
                            "start": slot_start.isoformat(),
                            "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                            "duration_minutes": duration_minutes
                        })
                    
                    slot_start += timedelta(minutes=30)  # 30-minute increments
            
            current_time = busy_end
        
        # Check for free time after all busy periods
        if current_time < search_end:
            slot_start = current_time
            while slot_start + timedelta(minutes=duration_minutes) <= search_end:
                if working_hours_only:
                    if 9 <= slot_start.hour < 17 and slot_start.weekday() < 5:
                        free_slots.append({
                            "start": slot_start.isoformat(),
                            "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                            "duration_minutes": duration_minutes
                        })
                else:
                    free_slots.append({
                        "start": slot_start.isoformat(),
                        "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                        "duration_minutes": duration_minutes
                    })
                
                slot_start += timedelta(minutes=30)
        
        return free_slots[:20]  # Return max 20 slots
        
    except Exception as e:
        print(f"Error finding free time: {str(e)}")
        return []

@weave.op(name="calendar-create_event")
def create_event(
    *,
    summary: str,
    start_time: str,
    end_time: Optional[str] = None,
    duration_minutes: Optional[int] = 60,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendee_emails: Optional[List[str]] = None,
    reminder_minutes: Optional[int] = 10,
    calendar_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Create a new calendar event.
    
    Args:
        summary: Event title/summary
        start_time: Start time (ISO format or natural language)
        end_time: End time (if not provided, uses duration_minutes)
        duration_minutes: Duration in minutes if end_time not provided (default 60)
        description: Event description
        location: Event location
        attendee_emails: List of attendee email addresses
        reminder_minutes: Minutes before event to send reminder (default 10)
        calendar_id: Calendar ID to create event in (defaults to primary)
    
    Returns:
        Created event details or None if failed
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Parse start time
        start_dt = parse_natural_time(start_time)
        
        # Determine end time
        if end_time:
            end_dt = parse_natural_time(end_time)
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Build event body
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': str(start_dt.tzinfo),
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': str(end_dt.tzinfo),
            },
        }
        
        if description:
            event['description'] = description
        
        if location:
            event['location'] = location
        
        if attendee_emails:
            event['attendees'] = [{'email': email} for email in attendee_emails]
        
        if reminder_minutes:
            event['reminders'] = {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': reminder_minutes},
                ],
            }
        
        # Create the event
        created_event = service.events().insert(
            calendarId=cal_id,
            body=event,
            sendUpdates='all' if attendee_emails else 'none'
        ).execute()
        
        return {
            'id': created_event['id'],
            'summary': created_event.get('summary'),
            'start': created_event['start'].get('dateTime', created_event['start'].get('date')),
            'end': created_event['end'].get('dateTime', created_event['end'].get('date')),
            'htmlLink': created_event.get('htmlLink'),
            'status': 'created'
        }
        
    except Exception as e:
        print(f"Error creating event: {str(e)}")
        return None

@weave.op(name="calendar-reschedule_event")
def reschedule_event(
    *,
    event_id: str,
    new_start_time: str,
    new_end_time: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    notify_attendees: bool = True,
    calendar_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Reschedule an existing calendar event.
    
    Args:
        event_id: ID of the event to reschedule
        new_start_time: New start time (ISO format or natural language)
        new_end_time: New end time (if not provided, maintains original duration)
        duration_minutes: New duration if end_time not provided
        notify_attendees: Whether to send update notifications to attendees
        calendar_id: Calendar ID containing the event (defaults to primary)
    
    Returns:
        Updated event details or None if failed
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Get the existing event
        event = service.events().get(calendarId=cal_id, eventId=event_id).execute()
        
        # Parse new start time
        new_start_dt = parse_natural_time(new_start_time)
        
        # Determine new end time
        if new_end_time:
            new_end_dt = parse_natural_time(new_end_time)
        elif duration_minutes:
            new_end_dt = new_start_dt + timedelta(minutes=duration_minutes)
        else:
            # Maintain original duration
            original_start = dateutil.parser.parse(event['start'].get('dateTime', event['start'].get('date')))
            original_end = dateutil.parser.parse(event['end'].get('dateTime', event['end'].get('date')))
            original_duration = original_end - original_start
            new_end_dt = new_start_dt + original_duration
        
        # Update event times
        event['start'] = {
            'dateTime': new_start_dt.isoformat(),
            'timeZone': str(new_start_dt.tzinfo),
        }
        event['end'] = {
            'dateTime': new_end_dt.isoformat(),
            'timeZone': str(new_end_dt.tzinfo),
        }
        
        # Update the event
        updated_event = service.events().update(
            calendarId=cal_id,
            eventId=event_id,
            body=event,
            sendUpdates='all' if notify_attendees else 'none'
        ).execute()
        
        return {
            'id': updated_event['id'],
            'summary': updated_event.get('summary'),
            'start': updated_event['start'].get('dateTime', updated_event['start'].get('date')),
            'end': updated_event['end'].get('dateTime', updated_event['end'].get('date')),
            'htmlLink': updated_event.get('htmlLink'),
            'status': 'rescheduled'
        }
        
    except Exception as e:
        print(f"Error rescheduling event: {str(e)}")
        return None

@weave.op(name="calendar-cancel_event")
def cancel_event(
    *,
    event_id: str,
    cancellation_message: Optional[str] = None,
    notify_attendees: bool = True,
    calendar_id: Optional[str] = None
) -> bool:
    """
    Cancel a calendar event.
    
    Args:
        event_id: ID of the event to cancel
        cancellation_message: Optional message to include with cancellation
        notify_attendees: Whether to send cancellation notifications
        calendar_id: Calendar ID containing the event (defaults to primary)
    
    Returns:
        True if successfully cancelled, False otherwise
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        if cancellation_message:
            # Get event first to add cancellation message
            event = service.events().get(calendarId=cal_id, eventId=event_id).execute()
            event['status'] = 'cancelled'
            if 'description' in event:
                event['description'] = f"CANCELLED: {cancellation_message}\n\nOriginal description:\n{event['description']}"
            else:
                event['description'] = f"CANCELLED: {cancellation_message}"
            
            service.events().update(
                calendarId=cal_id,
                eventId=event_id,
                body=event,
                sendUpdates='all' if notify_attendees else 'none'
            ).execute()
        
        # Delete the event
        service.events().delete(
            calendarId=cal_id,
            eventId=event_id,
            sendUpdates='all' if notify_attendees else 'none'
        ).execute()
        
        return True
        
    except Exception as e:
        print(f"Error cancelling event: {str(e)}")
        return False

@weave.op(name="calendar-check_conflicts")
def check_conflicts(
    *,
    start_time: str,
    end_time: Optional[str] = None,
    duration_minutes: Optional[int] = 60,
    attendee_emails: Optional[List[str]] = None,
    calendar_id: Optional[str] = None
) -> Dict:
    """
    Check if a proposed time conflicts with existing events.
    
    Args:
        start_time: Proposed start time (ISO format or natural language)
        end_time: Proposed end time (if not provided, uses duration_minutes)
        duration_minutes: Duration in minutes if end_time not provided (default 60)
        attendee_emails: List of attendee emails to check for conflicts
        calendar_id: Calendar ID to check (defaults to primary)
    
    Returns:
        Dictionary with conflict information and conflicting events
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Parse times
        start_dt = parse_natural_time(start_time)
        if end_time:
            end_dt = parse_natural_time(end_time)
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Check calendars
        items = [{"id": cal_id}]
        if attendee_emails:
            items.extend([{"id": email} for email in attendee_emails])
        
        freebusy_query = service.freebusy().query(
            body={
                "timeMin": start_dt.isoformat(),
                "timeMax": end_dt.isoformat(),
                "items": items
            }
        ).execute()
        
        conflicts = []
        has_conflicts = False
        
        for calendar_id, calendar_data in freebusy_query['calendars'].items():
            busy_times = calendar_data.get('busy', [])
            if busy_times:
                has_conflicts = True
                for busy in busy_times:
                    conflicts.append({
                        'calendar': calendar_id,
                        'start': busy['start'],
                        'end': busy['end']
                    })
        
        return {
            'has_conflicts': has_conflicts,
            'proposed_start': start_dt.isoformat(),
            'proposed_end': end_dt.isoformat(),
            'conflicts': conflicts
        }
        
    except Exception as e:
        print(f"Error checking conflicts: {str(e)}")
        return {
            'has_conflicts': False,
            'error': str(e),
            'conflicts': []
        }

@weave.op(name="calendar-get_daily_summary")
def get_daily_summary(
    *,
    date: Optional[str] = None,
    calendar_id: Optional[str] = None,
    include_details: bool = False
) -> Dict:
    """
    Get a summary of events for a specific day.
    
    Args:
        date: Date to get summary for (defaults to today)
        calendar_id: Calendar ID to query (defaults to primary)
        include_details: Whether to include full event details
    
    Returns:
        Dictionary with day summary including event count and list
    """
    try:
        client = GoogleCalendarClient()
        
        # Parse date
        if date:
            target_date = parse_natural_time(date)
        else:
            target_date = datetime.now(tz=tz.tzlocal())
        
        # Set to beginning and end of day
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get events for the day
        events = list_events(
            time_min=day_start.isoformat(),
            time_max=day_end.isoformat(),
            max_results=50,
            calendar_id=calendar_id
        )
        
        # Calculate total busy time
        total_busy_minutes = 0
        for event in events:
            if 'dateTime' in event.get('start', {}):
                start = dateutil.parser.parse(event['start'])
                end = dateutil.parser.parse(event['end'])
                duration = (end - start).total_seconds() / 60
                total_busy_minutes += duration
        
        summary = {
            'date': day_start.strftime('%Y-%m-%d'),
            'day_name': day_start.strftime('%A'),
            'event_count': len(events),
            'total_busy_hours': round(total_busy_minutes / 60, 1),
            'first_event_time': events[0]['start'] if events else None,
            'last_event_time': events[-1]['end'] if events else None,
        }
        
        if include_details:
            summary['events'] = events
        else:
            summary['event_titles'] = [event['summary'] for event in events]
        
        return summary
        
    except Exception as e:
        print(f"Error getting daily summary: {str(e)}")
        return {
            'date': date or 'today',
            'error': str(e),
            'event_count': 0
        }

@weave.op(name="calendar-update_event")
def update_event(
    *,
    event_id: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    add_attendees: Optional[List[str]] = None,
    remove_attendees: Optional[List[str]] = None,
    calendar_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Update an existing calendar event's details.
    
    Args:
        event_id: ID of the event to update
        summary: New event title/summary
        description: New event description
        location: New event location
        add_attendees: Email addresses of attendees to add
        remove_attendees: Email addresses of attendees to remove
        calendar_id: Calendar ID containing the event (defaults to primary)
    
    Returns:
        Updated event details or None if failed
    """
    try:
        client = GoogleCalendarClient()
        service = client.service
        cal_id = calendar_id or client.calendar_id
        
        # Get the existing event
        event = service.events().get(calendarId=cal_id, eventId=event_id).execute()
        
        # Update fields if provided
        if summary is not None:
            event['summary'] = summary
        
        if description is not None:
            event['description'] = description
        
        if location is not None:
            event['location'] = location
        
        # Handle attendee modifications
        current_attendees = event.get('attendees', [])
        attendee_emails = {att['email'] for att in current_attendees}
        
        if remove_attendees:
            attendee_emails -= set(remove_attendees)
        
        if add_attendees:
            attendee_emails.update(add_attendees)
        
        event['attendees'] = [{'email': email} for email in attendee_emails]
        
        # Update the event
        updated_event = service.events().update(
            calendarId=cal_id,
            eventId=event_id,
            body=event,
            sendUpdates='all'
        ).execute()
        
        return {
            'id': updated_event['id'],
            'summary': updated_event.get('summary'),
            'start': updated_event['start'].get('dateTime', updated_event['start'].get('date')),
            'end': updated_event['end'].get('dateTime', updated_event['end'].get('date')),
            'location': updated_event.get('location'),
            'description': updated_event.get('description'),
            'attendees': [att['email'] for att in updated_event.get('attendees', [])],
            'htmlLink': updated_event.get('htmlLink'),
            'status': 'updated'
        }
        
    except Exception as e:
        print(f"Error updating event: {str(e)}")
        return None

@weave.op(name="calendar-find_optimal_meeting_time")
def find_optimal_meeting_time(
    *,
    attendee_emails: List[str],
    duration_minutes: int = 60,
    earliest_start: Optional[str] = None,
    latest_start: Optional[str] = None,
    preferred_times: Optional[List[str]] = None,
    calendar_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Find the optimal meeting time for multiple attendees.
    
    Args:
        attendee_emails: List of attendee email addresses to check
        duration_minutes: Duration of the meeting in minutes
        earliest_start: Earliest acceptable start time
        latest_start: Latest acceptable start time
        preferred_times: List of preferred time slots (e.g., ["morning", "afternoon"])
        calendar_id: Calendar ID to check (defaults to primary)
    
    Returns:
        Optimal meeting time slot or None if no common time found
    """
    try:
        # Get free times for all attendees
        free_slots = find_free_time(
            duration_minutes=duration_minutes,
            time_min=earliest_start,
            time_max=latest_start,
            attendee_emails=attendee_emails,
            working_hours_only=True,
            calendar_id=calendar_id
        )
        
        if not free_slots:
            return None
        
        # Score slots based on preferences
        scored_slots = []
        for slot in free_slots:
            slot_start = dateutil.parser.parse(slot['start'])
            score = 100  # Base score
            
            # Prefer slots not too early or too late
            hour = slot_start.hour
            if 10 <= hour <= 11 or 14 <= hour <= 15:
                score += 20  # Prefer mid-morning or mid-afternoon
            elif hour < 9 or hour > 16:
                score -= 20  # Penalize very early or late slots
            
            # Check preferred times
            if preferred_times:
                for pref in preferred_times:
                    if pref.lower() == "morning" and hour < 12:
                        score += 10
                    elif pref.lower() == "afternoon" and 12 <= hour < 17:
                        score += 10
                    elif pref.lower() == "lunch" and 11 <= hour <= 13:
                        score += 15
            
            # Prefer slots closer to current time (but not too close)
            hours_from_now = (slot_start - datetime.now(tz=tz.tzlocal())).total_seconds() / 3600
            if 2 <= hours_from_now <= 24:
                score += 10
            elif hours_from_now > 72:
                score -= 5
            
            scored_slots.append((score, slot))
        
        # Sort by score (highest first)
        scored_slots.sort(reverse=True, key=lambda x: x[0])
        
        optimal_slot = scored_slots[0][1]
        return {
            'optimal_time': optimal_slot,
            'alternative_times': [slot for _, slot in scored_slots[1:4]],  # Top 3 alternatives
            'total_options_found': len(free_slots)
        }
        
    except Exception as e:
        print(f"Error finding optimal meeting time: {str(e)}")
        return None

# Tool definitions for Tyler integration
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-list_events",
                "description": "List calendar events within a specified time range. Use natural language for times like 'today', 'tomorrow at 2pm', 'next Monday'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "time_min": {
                            "type": "string",
                            "description": "Start time (ISO format or natural language)"
                        },
                        "time_max": {
                            "type": "string",
                            "description": "End time (ISO format or natural language)"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events to return"
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Optional text to search in event titles/descriptions"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to query (defaults to primary calendar)"
                        }
                    }
                }
            }
        },
        "implementation": list_events
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-find_free_time",
                "description": "Find available time slots in calendar(s). Useful for scheduling meetings.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration of the desired time slot in minutes"
                        },
                        "time_min": {
                            "type": "string",
                            "description": "Start of search window"
                        },
                        "time_max": {
                            "type": "string",
                            "description": "End of search window"
                        },
                        "attendee_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee emails to check availability"
                        },
                        "working_hours_only": {
                            "type": "boolean",
                            "description": "Only return slots during working hours (9 AM - 5 PM)"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to check"
                        }
                    },
                    "required": ["duration_minutes"]
                }
            }
        },
        "implementation": find_free_time
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-create_event",
                "description": "Create a new calendar event. Supports natural language for times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Event title/summary"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time (ISO format or natural language like 'tomorrow at 2pm')"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time (if not provided, uses duration_minutes)"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes if end_time not provided"
                        },
                        "description": {
                            "type": "string",
                            "description": "Event description"
                        },
                        "location": {
                            "type": "string",
                            "description": "Event location"
                        },
                        "attendee_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee email addresses"
                        },
                        "reminder_minutes": {
                            "type": "integer",
                            "description": "Minutes before event to send reminder"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to create event in"
                        }
                    },
                    "required": ["summary", "start_time"]
                }
            }
        },
        "implementation": create_event
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-reschedule_event",
                "description": "Reschedule an existing calendar event to a new time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "ID of the event to reschedule"
                        },
                        "new_start_time": {
                            "type": "string",
                            "description": "New start time (ISO format or natural language)"
                        },
                        "new_end_time": {
                            "type": "string",
                            "description": "New end time (if not provided, maintains original duration)"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "New duration if end_time not provided"
                        },
                        "notify_attendees": {
                            "type": "boolean",
                            "description": "Whether to send update notifications to attendees"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID containing the event"
                        }
                    },
                    "required": ["event_id", "new_start_time"]
                }
            }
        },
        "implementation": reschedule_event
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-cancel_event",
                "description": "Cancel a calendar event with optional cancellation message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "ID of the event to cancel"
                        },
                        "cancellation_message": {
                            "type": "string",
                            "description": "Optional message to include with cancellation"
                        },
                        "notify_attendees": {
                            "type": "boolean",
                            "description": "Whether to send cancellation notifications"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID containing the event"
                        }
                    },
                    "required": ["event_id"]
                }
            }
        },
        "implementation": cancel_event
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-check_conflicts",
                "description": "Check if a proposed time conflicts with existing events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "Proposed start time"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "Proposed end time"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes if end_time not provided"
                        },
                        "attendee_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee emails to check for conflicts"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to check"
                        }
                    },
                    "required": ["start_time"]
                }
            }
        },
        "implementation": check_conflicts
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-get_daily_summary",
                "description": "Get a summary of events for a specific day.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date to get summary for (defaults to today)"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to query"
                        },
                        "include_details": {
                            "type": "boolean",
                            "description": "Whether to include full event details"
                        }
                    }
                }
            }
        },
        "implementation": get_daily_summary
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-update_event",
                "description": "Update an existing calendar event's details (title, description, location, attendees).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "ID of the event to update"
                        },
                        "summary": {
                            "type": "string",
                            "description": "New event title/summary"
                        },
                        "description": {
                            "type": "string",
                            "description": "New event description"
                        },
                        "location": {
                            "type": "string",
                            "description": "New event location"
                        },
                        "add_attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Email addresses of attendees to add"
                        },
                        "remove_attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Email addresses of attendees to remove"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID containing the event"
                        }
                    },
                    "required": ["event_id"]
                }
            }
        },
        "implementation": update_event
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "calendar-find_optimal_meeting_time",
                "description": "Find the optimal meeting time for multiple attendees based on availability and preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "attendee_emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee email addresses to check"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration of the meeting in minutes"
                        },
                        "earliest_start": {
                            "type": "string",
                            "description": "Earliest acceptable start time"
                        },
                        "latest_start": {
                            "type": "string",
                            "description": "Latest acceptable start time"
                        },
                        "preferred_times": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of preferred time slots (e.g., ['morning', 'afternoon'])"
                        },
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID to check"
                        }
                    },
                    "required": ["attendee_emails", "duration_minutes"]
                }
            }
        },
        "implementation": find_optimal_meeting_time
    }
]