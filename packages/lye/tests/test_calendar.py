import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
from dateutil import tz
from lye.calendar import (
    GoogleCalendarClient,
    parse_natural_time,
    list_events,
    find_free_time,
    create_event,
    reschedule_event,
    cancel_event,
    check_conflicts,
    get_daily_summary,
    update_event,
    find_optimal_meeting_time
)

@pytest.fixture
def mock_env_service_account(monkeypatch):
    """Fixture to mock Google service account environment variable"""
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "mock-service-account.json")
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "primary")

@pytest.fixture
def mock_google_service():
    """Fixture to create a mock Google Calendar service"""
    with patch('lye.calendar.build') as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service

@patch('os.path.exists')
@patch('lye.calendar.service_account.Credentials.from_service_account_file')
def test_google_calendar_client_init_service_account(mock_creds, mock_exists, mock_env_service_account):
    """Test GoogleCalendarClient initialization with service account"""
    mock_exists.return_value = True
    mock_creds.return_value = MagicMock()
    
    with patch('lye.calendar.build'):
        client = GoogleCalendarClient()
        assert client.calendar_id == "primary"
        mock_creds.assert_called_once()

def test_google_calendar_client_init_missing_creds(monkeypatch):
    """Test GoogleCalendarClient initialization with missing credentials"""
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_TOKEN_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", raising=False)
    
    with patch('os.path.exists', return_value=False):
        with pytest.raises(ValueError, match="No valid Google Calendar credentials found"):
            GoogleCalendarClient()

def test_parse_natural_time():
    """Test natural language time parsing"""
    reference = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz.tzlocal())  # Monday
    
    # Test "today"
    result = parse_natural_time("today at 2pm", reference)
    assert result.date() == reference.date()
    assert result.hour == 14
    
    # Test "tomorrow"
    result = parse_natural_time("tomorrow at 9am", reference)
    assert result.date() == (reference + timedelta(days=1)).date()
    assert result.hour == 9
    
    # Test "next tuesday"
    result = parse_natural_time("next tuesday at 3:30pm", reference)
    # Next Tuesday from Monday Jan 15, 2024 should be Jan 16, 2024
    assert result.weekday() == 1  # Tuesday
    assert result.hour == 15
    assert result.minute == 30
    
    # Test ISO format passthrough
    iso_time = "2024-01-20T14:00:00Z"
    result = parse_natural_time(iso_time)
    assert result.hour == 14

@patch('lye.calendar.GoogleCalendarClient')
def test_list_events(mock_client_class):
    """Test listing calendar events"""
    mock_client = MagicMock()
    mock_service = MagicMock()
    mock_client.service = mock_service
    mock_client.calendar_id = "primary"
    mock_client_class.return_value = mock_client
    
    # Mock API response
    mock_events = {
        'items': [{
            'id': 'event1',
            'summary': 'Test Meeting',
            'start': {'dateTime': '2024-01-15T10:00:00-05:00'},
            'end': {'dateTime': '2024-01-15T11:00:00-05:00'},
            'location': 'Conference Room',
            'description': 'Test description',
            'attendees': [{'email': 'test@example.com', 'responseStatus': 'accepted'}],
            'organizer': {'email': 'organizer@example.com'},
            'htmlLink': 'https://calendar.google.com/event1'
        }]
    }
    
    mock_service.events().list().execute.return_value = mock_events
    
    result = list_events(time_min="today", time_max="tomorrow")
    
    assert len(result) == 1
    assert result[0]['summary'] == 'Test Meeting'
    assert result[0]['location'] == 'Conference Room'

