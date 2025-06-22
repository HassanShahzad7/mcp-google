"""
Pydantic models for Google Calendar API resources and requests.
"""

import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any


class EventDateTime(BaseModel):
    """Represents the start or end time of an event."""
    date: Optional[datetime.date] = None
    dateTime: Optional[datetime.datetime] = None
    timeZone: Optional[str] = None

    class Config:
        populate_by_name = True


class EventAttendee(BaseModel):
    """Represents an attendee of an event."""
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    displayName: Optional[str] = None
    organizer: Optional[bool] = None
    self: Optional[bool] = None
    resource: Optional[bool] = None
    optional: Optional[bool] = None
    responseStatus: Optional[str] = None
    comment: Optional[str] = None
    additionalGuests: Optional[int] = None

    class Config:
        populate_by_name = True


class EventCreator(BaseModel):
    """Represents the creator of an event."""
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    displayName: Optional[str] = None
    self: Optional[bool] = None

    class Config:
        populate_by_name = True


class EventOrganizer(BaseModel):
    """Represents the organizer of an event."""
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    displayName: Optional[str] = None
    self: Optional[bool] = None

    class Config:
        populate_by_name = True


class EventReminderOverride(BaseModel):
    method: Optional[str] = None
    minutes: Optional[int] = None

    class Config:
        populate_by_name = True


class EventReminders(BaseModel):
    useDefault: bool = Field(..., alias="useDefault")
    overrides: Optional[List[EventReminderOverride]] = None

    class Config:
        populate_by_name = True


class GoogleCalendarEvent(BaseModel):
    """Pydantic model representing a Google Calendar event resource."""
    kind: str = "calendar#event"
    id: Optional[str] = Field(None, description="Opaque identifier of the event.")
    status: Optional[str] = Field(None, description="Status of the event.")
    htmlLink: Optional[str] = Field(None, description="URL for the event in the Google Calendar UI.")
    created: Optional[datetime.datetime] = Field(None, description="Creation time of the event.")
    updated: Optional[datetime.datetime] = Field(None, description="Last modification time of the event.")
    summary: Optional[str] = Field(None, description="Title of the event.")
    description: Optional[str] = Field(None, description="Description of the event.")
    location: Optional[str] = Field(None, description="Geographic location of the event.")
    colorId: Optional[str] = Field(None, description="Color of the event.")
    creator: Optional[EventCreator] = Field(None, description="The creator of the event.")
    organizer: Optional[EventOrganizer] = Field(None, description="The organizer of the event.")
    start: Optional[EventDateTime] = Field(None, description="The start time of the event.")
    end: Optional[EventDateTime] = Field(None, description="The end time of the event.")
    endTimeUnspecified: Optional[bool] = Field(None, description="Whether the end time is unspecified.")
    recurrence: Optional[List[str]] = Field(None, description="List of RRULE properties for recurring events.")
    recurringEventId: Optional[str] = Field(None, description="ID of the recurring event.")
    originalStartTime: Optional[EventDateTime] = Field(None, description="Original start time for recurring event instances.")
    attendees: Optional[List[EventAttendee]] = Field([], description="The attendees of the event.")
    attendeesOmitted: Optional[bool] = Field(None, description="Whether attendees were omitted.")
    reminders: Optional[EventReminders] = Field(None, description="Information about the event's reminders.")

    class Config:
        populate_by_name = True


class EventCreateRequest(BaseModel):
    """Model for creating a new event."""
    summary: str
    start: EventDateTime
    end: EventDateTime
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses.")
    recurrence: Optional[List[str]] = Field(None, description="List of RRULEs for recurring events.")
    reminders: Optional[EventReminders] = None


class EventUpdateRequest(BaseModel):
    """Model for updating an existing event."""
    summary: Optional[str] = None
    start: Optional[EventDateTime] = None
    end: Optional[EventDateTime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[EventAttendee]] = None


class CalendarListEntry(BaseModel):
    """Represents an entry in the user's calendar list."""
    kind: str = "calendar#calendarListEntry"
    etag: str
    id: str
    summary: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    timeZone: Optional[str] = None
    summaryOverride: Optional[str] = None
    colorId: Optional[str] = None
    backgroundColor: Optional[str] = None
    foregroundColor: Optional[str] = None
    hidden: Optional[bool] = None
    selected: Optional[bool] = None
    accessRole: Optional[str] = None
    defaultReminders: Optional[List[EventReminderOverride]] = None
    primary: Optional[bool] = None
    deleted: Optional[bool] = None

    class Config:
        populate_by_name = True


class EventsResponse(BaseModel):
    """Response containing a list of events."""
    kind: str = "calendar#events"
    summary: Optional[str] = None
    description: Optional[str] = None
    updated: Optional[datetime.datetime] = None
    timeZone: Optional[str] = None
    accessRole: Optional[str] = None
    defaultReminders: Optional[List[EventReminderOverride]] = []
    items: List[GoogleCalendarEvent] = []
    nextPageToken: Optional[str] = None
    nextSyncToken: Optional[str] = None

    class Config:
        populate_by_name = True


class CalendarListResponse(BaseModel):
    """Response containing a list of calendars."""
    kind: str = "calendar#calendarList"
    items: List[CalendarListEntry] = []
    nextPageToken: Optional[str] = None
    nextSyncToken: Optional[str] = None

    class Config:
        populate_by_name = True


class ProjectedEventOccurrence:
    """Represents a projected occurrence of a recurring event."""
    def __init__(self, original_event_id: str, original_summary: str, occurrence_start: datetime.datetime, occurrence_end: datetime.datetime):
        self.original_event_id = original_event_id
        self.original_summary = original_summary
        self.occurrence_start = occurrence_start
        self.occurrence_end = occurrence_end

    def __repr__(self):
        return f"ProjectedOccurrence(id='{self.original_event_id}', summary='{self.original_summary}', start='{self.occurrence_start}', end='{self.occurrence_end}')"