#!/usr/bin/env python
"""
Simple script to test Google Calendar API connectivity.
Run with: uv run python scripts/test_calendar_setup.py
"""

from datetime import datetime, timedelta
from mcp_google import calendar


def test_calendar_connection():
    """Tests connection to Google Calendar API and prints calendar info to verify access."""
    print("Starting Google Calendar API test...")

    # Use the calendar module to get authenticated service
    service = calendar.get_calendar_service(scopes=calendar.CALENDAR_SCOPES)
    print("Authentication successful!")

    # Test 1: List available calendars
    print("\n=== Testing Calendar List ===")
    calendars_response = calendar.find_calendars(service)
    if calendars_response and calendars_response.items:
        print(f"Found {len(calendars_response.items)} calendars:")
        for cal in calendars_response.items[:3]:  # Show first 3 calendars
            print(f"  - {cal.summary} (ID: {cal.id}) - Access: {cal.accessRole}")
    else:
        print("No calendars found or error occurred.")
        return

    # Test 2: Get recent events from primary calendar
    print("\n=== Testing Event Retrieval ===")
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)  # Last 7 days
    
    events_response = calendar.find_events(
        service,
        calendar_id='primary',
        time_min=start_time,
        time_max=end_time,
        max_results=5
    )
    
    if events_response and events_response.items:
        print(f"Found {len(events_response.items)} recent events:")
        for event in events_response.items:
            start_str = "Unknown start"
            if event.start:
                if event.start.dateTime:
                    start_str = event.start.dateTime.strftime("%Y-%m-%d %H:%M")
                elif event.start.date:
                    start_str = event.start.date.strftime("%Y-%m-%d") + " (All Day)"
            
            print(f"  - {event.summary or 'No Title'} ({start_str})")
    else:
        print("No recent events found (this is normal if you have no events in the last 7 days).")

    # Test 3: Test creating a test event (we'll delete it right after)
    print("\n=== Testing Event Creation ===")
    try:
        # Create a simple test event 1 hour from now
        test_start = datetime.now() + timedelta(hours=1)
        test_end = test_start + timedelta(minutes=30)
        
        # Use quick add for simplicity
        test_event = calendar.quick_add_event(
            service, 
            f"MCP Test Event at {test_start.strftime('%I:%M %p')}",
            calendar_id='primary'
        )
        
        if test_event:
            print(f"✅ Successfully created test event: {test_event.id}")
            
            # Clean up: Delete the test event
            deleted = calendar.delete_event(service, test_event.id, calendar_id='primary')
            if deleted:
                print("✅ Successfully deleted test event (cleanup complete)")
            else:
                print(f"⚠️  Test event created but couldn't delete it. You may want to manually delete event: {test_event.id}")
        else:
            print("❌ Failed to create test event")
    
    except Exception as e:
        print(f"❌ Error during event creation test: {e}")

    print("\n✅ SUCCESS: Your Google Calendar API setup is working correctly!")
    print("\nAPI access test completed.")


if __name__ == "__main__":
    test_calendar_connection()