@patch('lye.calendar.GoogleCalendarClient')
def test_create_event(mock_client_class):
    """Test creating a calendar event"""
    mock_client = MagicMock()
    mock_service = MagicMock()
    mock_client.service = mock_service
    mock_client.calendar_id = "primary"
    mock_client_class.return_value = mock_client
    
    # Mock API response
    mock_created_event = {
        'id': 'new_event_id',
        'summary': 'New Meeting',
        'start': {'dateTime': '2024-01-20T14:00:00-05:00'},
        'end': {'dateTime': '2024-01-20T15:00:00-05:00'},
        'htmlLink': 'https://calendar.google.com/new_event'
    }
    
    mock_service.events().insert().execute.return_value = mock_created_event
    
    result = create_event(
        summary="New Meeting",
        start_time="tomorrow at 2pm",
        duration_minutes=60,
        description="Important meeting",
        location="Office",
        attendee_emails=["attendee@example.com"]
    )
    
    assert result is not None
    assert result['id'] == 'new_event_id'
    assert result['summary'] == 'New Meeting'
    assert result['status'] == 'created'

@patch('lye.calendar.GoogleCalendarClient')
def test_find_free_time(mock_client_class):
    """Test finding free time slots"""
    mock_client = MagicMock()
    mock_service = MagicMock()
    mock_client.service = mock_service
    mock_client.calendar_id = "primary"
    mock_client_class.return_value = mock_client
    
    # Mock freebusy response
    now = datetime.now(tz=tz.tzlocal())
    busy_start = (now + timedelta(hours=2)).isoformat()
    busy_end = (now + timedelta(hours=3)).isoformat()
    
    mock_freebusy = {
        'calendars': {
            'primary': {
                'busy': [
                    {'start': busy_start, 'end': busy_end}
                ]
            }
        }
    }
    
    mock_service.freebusy().query().execute.return_value = mock_freebusy
    
    result = find_free_time(
        duration_minutes=60,
        working_hours_only=True
    )
    
    # Should return free slots
    assert isinstance(result, list)
    # Each slot should have required fields
    if result:
        assert 'start' in result[0]
        assert 'end' in result[0]
        assert 'duration_minutes' in result[0]

@patch('lye.calendar.GoogleCalendarClient')
def test_cancel_event(mock_client_class):
    """Test cancelling an event"""
    mock_client = MagicMock()
    mock_service = MagicMock()
    mock_client.service = mock_service
    mock_client.calendar_id = "primary"
    mock_client_class.return_value = mock_client
    
    # Mock successful deletion
    mock_service.events().delete().execute.return_value = None
    
    result = cancel_event(event_id="event123", notify_attendees=True)
    
    assert result is True
    # Check that delete was called with correct parameters
    mock_service.events().delete.assert_called_with(
        calendarId='primary',
        eventId='event123',
        sendUpdates='all'
    )

@patch('lye.calendar.GoogleCalendarClient')
def test_check_conflicts(mock_client_class):
    """Test checking for conflicts"""
    mock_client = MagicMock()
    mock_service = MagicMock()
    mock_client.service = mock_service
    mock_client.calendar_id = "primary"
    mock_client_class.return_value = mock_client
    
    # Mock freebusy response with conflict
    conflict_start = "2024-01-20T14:00:00Z"
    conflict_end = "2024-01-20T15:00:00Z"
    
    mock_freebusy = {
        'calendars': {
            'primary': {
                'busy': [
                    {'start': conflict_start, 'end': conflict_end}
                ]
            }
        }
    }
    
    mock_service.freebusy().query().execute.return_value = mock_freebusy
    
    result = check_conflicts(
        start_time="2024-01-20T14:30:00Z",
        duration_minutes=30
    )
    
    assert result['has_conflicts'] is True
    assert len(result['conflicts']) == 1

def test_calendar_tools_export():
    """Test that calendar tools are properly exported"""
    from lye import CALENDAR_TOOLS
    
    # Check that tools are exported
    assert isinstance(CALENDAR_TOOLS, list)
    assert len(CALENDAR_TOOLS) > 0
    
    # Check tool structure
    for tool in CALENDAR_TOOLS:
        assert 'definition' in tool
        assert 'implementation' in tool
        assert 'function' in tool['definition']
        assert 'name' in tool['definition']['function']
        assert tool['definition']['function']['name'].startswith('calendar-')