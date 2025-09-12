"""
Google Calendar Service - Comprehensive Implementation
=====================================================
A production-ready Calendar service with full CRUD operations,
advanced scheduling features, and intelligent conflict management.
"""

import logging
import re
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
import pytz
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
from aiogram import types
from aiogram.fsm.context import FSMContext

from services.base_service import BaseGoogleService
from states.bot_states import BotStates
from config import Config
from utils.date_parser import DateParser

logger = logging.getLogger(__name__)


class CalendarService(BaseGoogleService):
    """
    Comprehensive Google Calendar service with full functionality.
    Handles all calendar operations including CRUD, scheduling, and advanced features.
    """
    
    def __init__(self, auth_manager, config: Dict):
        """Initialize Calendar service with enhanced capabilities."""
        super().__init__(auth_manager, config)
        self.timezone = Config.DEFAULT_TIMEZONE
        self.date_parser = DateParser(self.timezone)
        self.search_results = {}  # Store search results for multi-step operations
        self.calendar_cache = {}  # Cache calendar metadata
        self.event_templates = {}  # Store event templates for duplication
        self.default_reminders = [
            {'method': 'popup', 'minutes': 10},
            {'method': 'email', 'minutes': 60}
        ]
    
    # ========================================================================
    # MAIN ACTION HANDLER - Routes all calendar actions
    # ========================================================================
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """
        Main router for all calendar actions.
        Maps action types to their specific handlers.
        """
        action_handlers = {
            # Basic CRUD operations
            'CREATE_EVENT': self.handle_create_event,
            'CREATE_MULTIPLE': self.handle_create_multiple_events,
            'CREATE_RECURRING': self.handle_create_recurring_event,
            'QUICK_ADD': self.handle_quick_add_event,
            
            # View operations - All time ranges
            'VIEW_EVENTS': self.handle_view_events,
            'VIEW_YESTERDAY': self.handle_view_yesterday,
            'VIEW_TODAY': self.handle_view_today,
            'VIEW_TOMORROW': self.handle_view_tomorrow,
            'VIEW_WEEKLY': self.handle_view_weekly,
            'VIEW_PREVIOUS_WEEK': self.handle_view_previous_week,
            'VIEW_NEXT_WEEK': self.handle_view_next_week,
            'VIEW_MONTHLY': self.handle_view_monthly,
            'VIEW_PREVIOUS_MONTH': self.handle_view_previous_month,
            'VIEW_NEXT_MONTH': self.handle_view_next_month,
            
            # Search and details
            'SEARCH_EVENTS': self.handle_search_events,
            'GET_EVENT_DETAILS': self.handle_get_event_details,
            
            # Update operations
            'UPDATE_EVENT': self.handle_update_event,
            'MOVE_EVENT': self.handle_move_event,
            'UPDATE_TITLE': self.handle_update_title,
            'UPDATE_LOCATION': self.handle_update_location,
            'UPDATE_DESCRIPTION': self.handle_update_description,
            
            # Delete operations
            'DELETE_EVENT': self.handle_delete_event,
            'DELETE_MULTIPLE': self.handle_delete_multiple_events,
            'CANCEL_ALL_DAY': self.handle_cancel_all_day,
            
            # Advanced features
            'ADD_ATTENDEES': self.handle_add_attendees,
            'REMOVE_ATTENDEES': self.handle_remove_attendees,
            'DUPLICATE_EVENT': self.handle_duplicate_event,
            'CHECK_CONFLICTS': self.handle_check_conflicts,
            'FIND_FREE_TIME': self.handle_find_free_time,
            'CHECK_AVAILABILITY': self.handle_check_availability,
            'BLOCK_TIME': self.handle_block_time,
            'SET_OUT_OF_OFFICE': self.handle_set_out_of_office,
            
            # Calendar management
            'LIST_CALENDARS': self.handle_list_calendars,
            'SWITCH_CALENDAR': self.handle_switch_calendar,
            'EXPORT_EVENTS': self.handle_export_events,
            'IMPORT_EVENTS': self.handle_import_events,
            
            # Reminder management
            'ADD_REMINDER': self.handle_add_reminder,
            'REMOVE_REMINDER': self.handle_remove_reminder,
            'UPDATE_REMINDERS': self.handle_update_reminders,
        }
        
        handler = action_handlers.get(action)
        if handler:
            try:
                return await handler(params, message, state)
            except Exception as e:
                logger.error(f"Error in {action}: {e}", exc_info=True)
                return {'success': False, 'message': f'❌ Error: {str(e)}'}
        
        return {'success': False, 'message': f'❌ Unknown calendar action: {action}'}
    
    # ========================================================================
    # CREATE EVENT HANDLERS
    # ========================================================================
    
    async def handle_create_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """
        Create a single calendar event with comprehensive validation and conflict checking.
        """
        try:
            # Extract and validate parameters
            title = params.get('title', 'New Event')
            date_str = params.get('date', 'today')
            time_str = params.get('time', '12:00 PM')
            duration = self.date_parser.parse_duration(params.get('duration', '1 hour'))
            
            # Parse date and time
            event_date = self.date_parser.parse_date(date_str)
            hour, minute = self.date_parser.parse_time(time_str)
            
            # Create datetime objects with timezone
            start_dt = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if not start_dt.tzinfo:
                start_dt = self.timezone.localize(start_dt)
            end_dt = start_dt + timedelta(hours=duration)
            
            # Additional event details
            location = params.get('location', '')
            description = params.get('description', '')
            attendees = self._parse_attendees(params.get('attendees', ''))
            calendar_id = params.get('calendar_id', 'primary')
            reminders = params.get('reminders', self.default_reminders)
            
            # Check for conflicts
            conflicts = await self._check_for_conflicts(start_dt, end_dt, calendar_id)
            
            # Build event data
            event_data = {
                'summary': title,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': str(self.timezone)
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': str(self.timezone)
                },
                'description': description,
                'location': location,
                'reminders': {
                    'useDefault': False,
                    'overrides': reminders
                }
            }
            
            # Add attendees if provided
            if attendees:
                event_data['attendees'] = [{'email': email} for email in attendees]
                event_data['sendUpdates'] = 'all'
            
            # Handle conflicts
            if conflicts and not params.get('force', False):
                # Store data for confirmation
                await state.update_data(
                    service='calendar',
                    action='create_with_conflicts',
                    event_data=event_data,
                    conflicts=conflicts
                )
                await state.set_state(BotStates.confirming_action)
                
                # Format conflict message
                conflict_msg = self._format_conflict_message(conflicts, start_dt, end_dt, title)
                await message.answer(conflict_msg, parse_mode='Markdown')
                return {'success': True}
            
            # Create the event
            result = await self.make_api_call(
                'POST',
                f'calendars/{calendar_id}/events',
                json_data=event_data
            )
            
            if result['success']:
                created_event = result['data']
                response = self._format_event_created_message(created_event, start_dt, end_dt)
                return {'success': True, 'message': response}
            
            return {'success': False, 'message': f"❌ Failed to create event: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return {'success': False, 'message': f'❌ Error creating event: {str(e)}'}
    
    async def handle_create_multiple_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create multiple events at once."""
        try:
            count = int(params.get('count', 1))
            base_title = params.get('title', 'Event')
            base_date = self.date_parser.parse_date(params.get('date', 'today'))
            interval_hours = float(params.get('interval', 1))
            
            created_events = []
            failed_events = []
            
            for i in range(count):
                # Calculate start time for each event
                start_dt = base_date + timedelta(hours=interval_hours * i)
                
                # Create event params
                event_params = params.copy()
                event_params['title'] = f"{base_title} {i+1}" if count > 1 else base_title
                event_params['date'] = start_dt.strftime('%Y-%m-%d')
                event_params['time'] = start_dt.strftime('%I:%M %p')
                
                # Create event
                result = await self.handle_create_event(event_params, message, state)
                
                if result['success']:
                    created_events.append(event_params['title'])
                else:
                    failed_events.append(event_params['title'])
            
            # Format response
            response = f"📅 **Created {len(created_events)} events:**\n"
            for event_title in created_events:
                response += f"✅ {event_title}\n"
            
            if failed_events:
                response += f"\n❌ **Failed to create {len(failed_events)} events**"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error creating multiple events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_create_recurring_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create a recurring event with RRULE support."""
        try:
            # Parse recurrence parameters
            frequency = params.get('frequency', 'WEEKLY').upper()
            count = int(params.get('count', 10))
            interval = int(params.get('interval', 1))
            until_date = params.get('until')
            by_day = params.get('by_day', '')  # e.g., "MO,WE,FR"
            
            # Build RRULE
            rrule_parts = [f"FREQ={frequency}"]
            
            if until_date:
                until_dt = self.date_parser.parse_date(until_date)
                rrule_parts.append(f"UNTIL={until_dt.strftime('%Y%m%dT000000Z')}")
            else:
                rrule_parts.append(f"COUNT={count}")
            
            if interval > 1:
                rrule_parts.append(f"INTERVAL={interval}")
            
            if by_day:
                rrule_parts.append(f"BYDAY={by_day}")
            
            rrule_string = f"RRULE:{';'.join(rrule_parts)}"
            
            # Add recurrence to event params
            params['recurrence'] = [rrule_string]
            
            # Create the recurring event
            result = await self.handle_create_event(params, message, state)
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Recurring event created!**\n"
                              f"Frequency: {frequency}\n"
                              f"Occurrences: {count if not until_date else 'Until ' + until_date}"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating recurring event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_quick_add_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Quick add event using natural language."""
        try:
            text = params.get('text', '')
            calendar_id = params.get('calendar_id', 'primary')
            
            if not text:
                return {'success': False, 'message': '❌ Event description required'}
            
            # Use Google's quick add feature
            result = await self.make_api_call(
                'POST',
                f'calendars/{calendar_id}/events/quickAdd',
                params={'text': text}
            )
            
            if result['success']:
                event = result['data']
                return {
                    'success': True,
                    'message': f"✅ **Event created:** {event.get('summary', 'Event')}\n"
                              f"📅 {self._format_event_time(event)}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error in quick add: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # VIEW EVENT HANDLERS
    # ========================================================================
    
    async def handle_view_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View events for a specific date or range."""
        try:
            range_filter = params.get('range', 'today')
            calendar_id = params.get('calendar_id', 'primary')
            max_results = int(params.get('max_results', 50))
            
            # Get events
            events = await self._get_events_for_range(range_filter, calendar_id, max_results)
            
            if not events:
                # Better message for different ranges
                range_messages = {
                    'yesterday': '📭 **No events yesterday**',
                    'today': '📭 **No events today**',
                    'tomorrow': '📭 **No events tomorrow**',
                    'week': '📭 **No events this week**',
                    'this week': '📭 **No events this week**',
                    'last_week': '📭 **No events last week**',
                    'previous_week': '📭 **No events last week**',
                    'last week': '📭 **No events last week**',
                    'previous week': '📭 **No events last week**',
                    'next_week': '📭 **No events next week**',
                    'next week': '📭 **No events next week**',
                    'month': '📭 **No events this month**',
                    'this month': '📭 **No events this month**',
                    'last_month': '📭 **No events last month**',
                    'previous_month': '📭 **No events last month**',
                    'last month': '📭 **No events last month**',
                    'previous month': '📭 **No events last month**',
                    'next_month': '📭 **No events next month**',
                    'next month': '📭 **No events next month**'
                }
                
                no_events_msg = range_messages.get(
                    range_filter.lower().replace('_', ' '), 
                    f'📭 **No events for {range_filter}**'
                )
                
                return {'success': True, 'message': no_events_msg}
            
            # Format response
            response = self._format_events_display(events, range_filter)
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error viewing events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_view_yesterday(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View yesterday's calendar."""
        params['range'] = 'yesterday'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_today(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View today's calendar."""
        params['range'] = 'today'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_tomorrow(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View tomorrow's calendar."""
        params['range'] = 'tomorrow'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_weekly(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View weekly calendar with day-by-day breakdown."""
        params['range'] = 'week'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_previous_week(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View previous week's calendar."""
        params['range'] = 'last_week'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_next_week(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View next week's calendar."""
        params['range'] = 'next_week'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_monthly(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View monthly calendar."""
        params['range'] = 'month'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_previous_month(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View previous month's calendar."""
        params['range'] = 'last_month'
        return await self.handle_view_events(params, message, state)
    
    async def handle_view_next_month(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View next month's calendar."""
        params['range'] = 'next_month'
        return await self.handle_view_events(params, message, state)
    
    async def handle_search_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Search for events by query string."""
        try:
            query = params.get('query', '')
            calendar_id = params.get('calendar_id', 'primary')
            max_results = int(params.get('max_results', 20))
            
            if not query:
                return {'success': False, 'message': '❌ Search query required'}
            
            # Search events
            events = await self._search_events(query, calendar_id, max_results)
            
            if not events:
                return {'success': True, 'message': f'📭 **No events found for:** "{query}"'}
            
            # Store results for potential actions
            user_id = message.from_user.id
            self.search_results[user_id] = events
            
            # Format response
            response = f"🔍 **Search results for '{query}' ({len(events)} found):**\n\n"
            
            for i, event in enumerate(events[:15], 1):
                response += f"**{i}. {event.get('summary', 'Untitled')}**\n"
                response += f"   📅 {self._format_event_time(event)}\n"
                
                if event.get('location'):
                    response += f"   📍 {event['location']}\n"
                
                response += "\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error searching events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_get_event_details(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Get detailed information about a specific event."""
        try:
            event_id = params.get('event_id')
            title = params.get('title')
            calendar_id = params.get('calendar_id', 'primary')
            
            # Get event by ID or search by title
            if event_id:
                result = await self.make_api_call('GET', f'calendars/{calendar_id}/events/{event_id}')
                if not result['success']:
                    return {'success': False, 'message': '❌ Event not found'}
                event = result['data']
            elif title:
                events = await self._search_events(title, calendar_id, 1)
                if not events:
                    return {'success': False, 'message': f'❌ No event found with title: {title}'}
                event = events[0]
            else:
                return {'success': False, 'message': '❌ Event ID or title required'}
            
            # Format detailed response
            response = self._format_event_details(event)
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error getting event details: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # UPDATE EVENT HANDLERS
    # ========================================================================
    
    async def handle_update_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update an event with flexible parameter handling."""
        try:
            # Find the event to update
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Prepare update data
            update_data = await self._prepare_update_data(event, params)
            
            # Check for conflicts if time is being changed
            if 'start' in update_data or 'end' in update_data:
                conflicts = await self._check_for_conflicts(
                    datetime.fromisoformat(update_data['start']['dateTime']),
                    datetime.fromisoformat(update_data['end']['dateTime']),
                    params.get('calendar_id', 'primary'),
                    exclude_event_id=event['id']
                )
                
                if conflicts and not params.get('force', False):
                    # Request confirmation
                    await state.update_data(
                        service='calendar',
                        action='update_with_conflicts',
                        event_id=event['id'],
                        update_data=update_data,
                        conflicts=conflicts
                    )
                    await state.set_state(BotStates.confirming_action)
                    
                    conflict_msg = "⚠️ **Conflicts detected!**\n" + self._format_conflict_list(conflicts)
                    conflict_msg += "\n\nReply 'yes' to proceed anyway or 'no' to cancel."
                    await message.answer(conflict_msg, parse_mode='Markdown')
                    return {'success': True}
            
            # Update the event
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data
            )
            
            if result['success']:
                return {'success': True, 'message': '✅ **Event updated successfully!**'}
            
            return {'success': False, 'message': f"❌ Failed to update: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_move_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Move/reschedule an event to a new time."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Parse new date and time
            new_date = self.date_parser.parse_date(params.get('new_date', 'tomorrow'))
            new_time = params.get('new_time', '')
            
            if new_time:
                hour, minute = self.date_parser.parse_time(new_time)
            else:
                # Keep original time
                start_dt = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                hour, minute = start_dt.hour, start_dt.minute
            
            # Calculate new start and end times
            new_start = new_date.replace(hour=hour, minute=minute)
            if not new_start.tzinfo:
                new_start = self.timezone.localize(new_start)
            
            # Keep original duration
            duration = self._calculate_event_duration(event)
            new_end = new_start + duration
            
            # Prepare update with new times
            params['new_start'] = new_start.isoformat()
            params['new_end'] = new_end.isoformat()
            
            return await self.handle_update_event(params, message, state)
            
        except Exception as e:
            logger.error(f"Error moving event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_update_title(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update only the title of an event."""
        params['new_title'] = params.get('new_title', params.get('title', ''))
        return await self.handle_update_event(params, message, state)
    
    async def handle_update_location(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update only the location of an event."""
        params['new_location'] = params.get('new_location', params.get('location', ''))
        return await self.handle_update_event(params, message, state)
    
    async def handle_update_description(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update or add description/notes to an event."""
        params['new_description'] = params.get('new_description', params.get('description', ''))
        return await self.handle_update_event(params, message, state)
    
    # ========================================================================
    # DELETE EVENT HANDLERS
    # ========================================================================
    
    async def handle_delete_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Delete a single event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Confirm deletion for important events
            if event.get('attendees') and not params.get('confirmed', False):
                await state.update_data(
                    service='calendar',
                    action='delete_with_attendees',
                    event_id=event['id'],
                    event_title=event.get('summary', 'Event')
                )
                await state.set_state(BotStates.confirming_action)
                
                confirm_msg = f"⚠️ **This event has {len(event['attendees'])} attendees.**\n"
                confirm_msg += f"Event: {event.get('summary', 'Untitled')}\n"
                confirm_msg += "Reply 'yes' to cancel and notify attendees, or 'no' to keep the event."
                
                await message.answer(confirm_msg, parse_mode='Markdown')
                return {'success': True}
            
            # Delete the event
            calendar_id = params.get('calendar_id', 'primary')
            send_updates = 'all' if event.get('attendees') else 'none'
            
            result = await self.make_api_call(
                'DELETE',
                f'calendars/{calendar_id}/events/{event["id"]}',
                params={'sendUpdates': send_updates}
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Deleted:** {event.get('summary', 'Event')}"
                }
            
            return {'success': False, 'message': f"❌ Failed to delete: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error deleting event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_delete_multiple_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Delete multiple events at once."""
        try:
            event_ids = params.get('event_ids', [])
            titles = params.get('titles', [])
            calendar_id = params.get('calendar_id', 'primary')
            
            # Find events by titles if IDs not provided
            if not event_ids and titles:
                events = []
                for title in titles:
                    found = await self._search_events(title, calendar_id, 1)
                    if found:
                        events.extend(found)
                event_ids = [e['id'] for e in events]
            
            if not event_ids:
                return {'success': False, 'message': '❌ No events specified for deletion'}
            
            # Delete each event
            deleted = []
            failed = []
            
            for event_id in event_ids:
                result = await self.make_api_call(
                    'DELETE',
                    f'calendars/{calendar_id}/events/{event_id}'
                )
                
                if result['success']:
                    deleted.append(event_id)
                else:
                    failed.append(event_id)
            
            # Format response
            response = f"✅ **Deleted {len(deleted)} events**"
            if failed:
                response += f"\n❌ **Failed to delete {len(failed)} events**"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error deleting multiple events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_cancel_all_day(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Cancel all events for a specific day."""
        try:
            date_str = params.get('date', 'today')
            calendar_id = params.get('calendar_id', 'primary')
            
            # Parse date
            target_date = self.date_parser.parse_date(date_str)
            
            # Get all events for the day
            events = await self._get_events_for_date(target_date, calendar_id)
            
            if not events:
                return {
                    'success': True,
                    'message': f'📭 **No events on {target_date.strftime("%A, %B %d")}**'
                }
            
            # Confirm cancellation
            if not params.get('confirmed', False):
                await state.update_data(
                    service='calendar',
                    action='cancel_all_day',
                    date=target_date.isoformat(),
                    event_ids=[e['id'] for e in events]
                )
                await state.set_state(BotStates.confirming_action)
                
                confirm_msg = f"⚠️ **Cancel all {len(events)} events on {target_date.strftime('%A, %B %d')}?**\n\n"
                for event in events:
                    confirm_msg += f"• {event.get('summary', 'Untitled')}\n"
                confirm_msg += "\nReply 'yes' to cancel all or 'no' to keep them."
                
                await message.answer(confirm_msg, parse_mode='Markdown')
                return {'success': True}
            
            # Delete all events
            params['event_ids'] = [e['id'] for e in events]
            return await self.handle_delete_multiple_events(params, message, state)
            
        except Exception as e:
            logger.error(f"Error canceling all day events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # ATTENDEE MANAGEMENT
    # ========================================================================
    
    async def handle_add_attendees(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Add attendees to an existing event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Parse new attendees
            new_attendees = self._parse_attendees(params.get('attendees', ''))
            
            if not new_attendees:
                return {'success': False, 'message': '❌ No attendees specified'}
            
            # Get existing attendees
            existing_attendees = event.get('attendees', [])
            existing_emails = {a['email'] for a in existing_attendees}
            
            # Add new attendees
            for email in new_attendees:
                if email not in existing_emails:
                    existing_attendees.append({'email': email})
            
            # Update event
            update_data = event.copy()
            update_data['attendees'] = existing_attendees
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data,
                params={'sendUpdates': 'all'}
            )
            
            if result['success']:
                added_count = len(new_attendees) - len(existing_emails.intersection(new_attendees))
                return {
                    'success': True,
                    'message': f"✅ **Added {added_count} attendees to:** {event.get('summary', 'Event')}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error adding attendees: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_remove_attendees(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Remove attendees from an event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Parse attendees to remove
            remove_emails = self._parse_attendees(params.get('attendees', ''))
            
            if not remove_emails:
                return {'success': False, 'message': '❌ No attendees specified'}
            
            # Filter out specified attendees
            existing_attendees = event.get('attendees', [])
            updated_attendees = [
                a for a in existing_attendees 
                if a['email'] not in remove_emails
            ]
            
            removed_count = len(existing_attendees) - len(updated_attendees)
            
            if removed_count == 0:
                return {'success': True, 'message': '⚠️ No matching attendees found to remove'}
            
            # Update event
            update_data = event.copy()
            update_data['attendees'] = updated_attendees
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data,
                params={'sendUpdates': 'all'}
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Removed {removed_count} attendees from:** {event.get('summary', 'Event')}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error removing attendees: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # ADVANCED FEATURES
    # ========================================================================
    
    async def handle_duplicate_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Duplicate an existing event."""
        try:
            # Find the event to duplicate
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Create a copy of the event
            new_event = {
                'summary': params.get('new_title', f"Copy of {event.get('summary', 'Event')}"),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'attendees': event.get('attendees', []) if params.get('copy_attendees', False) else [],
                'reminders': event.get('reminders', self.default_reminders)
            }
            
            # Set new date/time
            if params.get('new_date'):
                new_date = self.date_parser.parse_date(params['new_date'])
                # Keep original time
                if 'dateTime' in event.get('start', {}):
                    orig_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    new_start = new_date.replace(hour=orig_start.hour, minute=orig_start.minute)
                    
                    duration = self._calculate_event_duration(event)
                    new_end = new_start + duration
                    
                    new_event['start'] = {
                        'dateTime': new_start.isoformat(),
                        'timeZone': str(self.timezone)
                    }
                    new_event['end'] = {
                        'dateTime': new_end.isoformat(),
                        'timeZone': str(self.timezone)
                    }
                else:
                    # All-day event
                    new_event['start'] = {'date': new_date.strftime('%Y-%m-%d')}
                    new_event['end'] = {'date': (new_date + timedelta(days=1)).strftime('%Y-%m-%d')}
            else:
                # Copy original times
                new_event['start'] = event['start']
                new_event['end'] = event['end']
            
            # Create the duplicated event
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'POST',
                f'calendars/{calendar_id}/events',
                json_data=new_event
            )
            
            if result['success']:
                created = result['data']
                return {
                    'success': True,
                    'message': f"✅ **Event duplicated!**\n"
                              f"Original: {event.get('summary', 'Event')}\n"
                              f"New: {created.get('summary', 'Event')}\n"
                              f"📅 {self._format_event_time(created)}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error duplicating event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_check_conflicts(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Check for scheduling conflicts."""
        try:
            # Parse date and time
            date_str = params.get('date', 'today')
            time_str = params.get('time', '12:00 PM')
            duration = self.date_parser.parse_duration(params.get('duration', '1 hour'))
            calendar_id = params.get('calendar_id', 'primary')
            
            # Create datetime range
            event_date = self.date_parser.parse_date(date_str)
            hour, minute = self.date_parser.parse_time(time_str)
            start_dt = event_date.replace(hour=hour, minute=minute)
            if not start_dt.tzinfo:
                start_dt = self.timezone.localize(start_dt)
            end_dt = start_dt + timedelta(hours=duration)
            
            # Check for conflicts
            conflicts = await self._check_for_conflicts(start_dt, end_dt, calendar_id)
            
            if not conflicts:
                return {
                    'success': True,
                    'message': f"✅ **No conflicts found!**\n"
                              f"Time slot available: {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
                              f"Date: {start_dt.strftime('%A, %B %d')}"
                }
            
            # Format conflict response
            response = f"⚠️ **{len(conflicts)} conflict(s) found:**\n\n"
            for event in conflicts:
                response += f"• **{event.get('summary', 'Untitled')}**\n"
                response += f"  {self._format_event_time(event)}\n\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_find_free_time(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Find available time slots."""
        try:
            duration = float(params.get('duration', 1))  # hours
            days_ahead = int(params.get('days_ahead', 7))
            start_hour = int(params.get('start_hour', 9))
            end_hour = int(params.get('end_hour', 17))
            calendar_id = params.get('calendar_id', 'primary')
            
            free_slots = []
            today = datetime.now(self.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
            
            for day_offset in range(days_ahead):
                check_date = today + timedelta(days=day_offset)
                
                # Skip weekends if requested
                if params.get('weekdays_only', False) and check_date.weekday() >= 5:
                    continue
                
                # Get events for this day
                events = await self._get_events_for_date(check_date, calendar_id)
                
                # Find free slots
                day_slots = self._calculate_free_slots(
                    events, check_date, start_hour, end_hour, duration
                )
                
                free_slots.extend(day_slots)
                
                # Stop if we have enough slots
                if len(free_slots) >= 10:
                    break
            
            if not free_slots:
                return {
                    'success': True,
                    'message': f"❌ **No {duration}h free slots found in the next {days_ahead} days**"
                }
            
            # Format response
            response = f"🕐 **Available {duration}h slots:**\n\n"
            
            for slot in free_slots[:10]:
                response += f"• **{slot['date'].strftime('%a %b %d')}:** "
                response += f"{slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error finding free time: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_check_availability(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Check availability for a specific date/time."""
        try:
            date_str = params.get('date', 'today')
            calendar_id = params.get('calendar_id', 'primary')
            
            # Parse date
            check_date = self.date_parser.parse_date(date_str)
            
            # Get events for the date
            events = await self._get_events_for_date(check_date, calendar_id)
            
            if not events:
                return {
                    'success': True,
                    'message': f"✅ **You're completely free on {check_date.strftime('%A, %B %d')}!**"
                }
            
            # Calculate free and busy times
            free_slots = self._calculate_free_slots(events, check_date, 0, 24, 0.5)
            
            # Format response
            response = f"📅 **Availability for {check_date.strftime('%A, %B %d')}:**\n\n"
            
            response += f"**Scheduled ({len(events)} events):**\n"
            for event in events:
                response += f"• {self._format_event_summary(event)}\n"
            
            if free_slots:
                response += f"\n**Free times:**\n"
                for slot in free_slots:
                    if (slot['end'] - slot['start']).total_seconds() >= 1800:  # At least 30 minutes
                        response += f"• {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_block_time(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Block time on calendar (create busy event)."""
        # Set default title and mark as busy
        params['title'] = params.get('title', 'Busy')
        params['description'] = params.get('description', 'Time blocked')
        params['transparency'] = 'opaque'  # Shows as busy
        params['visibility'] = params.get('visibility', 'private')
        
        return await self.handle_create_event(params, message, state)
    
    async def handle_set_out_of_office(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Set out of office status."""
        try:
            start_date = self.date_parser.parse_date(params.get('start_date', 'today'))
            end_date = self.date_parser.parse_date(params.get('end_date', params.get('start_date', 'today')))
            message_text = params.get('message', 'I am currently out of office')
            
            # Create all-day out of office event
            event_data = {
                'summary': 'Out of Office',
                'description': message_text,
                'start': {'date': start_date.strftime('%Y-%m-%d')},
                'end': {'date': (end_date + timedelta(days=1)).strftime('%Y-%m-%d')},
                'transparency': 'opaque',
                'visibility': 'public',
                'reminders': {'useDefault': False}
            }
            
            # Add response status
            if params.get('auto_decline', False):
                event_data['responseStatus'] = 'declined'
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'POST',
                f'calendars/{calendar_id}/events',
                json_data=event_data
            )
            
            if result['success']:
                days = (end_date - start_date).days + 1
                return {
                    'success': True,
                    'message': f"✅ **Out of Office set!**\n"
                              f"Duration: {days} day{'s' if days > 1 else ''}\n"
                              f"From: {start_date.strftime('%B %d')}\n"
                              f"To: {end_date.strftime('%B %d')}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error setting out of office: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # CALENDAR MANAGEMENT
    # ========================================================================
    
    async def handle_list_calendars(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List all available calendars."""
        try:
            result = await self.make_api_call('GET', 'users/me/calendarList')
            
            if not result['success']:
                return {'success': False, 'message': '❌ Failed to get calendars'}
            
            calendars = result.get('data', {}).get('items', [])
            
            # Format response
            response = "📅 **Your Calendars:**\n\n"
            
            for cal in calendars:
                response += f"• **{cal.get('summary', 'Unnamed')}**"
                
                if cal.get('primary'):
                    response += " 🌟 (Primary)"
                
                if cal.get('description'):
                    response += f"\n  {cal['description'][:50]}"
                
                response += f"\n  ID: `{cal['id']}`\n\n"
            
            # Cache calendar list
            user_id = message.from_user.id
            self.calendar_cache[user_id] = calendars
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error listing calendars: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_switch_calendar(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Switch active calendar (store preference)."""
        calendar_name = params.get('calendar_name', '')
        user_id = message.from_user.id
        
        # Get calendar list
        if user_id not in self.calendar_cache:
            await self.handle_list_calendars({}, message, state)
        
        calendars = self.calendar_cache.get(user_id, [])
        
        # Find matching calendar
        matched = None
        for cal in calendars:
            if calendar_name.lower() in cal.get('summary', '').lower():
                matched = cal
                break
        
        if matched:
            # Store preference (would need persistent storage in production)
            return {
                'success': True,
                'message': f"✅ **Switched to calendar:** {matched['summary']}"
            }
        
        return {'success': False, 'message': f'❌ Calendar "{calendar_name}" not found'}
    
    async def handle_export_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Export events to a file format."""
        # This would generate an ICS file or similar
        return {
            'success': True,
            'message': '📤 **Export feature coming soon!**\nEvents can be exported from Google Calendar web interface.'
        }
    
    async def handle_import_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Import events from a file."""
        # This would parse an ICS file or similar
        return {
            'success': True,
            'message': '📥 **Import feature coming soon!**\nEvents can be imported via Google Calendar web interface.'
        }
    
    # ========================================================================
    # REMINDER MANAGEMENT
    # ========================================================================
    
    async def handle_add_reminder(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Add reminder to an event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Parse reminder settings
            minutes = int(params.get('minutes', 10))
            method = params.get('method', 'popup')  # popup, email, sms
            
            # Get existing reminders
            reminders = event.get('reminders', {})
            overrides = reminders.get('overrides', [])
            
            # Add new reminder
            new_reminder = {'method': method, 'minutes': minutes}
            
            # Check if already exists
            if new_reminder not in overrides:
                overrides.append(new_reminder)
            else:
                return {'success': True, 'message': '⚠️ This reminder already exists'}
            
            # Update event
            update_data = event.copy()
            update_data['reminders'] = {
                'useDefault': False,
                'overrides': overrides
            }
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Reminder added!**\n"
                              f"Event: {event.get('summary', 'Event')}\n"
                              f"Alert: {minutes} minutes before via {method}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_remove_reminder(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Remove reminders from an event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Update event to remove reminders
            update_data = event.copy()
            update_data['reminders'] = {'useDefault': False, 'overrides': []}
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Reminders removed from:** {event.get('summary', 'Event')}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error removing reminder: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_update_reminders(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update all reminders for an event."""
        try:
            # Find the event
            event = await self._find_event_for_update(params, message.from_user.id)
            
            if not event:
                return {'success': False, 'message': '❌ Event not found'}
            
            # Parse new reminders
            reminders_str = params.get('reminders', '10,30,60')  # minutes
            reminder_minutes = [int(m.strip()) for m in reminders_str.split(',')]
            
            # Create reminder objects
            overrides = [
                {'method': 'popup', 'minutes': m} for m in reminder_minutes
            ]
            
            # Update event
            update_data = event.copy()
            update_data['reminders'] = {
                'useDefault': False,
                'overrides': overrides
            }
            
            calendar_id = params.get('calendar_id', 'primary')
            result = await self.make_api_call(
                'PUT',
                f'calendars/{calendar_id}/events/{event["id"]}',
                json_data=update_data
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"✅ **Reminders updated!**\n"
                              f"Event: {event.get('summary', 'Event')}\n"
                              f"Alerts: {', '.join(str(m) + ' min' for m in reminder_minutes)}"
                }
            
            return {'success': False, 'message': f"❌ Failed: {result.get('error')}"}
            
        except Exception as e:
            logger.error(f"Error updating reminders: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_events_for_range(self, range_filter: str, calendar_id: str, max_results: int) -> List[Dict]:
        """Get events for a specific time range."""
        now = datetime.now(self.timezone)
        
        # Normalize range filter
        range_filter = range_filter.lower().replace('_', ' ')
        
        # Determine time range
        if range_filter == 'yesterday':
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'tomorrow':
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter in ['week', 'this week']:
            # Current week (Monday to Sunday)
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif range_filter in ['last week', 'previous week']:
            # Previous week (Monday to Sunday)
            start = now - timedelta(days=now.weekday() + 7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif range_filter in ['next week']:
            # Next week (Monday to Sunday)
            start = now - timedelta(days=now.weekday()) + timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif range_filter in ['month', 'this month']:
            # Current month
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Get first day of next month
            if now.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif range_filter in ['last month', 'previous month']:
            # Previous month
            if now.month == 1:
                start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif range_filter in ['next month']:
            # Next month
            if now.month == 12:
                start = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end = start.replace(month=2, day=1) if start.month == 1 else start.replace(month=start.month + 1, day=1)
            else:
                start = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
                if start.month == 12:
                    end = start.replace(year=start.year + 1, month=1, day=1)
                else:
                    end = start.replace(month=start.month + 1, day=1)
        else:
            # Default to today
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        
        # Convert to UTC for API
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)
        
        # API call
        params = {
            'timeMin': start_utc.isoformat(),
            'timeMax': end_utc.isoformat(),
            'singleEvents': 'true',
            'orderBy': 'startTime',
            'maxResults': max_results
        }
        
        result = await self.make_api_call('GET', f'calendars/{calendar_id}/events', params=params)
        
        if result['success']:
            return result.get('data', {}).get('items', [])
        
        return []
    
    
    async def _get_events_for_date(self, target_date: datetime, calendar_id: str) -> List[Dict]:
        """Get all events for a specific date."""
        start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if not start.tzinfo:
            start = self.timezone.localize(start)
        end = start + timedelta(days=1)
        
        # Convert to UTC
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)
        
        params = {
            'timeMin': start_utc.isoformat(),
            'timeMax': end_utc.isoformat(),
            'singleEvents': 'true',
            'orderBy': 'startTime'
        }
        
        result = await self.make_api_call('GET', f'calendars/{calendar_id}/events', params=params)
        
        if result['success']:
            return result.get('data', {}).get('items', [])
        
        return []
    
    async def _search_events(self, query: str, calendar_id: str, max_results: int) -> List[Dict]:
        """Search for events matching a query."""
        # Get events from next 30 days
        now = datetime.now(self.timezone)
        start_utc = now.astimezone(pytz.UTC)
        end_utc = (now + timedelta(days=30)).astimezone(pytz.UTC)
        
        params = {
            'timeMin': start_utc.isoformat(),
            'timeMax': end_utc.isoformat(),
            'singleEvents': 'true',
            'orderBy': 'startTime',
            'maxResults': 100,
            'q': query  # Google Calendar API supports text search
        }
        
        result = await self.make_api_call('GET', f'calendars/{calendar_id}/events', params=params)
        
        if result['success']:
            events = result.get('data', {}).get('items', [])
            return events[:max_results]
        
        return []
    
    async def _find_event_for_update(self, params: Dict, user_id: int) -> Optional[Dict]:
        """Find an event for update/delete operations."""
        event_id = params.get('event_id')
        title = params.get('title', params.get('event_title', ''))
        calendar_id = params.get('calendar_id', 'primary')
        
        if event_id:
            # Get by ID
            result = await self.make_api_call('GET', f'calendars/{calendar_id}/events/{event_id}')
            if result['success']:
                return result['data']
        
        if title:
            # Search by title
            events = await self._search_events(title, calendar_id, 1)
            if events:
                return events[0]
        
        # Check if user has recent search results
        if user_id in self.search_results and self.search_results[user_id]:
            # Use first result from recent search
            return self.search_results[user_id][0]
        
        return None
    
    async def _check_for_conflicts(self, start_dt: datetime, end_dt: datetime, 
                                  calendar_id: str, exclude_event_id: str = None) -> List[Dict]:
        """Check for scheduling conflicts."""
        # Get events in the time range
        params = {
            'timeMin': start_dt.astimezone(pytz.UTC).isoformat(),
            'timeMax': end_dt.astimezone(pytz.UTC).isoformat(),
            'singleEvents': 'true'
        }
        
        result = await self.make_api_call('GET', f'calendars/{calendar_id}/events', params=params)
        
        if not result['success']:
            return []
        
        conflicts = []
        events = result.get('data', {}).get('items', [])
        
        for event in events:
            # Skip if this is the event being updated
            if exclude_event_id and event['id'] == exclude_event_id:
                continue
            
            # Check if times overlap
            event_start = event.get('start', {})
            event_end = event.get('end', {})
            
            if 'dateTime' in event_start and 'dateTime' in event_end:
                evt_start = datetime.fromisoformat(event_start['dateTime'].replace('Z', '+00:00'))
                evt_end = datetime.fromisoformat(event_end['dateTime'].replace('Z', '+00:00'))
                
                # Check for overlap
                if evt_start < end_dt and evt_end > start_dt:
                    conflicts.append(event)
        
        return conflicts
    
    async def _prepare_update_data(self, event: Dict, params: Dict) -> Dict:
        """Prepare update data for an event."""
        update_data = event.copy()
        
        # Update title
        if params.get('new_title'):
            update_data['summary'] = params['new_title']
        
        # Update location
        if params.get('new_location'):
            update_data['location'] = params['new_location']
        
        # Update description
        if params.get('new_description'):
            update_data['description'] = params['new_description']
        
        # Update start/end times
        if params.get('new_start') or params.get('new_end'):
            if params.get('new_start'):
                start_dt = datetime.fromisoformat(params['new_start'])
            else:
                # Keep original start
                if 'dateTime' in event.get('start', {}):
                    start_dt = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                else:
                    start_dt = datetime.now(self.timezone)
            
            if params.get('new_end'):
                end_dt = datetime.fromisoformat(params['new_end'])
            else:
                # Keep original end or calculate from duration
                if 'dateTime' in event.get('end', {}):
                    end_dt = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                else:
                    end_dt = start_dt + timedelta(hours=1)
            
            update_data['start'] = {
                'dateTime': start_dt.isoformat(),
                'timeZone': str(self.timezone)
            }
            update_data['end'] = {
                'dateTime': end_dt.isoformat(),
                'timeZone': str(self.timezone)
            }
        
        # Update attendees if specified
        if params.get('new_attendees'):
            attendees = self._parse_attendees(params['new_attendees'])
            update_data['attendees'] = [{'email': email} for email in attendees]
        
        # Update reminders if specified
        if params.get('new_reminders'):
            update_data['reminders'] = params['new_reminders']
        
        return update_data
    
    def _calculate_free_slots(self, events: List[Dict], check_date: datetime,
                            start_hour: int, end_hour: int, min_duration: float) -> List[Dict]:
        """Calculate free time slots in a day."""
        # Set working hours
        day_start = check_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        day_end = check_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        if not day_start.tzinfo:
            day_start = self.timezone.localize(day_start)
            day_end = self.timezone.localize(day_end)
        
        # Extract busy times from events
        busy_times = []
        for event in events:
            start = event.get('start', {})
            end = event.get('end', {})
            
            if 'dateTime' in start and 'dateTime' in end:
                evt_start = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                evt_end = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                
                # Convert to local timezone
                evt_start = evt_start.astimezone(self.timezone)
                evt_end = evt_end.astimezone(self.timezone)
                
                busy_times.append((evt_start, evt_end))
        
        # Sort by start time
        busy_times.sort(key=lambda x: x[0])
        
        # Find gaps
        free_slots = []
        current_time = day_start
        
        for busy_start, busy_end in busy_times:
            # Check if there's a gap before this event
            if current_time < busy_start:
                gap_duration = (busy_start - current_time).total_seconds() / 3600
                if gap_duration >= min_duration:
                    free_slots.append({
                        'date': check_date,
                        'start': current_time,
                        'end': busy_start
                    })
            
            # Move current time to end of this event
            current_time = max(current_time, busy_end)
        
        # Check if there's time at the end of the day
        if current_time < day_end:
            gap_duration = (day_end - current_time).total_seconds() / 3600
            if gap_duration >= min_duration:
                free_slots.append({
                    'date': check_date,
                    'start': current_time,
                    'end': day_end
                })
        
        return free_slots
    
    def _calculate_event_duration(self, event: Dict) -> timedelta:
        """Calculate duration of an event."""
        start = event.get('start', {})
        end = event.get('end', {})
        
        if 'dateTime' in start and 'dateTime' in end:
            start_dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
            return end_dt - start_dt
        elif 'date' in start and 'date' in end:
            # All-day event
            start_date = datetime.strptime(start['date'], '%Y-%m-%d')
            end_date = datetime.strptime(end['date'], '%Y-%m-%d')
            return end_date - start_date
        
        return timedelta(hours=1)  # Default duration
    
    def _parse_attendees(self, attendees_str: str) -> List[str]:
        """Parse attendees from string input."""
        if not attendees_str:
            return []
        
        # Split by comma or semicolon
        attendees = re.split(r'[,;]', attendees_str)
        
        # Clean and validate emails
        valid_emails = []
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        for attendee in attendees:
            email = attendee.strip()
            if re.match(email_pattern, email):
                valid_emails.append(email)
        
        return valid_emails
    
    def _format_event_time(self, event: Dict) -> str:
        """Format event time for display."""
        start = event.get('start', {})
        end = event.get('end', {})
        
        if 'dateTime' in start:
            start_dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            start_local = start_dt.astimezone(self.timezone)
            
            if 'dateTime' in end:
                end_dt = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                end_local = end_dt.astimezone(self.timezone)
                
                # Same day event
                if start_local.date() == end_local.date():
                    return (f"{start_local.strftime('%b %d, %Y')} "
                           f"{start_local.strftime('%I:%M %p')} - {end_local.strftime('%I:%M %p')}")
                else:
                    # Multi-day event
                    return (f"{start_local.strftime('%b %d %I:%M %p')} - "
                           f"{end_local.strftime('%b %d %I:%M %p')}")
            
            return start_local.strftime('%b %d, %Y at %I:%M %p')
        
        elif 'date' in start:
            # All-day event
            start_date = datetime.strptime(start['date'], '%Y-%m-%d')
            if 'date' in end:
                end_date = datetime.strptime(end['date'], '%Y-%m-%d')
                days = (end_date - start_date).days
                if days == 1:
                    return f"{start_date.strftime('%b %d, %Y')} (All day)"
                else:
                    return f"{start_date.strftime('%b %d')} - {(end_date - timedelta(days=1)).strftime('%b %d, %Y')}"
            return f"{start_date.strftime('%b %d, %Y')} (All day)"
        
        return "Time not specified"
    
    def _format_event_summary(self, event: Dict) -> str:
        """Format brief event summary."""
        title = event.get('summary', 'Untitled')
        time = self._format_event_time(event)
        
        # Add icons for special properties
        icons = []
        if event.get('attendees'):
            icons.append(f"👥{len(event['attendees'])}")
        if event.get('location'):
            icons.append("📍")
        if event.get('recurrence'):
            icons.append("🔁")
        
        summary = f"{title} ({time})"
        if icons:
            summary += " " + " ".join(icons)
        
        return summary
    
    def _format_event_details(self, event: Dict) -> str:
        """Format detailed event information."""
        response = "📅 **Event Details:**\n\n"
        
        # Title
        response += f"**Title:** {event.get('summary', 'Untitled')}\n"
        
        # Time
        response += f"**Time:** {self._format_event_time(event)}\n"
        
        # Location
        if event.get('location'):
            response += f"**Location:** 📍 {event['location']}\n"
        
        # Description
        if event.get('description'):
            desc = event['description'][:500]
            if len(event['description']) > 500:
                desc += "..."
            response += f"**Description:** {desc}\n"
        
        # Attendees
        if event.get('attendees'):
            response += f"\n**Attendees ({len(event['attendees'])}):**\n"
            for attendee in event['attendees'][:10]:
                email = attendee.get('email', 'Unknown')
                status = attendee.get('responseStatus', 'needsAction')
                status_emoji = {
                    'accepted': '✅',
                    'declined': '❌',
                    'tentative': '❓',
                    'needsAction': '⏳'
                }.get(status, '')
                
                response += f"• {email} {status_emoji}\n"
            
            if len(event['attendees']) > 10:
                response += f"... and {len(event['attendees']) - 10} more\n"
        
        # Reminders
        reminders = event.get('reminders', {})
        if reminders.get('overrides'):
            response += f"\n**Reminders:**\n"
            for reminder in reminders['overrides']:
                response += f"• {reminder['minutes']} minutes before ({reminder['method']})\n"
        
        # Recurrence
        if event.get('recurrence'):
            response += f"\n**Recurring:** {event['recurrence'][0]}\n"
        
        # Event ID
        response += f"\n**Event ID:** `{event['id']}`"
        
        # Meeting link
        if event.get('hangoutLink'):
            response += f"\n**Meeting Link:** {event['hangoutLink']}"
        
        return response
    
    def _format_events_display(self, events: List[Dict], range_filter: str) -> str:
        """Format multiple events for display."""
        if not events:
            return f"📭 **No events {range_filter}**"
        
        # Normalize and format range display
        range_filter = range_filter.lower().replace('_', ' ')
        
        # Create appropriate title based on range
        title_map = {
            'yesterday': "Your schedule for yesterday",
            'today': "Your schedule for today",
            'tomorrow': "Your schedule for tomorrow",
            'week': "Your week's schedule",
            'this week': "Your week's schedule",
            'last week': "Your schedule from last week",
            'previous week': "Your schedule from last week",
            'next week': "Your schedule for next week",
            'month': "Your month's schedule",
            'this month': "Your month's schedule",
            'last month': "Your schedule from last month",
            'previous month': "Your schedule from last month",
            'next month': "Your schedule for next month"
        }
        
        title = title_map.get(range_filter, f"Your {range_filter} schedule")
        
        response = f"📅 **{title}:**\n\n"
        
        # Group events by date
        events_by_date = {}
        
        for event in events:
            start = event.get('start', {})
            
            if 'dateTime' in start:
                dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                dt_local = dt.astimezone(self.timezone)
                date_key = dt_local.strftime('%A, %B %d')
            elif 'date' in start:
                date_obj = datetime.strptime(start['date'], '%Y-%m-%d')
                date_key = date_obj.strftime('%A, %B %d')
            else:
                continue
            
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            
            events_by_date[date_key].append(event)
        
        # Format by date
        for date_str, date_events in events_by_date.items():
            response += f"**{date_str}**\n"
            
            # Sort events by time
            date_events.sort(key=lambda e: e.get('start', {}).get('dateTime', e.get('start', {}).get('date', '')))
            
            for event in date_events:
                # Get time
                start = event.get('start', {})
                if 'dateTime' in start:
                    dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    dt_local = dt.astimezone(self.timezone)
                    time_str = dt_local.strftime('%I:%M %p').lstrip('0')  # Remove leading zero
                else:
                    time_str = 'All day'
                
                # Format entry
                title = event.get('summary', 'Untitled')
                response += f"• {time_str}: {title}"
                
                # Add location if present
                if event.get('location'):
                    location = event['location']
                    # Truncate long locations
                    if len(location) > 30:
                        location = location[:27] + "..."
                    response += f" 📍{location}"
                
                # Add attendee count if present
                if event.get('attendees'):
                    attendee_count = len(event['attendees'])
                    response += f" 👥{attendee_count}"
                
                # Add recurrence indicator
                if event.get('recurrence'):
                    response += f" 🔁"
                
                response += "\n"
            
            response += "\n"
        
        # Add summary
        total = len(events)
        response += f"_Total: {total} event{'s' if total != 1 else ''}_"
        
        return response
    
    def _format_conflict_message(self, conflicts: List[Dict], start_dt: datetime, 
                                end_dt: datetime, new_title: str) -> str:
        """Format conflict warning message."""
        response = f"⚠️ **Scheduling Conflict Detected!**\n\n"
        response += f"**New Event:** {new_title}\n"
        response += f"**Time:** {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
        response += f"**Date:** {start_dt.strftime('%A, %B %d')}\n\n"
        
        response += f"**Conflicts with {len(conflicts)} event(s):**\n"
        for event in conflicts:
            response += f"• {event.get('summary', 'Untitled')}\n"
            response += f"  {self._format_event_time(event)}\n"
        
        response += "\n✅ Reply 'yes' to create anyway\n❌ Reply 'no' to cancel"
        
        return response
    
    def _format_conflict_list(self, conflicts: List[Dict]) -> str:
        """Format list of conflicting events."""
        response = ""
        for event in conflicts:
            response += f"• **{event.get('summary', 'Untitled')}**\n"
            response += f"  {self._format_event_time(event)}\n"
        return response
    
    def _format_event_created_message(self, event: Dict, start_dt: datetime, end_dt: datetime) -> str:
        """Format success message after event creation."""
        response = "✅ **Event created successfully!**\n\n"
        response += f"**Title:** {event.get('summary', 'Event')}\n"
        response += f"**Date:** {start_dt.strftime('%A, %B %d, %Y')}\n"
        response += f"**Time:** {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
        
        if event.get('location'):
            response += f"**Location:** 📍 {event['location']}\n"
        
        if event.get('attendees'):
            response += f"**Attendees:** 👥 {len(event['attendees'])} invited\n"
        
        if event.get('htmlLink'):
            response += f"\n[View in Google Calendar]({event['htmlLink']})"
        
        return response
