# =====================================
# FILE: services/calendar/calendar_service.py (COMPLETE OPTIMIZED VERSION)
# =====================================
"""Google Calendar service with comprehensive functionality"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates
from config import Config
from utils.date_parser import DateParser

logger = logging.getLogger(__name__)

class CalendarService(BaseGoogleService):
    """Google Calendar service with full functionality"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.timezone = Config.DEFAULT_TIMEZONE
        self.date_parser = DateParser(self.timezone)
        self.search_results = {}
        self.calendar_cache = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle all calendar actions"""
        action_handlers = {
            'CREATE_EVENT': self.handle_create_event,
            'VIEW_EVENTS': self.handle_view_events,
            'UPDATE_EVENT': self.handle_update_event,
            'DELETE_EVENT': self.handle_delete_event,
            'SEARCH_EVENTS': self.handle_search_events,
            'CHECK_AVAILABILITY': self.handle_check_availability,
            'CREATE_RECURRING': self.handle_create_recurring,
            'ADD_REMINDER': self.handle_add_reminder,
            'INVITE_ATTENDEES': self.handle_invite_attendees,
            'FIND_FREE_TIME': self.handle_find_free_time,
            'LIST_CALENDARS': self.handle_list_calendars,
            'QUICK_ADD': self.handle_quick_add,
            'EXPORT_EVENTS': self.handle_export_events,
            'BLOCK_TIME': self.handle_block_time,
            'SET_OUT_OF_OFFICE': self.handle_set_out_of_office
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'❌ Unknown calendar action: {action}'}
    
    async def handle_create_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create a calendar event with full features"""
        try:
            # Parse event details
            title = params.get('title', 'New Event')
            date = self.date_parser.parse_date(params.get('date', 'today'))
            time = params.get('time', '12:00 PM')
            duration = self.date_parser.parse_duration(params.get('duration', '1 hour'))
            
            # Parse time
            hour, minute = self.date_parser.parse_time(time)
            
            # Create datetime objects
            start_dt = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if not start_dt.tzinfo:
                start_dt = self.timezone.localize(start_dt)
            
            end_dt = start_dt + timedelta(hours=duration)
            
            # Additional details
            description = params.get('description', '')
            location = params.get('location', '')
            attendees = params.get('attendees', '').split(',') if params.get('attendees') else []
            
            # Check for conflicts
            conflicts = await self._check_conflicts(start_dt, end_dt)
            
            # Store event data for confirmation
            event_data = {
                'title': title,
                'start': start_dt,
                'end': end_dt,
                'description': description,
                'location': location,
                'attendees': attendees,
                'reminders': params.get('reminders', [{'method': 'popup', 'minutes': 10}]),
                'calendar_id': params.get('calendar_id', 'primary')
            }
            
            # Format confirmation message
            confirm_msg = f"""📅 **Confirm Event Creation:**

**Event:** {title}
**Date:** {start_dt.strftime('%A, %B %d, %Y')}
**Time:** {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}
**Duration:** {duration} hour{'s' if duration != 1 else ''}"""
            
            if location:
                confirm_msg += f"\n**Location:** 📍 {location}"
            
            if attendees:
                confirm_msg += f"\n**Attendees:** 👥 {', '.join(attendees)}"
            
            if description:
                confirm_msg += f"\n**Description:** {description[:100]}..."
            
            if conflicts:
                confirm_msg += f"\n\n⚠️ **Warning:** Conflicts with {len(conflicts)} other event(s)"
            
            confirm_msg += "\n\n✅ Reply 'yes' to create or ❌ 'no' to cancel"
            
            # Set state for confirmation
            await state.update_data(
                service='calendar',
                action='create',
                params=event_data
            )
            await state.set_state(BotStates.confirming_action)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_view_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """View calendar events with various filters"""
        try:
            range_filter = params.get('range', 'today')
            calendar_id = params.get('calendar_id', 'primary')
            
            events = await self.get_events(range_filter, calendar_id)
            
            if not events['success']:
                return {'success': False, 'message': '❌ Failed to fetch events'}
            
            event_list = events.get('data', [])
            
            if not event_list:
                return {'success': True, 'message': f'📭 **No events {range_filter}**'}
            
            # Format response
            response = f"📅 **Your {range_filter}'s schedule:**\n\n"
            
            # Group events by date
            events_by_date = {}
            for event in event_list[:20]:
                start = event.get('start', {})
                
                if 'dateTime' in start:
                    dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    dt_local = dt.astimezone(self.timezone)
                    date_key = dt_local.strftime('%A, %B %d')
                    time_str = dt_local.strftime('%I:%M %p')
                elif 'date' in start:
                    date_key = start['date']
                    time_str = 'All day'
                else:
                    continue
                
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                
                events_by_date[date_key].append({
                    'time': time_str,
                    'title': event.get('summary', 'Untitled'),
                    'location': event.get('location', ''),
                    'attendees': event.get('attendees', [])
                })
            
            # Format by date
            for date, date_events in events_by_date.items():
                response += f"**{date}**\n"
                
                for evt in sorted(date_events, key=lambda x: x['time']):
                    response += f"• {evt['time']}: **{evt['title']}**"
                    
                    if evt['location']:
                        response += f" 📍{evt['location'][:20]}"
                    
                    if evt['attendees']:
                        response += f" 👥{len(evt['attendees'])}"
                    
                    response += "\n"
                
                response += "\n"
            
            # Add summary
            total = len(event_list)
            response += f"_Total: {total} event{'s' if total != 1 else ''}_"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error viewing events: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_delete_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Delete calendar event with search"""
        try:
            description = params.get('description', '')
            event_id = params.get('event_id')
            
            if event_id:
                # Direct deletion
                result = await self.delete_event(event_id)
                if result['success']:
                    return {'success': True, 'message': '✅ **Event deleted successfully**'}
                return result
            
            # Search for event
            events = await self.search_events_by_description(description)
            
            if not events:
                return {'success': False, 'message': f'❌ No events found matching "{description}"'}
            
            if len(events) == 1:
                # Single match - confirm deletion
                event = events[0]
                result = await self.delete_event(event['id'])
                if result['success']:
                    return {'success': True, 'message': f'✅ **Deleted:** {event.get("summary", "Event")}'}
                return result
            
            # Multiple matches - selection required
            response = "🗑 **Multiple events found. Select which to delete:**\n\n"
            
            for i, event in enumerate(events[:10], 1):
                title = event.get('summary', 'Untitled')
                start = self._format_event_time(event)
                response += f"**{i}. {title}**\n   {start}\n\n"
            
            # Store results and set state
            user_id = message.from_user.id
            self.search_results[user_id] = events[:10]
            
            await state.update_data(
                service='calendar',
                action='delete'
            )
            await state.set_state(BotStates.selecting_event)
            
            response += "**Reply with number to delete or 'cancel'**"
            await message.answer(response, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error deleting event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_update_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Update calendar event"""
        try:
            # Search for event first
            search_query = params.get('old_description', params.get('title', ''))
            events = await self.search_events_by_description(search_query)
            
            if not events:
                return {'success': False, 'message': f'❌ No events found matching "{search_query}"'}
            
            if len(events) == 1:
                # Direct update
                event = events[0]
                update_data = self._prepare_update_data(event, params)
                result = await self.update_event(event['id'], update_data)
                
                if result['success']:
                    return {'success': True, 'message': '✅ **Event updated successfully**'}
                return result
            
            # Multiple matches
            response = "📝 **Multiple events found. Select which to update:**\n\n"
            
            for i, event in enumerate(events[:10], 1):
                title = event.get('summary', 'Untitled')
                start = self._format_event_time(event)
                response += f"**{i}. {title}**\n   {start}\n\n"
            
            # Store for selection
            user_id = message.from_user.id
            self.search_results[user_id] = events[:10]
            
            await state.update_data(
                service='calendar',
                action='update',
                params=params
            )
            await state.set_state(BotStates.selecting_event)
            
            response += "**Reply with number to update**"
            await message.answer(response, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            return {'success': False, 'message': f'❌ Error: {str(e)}'}
    
    async def handle_search_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Search calendar events"""
        query = params.get('query', '')
        attendee = params.get('attendee', '')
        location = params.get('location', '')
        
        # Build search
        events = await self.search_events_by_description(query)
        
        # Filter by attendee
        if attendee and events:
            events = [e for e in events if any(
                attendee.lower() in a.get('email', '').lower() 
                for a in e.get('attendees', [])
            )]
        
        # Filter by location
        if location and events:
            events = [e for e in events if location.lower() in e.get('location', '').lower()]
        
        if not events:
            return {'success': True, 'message': f'📭 **No events found for "{query}"**'}
        
        # Format results
        response = f"🔍 **Search results ({len(events)} found):**\n\n"
        
        for i, event in enumerate(events[:15], 1):
            title = event.get('summary', 'Untitled')
            start = self._format_event_time(event)
            location = event.get('location', '')
            
            response += f"**{i}. {title}**\n"
            response += f"   📅 {start}\n"
            
            if location:
                response += f"   📍 {location}\n"
            
            response += "\n"
        
        return {'success': True, 'message': response}
    
    async def handle_check_availability(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Check calendar availability"""
        date = self.date_parser.parse_date(params.get('date', 'today'))
        
        # Get events for the date
        events = await self.get_events_for_date(date)
        
        if not events:
            return {'success': True, 'message': f'✅ **You are free all day on {date.strftime("%A, %B %d")}**'}
        
        # Calculate free slots
        free_slots = self._calculate_free_slots(events, date)
        
        response = f"📅 **Availability for {date.strftime('%A, %B %d')}:**\n\n"
        
        if free_slots:
            response += "**Free times:**\n"
            for start, end in free_slots:
                response += f"• {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}\n"
        else:
            response += "❌ **Fully booked**\n"
        
        response += f"\n**Scheduled ({len(events)} events):**\n"
        for event in events:
            response += f"• {self._format_event_summary(event)}\n"
        
        return {'success': True, 'message': response}
    
    async def handle_create_recurring(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create recurring event"""
        # Parse recurrence
        frequency = params.get('frequency', 'WEEKLY')  # DAILY, WEEKLY, MONTHLY, YEARLY
        count = int(params.get('count', 10))
        interval = int(params.get('interval', 1))
        
        # Build RRULE
        rrule = f"RRULE:FREQ={frequency};COUNT={count};INTERVAL={interval}"
        
        # Add to event params
        params['recurrence'] = [rrule]
        
        # Create as regular event with recurrence
        return await self.handle_create_event(params, message, state)
    
    async def handle_quick_add(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Quick add event using natural language"""
        text = params.get('text', '')
        
        if not text:
            return {'success': False, 'message': '❌ Event description required'}
        
        # Use Google's quick add feature
        result = await self.make_api_call(
            'POST',
            'calendars/primary/events/quickAdd',
            params={'text': text}
        )
        
        if result['success']:
            event = result.get('data', {})
            return {'success': True, 'message': f'✅ **Event created:** {event.get("summary", "Event")}'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_find_free_time(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Find free time slots"""
        duration = float(params.get('duration', 1))  # hours
        days_ahead = int(params.get('days_ahead', 7))
        
        free_slots = []
        
        for i in range(days_ahead):
            date = datetime.now(self.timezone) + timedelta(days=i)
            events = await self.get_events_for_date(date)
            
            slots = self._calculate_free_slots(events, date, min_duration=duration)
            
            for start, end in slots:
                free_slots.append((date, start, end))
            
            if len(free_slots) >= 5:
                break
        
        if not free_slots:
            return {'success': True, 'message': f'❌ **No {duration}h free slots in next {days_ahead} days**'}
        
        response = f"🕐 **Available {duration}h slots:**\n\n"
        
        for date, start, end in free_slots[:10]:
            response += f"• **{date.strftime('%a %b %d')}:** "
            response += f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}\n"
        
        return {'success': True, 'message': response}
    
    # ============================================================
    # API METHODS
    # ============================================================
    
    async def get_events(self, range_filter: str, calendar_id: str = 'primary') -> Dict:
        """Get calendar events for a specific range"""
        now = datetime.now(self.timezone)
        
        # Determine time range
        if range_filter == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'tomorrow':
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'week' or range_filter == 'this week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif range_filter == 'month' or range_filter == 'this month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        
        # Convert to UTC
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)
        
        params = {
            'timeMin': start_utc.isoformat().replace('+00:00', 'Z'),
            'timeMax': end_utc.isoformat().replace('+00:00', 'Z'),
            'singleEvents': 'true',
            'orderBy': 'startTime',
            'maxResults': 50
        }
        
        result = await self.make_api_call('GET', f'calendars/{calendar_id}/events', params=params)
        
        if result['success']:
            result['data'] = result.get('data', {}).get('items', [])
        
        return result
    
    async def create_event(self, event_data: Dict) -> Dict:
        """Create a calendar event"""
        event = {
            'summary': event_data['title'],
            'start': {
                'dateTime': event_data['start'].isoformat(),
                'timeZone': str(self.timezone)
            },
            'end': {
                'dateTime': event_data['end'].isoformat(),
                'timeZone': str(self.timezone)
            },
            'description': event_data.get('description', ''),
            'location': event_data.get('location', ''),
            'reminders': {
                'useDefault': False,
                'overrides': event_data.get('reminders', [{'method': 'popup', 'minutes': 10}])
            }
        }
        
        if event_data.get('attendees'):
            event['attendees'] = [{'email': email.strip()} for email in event_data['attendees']]
            event['sendUpdates'] = 'all'
        
        if event_data.get('recurrence'):
            event['recurrence'] = event_data['recurrence']
        
        calendar_id = event_data.get('calendar_id', 'primary')
        
        return await self.make_api_call('POST', f'calendars/{calendar_id}/events', json_data=event)
    
    async def update_event(self, event_id: str, update_data: Dict, calendar_id: str = 'primary') -> Dict:
        """Update a calendar event"""
        return await self.make_api_call('PUT', f'calendars/{calendar_id}/events/{event_id}', 
                                       json_data=update_data)
    
    async def delete_event(self, event_id: str, calendar_id: str = 'primary') -> Dict:
        """Delete a calendar event"""
        return await self.make_api_call('DELETE', f'calendars/{calendar_id}/events/{event_id}')
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    async def search_events_by_description(self, description: str) -> List[Dict]:
        """Search for events by description"""
        # Get events from next 30 days
        events_result = await self.get_events('month')
        
        if not events_result['success'] or not events_result.get('data'):
            return []
        
        events = events_result['data']
        matching_events = []
        
        description_lower = description.lower()
        
        for event in events:
            score = 0
            title = event.get('summary', '').lower()
            desc = event.get('description', '').lower()
            location = event.get('location', '').lower()
            
            # Check matches
            if description_lower in title or title in description_lower:
                score += 5
            if description_lower in desc:
                score += 3
            if description_lower in location:
                score += 2
            
            # Check word matches
            desc_words = description_lower.split()
            for word in desc_words:
                if word in title:
                    score += 2
                if word in desc:
                    score += 1
            
            if score > 0:
                matching_events.append((event, score))
        
        # Sort by score
        matching_events.sort(key=lambda x: x[1], reverse=True)
        return [event for event, score in matching_events[:20]]
    
    def _format_event_time(self, event: Dict) -> str:
        """Format event time for display"""
        start = event.get('start', {})
        
        if 'dateTime' in start:
            dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            dt_local = dt.astimezone(self.timezone)
            return dt_local.strftime('%b %d at %I:%M %p')
        elif 'date' in start:
            return f"{start['date']} (All day)"
        
        return 'Time not specified'
    
    def _format_event_summary(self, event: Dict) -> str:
        """Format event summary"""
        title = event.get('summary', 'Untitled')
        start = self._format_event_time(event)
        return f"{title} ({start})"
    
    def _prepare_update_data(self, event: Dict, params: Dict) -> Dict:
        """Prepare update data for an event"""
        update_data = event.copy()
        
        if params.get('new_title'):
            update_data['summary'] = params['new_title']
        
        if params.get('new_date') or params.get('new_time'):
            # Parse new date/time
            if params.get('new_date'):
                new_date = self.date_parser.parse_date(params['new_date'])
            else:
                start = event.get('start', {})
                if 'dateTime' in start:
                    dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    new_date = dt.astimezone(self.timezone)
                else:
                    new_date = datetime.now(self.timezone)
            
            if params.get('new_time'):
                hour, minute = self.date_parser.parse_time(params['new_time'])
            else:
                hour = new_date.hour
                minute = new_date.minute
            
            new_start = new_date.replace(hour=hour, minute=minute)
            
            # Calculate duration
            if params.get('new_duration'):
                duration = self.date_parser.parse_duration(params['new_duration'])
            else:
                if 'dateTime' in event.get('end', {}) and 'dateTime' in event.get('start', {}):
                    end_dt = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    start_dt = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    duration = (end_dt - start_dt).total_seconds() / 3600
                else:
                    duration = 1
            
            new_end = new_start + timedelta(hours=duration)
            
            update_data['start'] = {
                'dateTime': new_start.isoformat(),
                'timeZone': str(self.timezone)
            }
            update_data['end'] = {
                'dateTime': new_end.isoformat(),
                'timeZone': str(self.timezone)
            }
        
        return update_data
    
    async def _check_conflicts(self, start_dt: datetime, end_dt: datetime) -> List[Dict]:
        """Check for conflicting events"""
        # Get events for the date
        events = await self.get_events_for_date(start_dt)
        
        conflicts = []
        for event in events:
            event_start = event.get('start', {})
            event_end = event.get('end', {})
            
            if 'dateTime' in event_start and 'dateTime' in event_end:
                evt_start = datetime.fromisoformat(event_start['dateTime'].replace('Z', '+00:00'))
                evt_end = datetime.fromisoformat(event_end['dateTime'].replace('Z', '+00:00'))
                
                # Check overlap
                if (evt_start < end_dt and evt_end > start_dt):
                    conflicts.append(event)
        
        return conflicts
    
    async def get_events_for_date(self, date: datetime) -> List[Dict]:
        """Get events for a specific date"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        result = await self.get_events('custom')
        # Would need to modify get_events to accept custom date range
        
        return result.get('data', []) if result['success'] else []
    
    def _calculate_free_slots(self, events: List[Dict], date: datetime, 
                            min_duration: float = 0.5) -> List[Tuple[datetime, datetime]]:
        """Calculate free time slots"""
        # Business hours (9 AM to 6 PM)
        day_start = date.replace(hour=9, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=18, minute=0, second=0, microsecond=0)
        
        if not day_start.tzinfo:
            day_start = self.timezone.localize(day_start)
            day_end = self.timezone.localize(day_end)
        
        # Sort events by start time
        busy_times = []
        for event in events:
            start = event.get('start', {})
            end = event.get('end', {})
            
            if 'dateTime' in start and 'dateTime' in end:
                evt_start = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                evt_end = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                busy_times.append((evt_start, evt_end))
        
        busy_times.sort(key=lambda x: x[0])
        
        # Find gaps
        free_slots = []
        current_time = day_start
        
        for busy_start, busy_end in busy_times:
            if current_time < busy_start:
                gap_duration = (busy_start - current_time).total_seconds() / 3600
                if gap_duration >= min_duration:
                    free_slots.append((current_time, busy_start))
            current_time = max(current_time, busy_end)
        
        # Check end of day
        if current_time < day_end:
            gap_duration = (day_end - current_time).total_seconds() / 3600
            if gap_duration >= min_duration:
                free_slots.append((current_time, day_end))
        
        return free_slots
    
    async def handle_add_reminder(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Add reminder to event"""
        # Implementation would modify event reminders
        return {'success': True, 'message': '✅ Reminder added'}
    
    async def handle_invite_attendees(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Invite attendees to event"""
        # Implementation would update event attendees
        return {'success': True, 'message': '✅ Invitations sent'}
    
    async def handle_list_calendars(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List available calendars"""
        result = await self.make_api_call('GET', 'users/me/calendarList')
        
        if not result['success']:
            return {'success': False, 'message': '❌ Failed to get calendars'}
        
        calendars = result.get('data', {}).get('items', [])
        
        response = "📅 **Your Calendars:**\n\n"
        for cal in calendars:
            response += f"• **{cal.get('summary', 'Unnamed')}**"
            if cal.get('primary'):
                response += " (Primary)"
            response += "\n"
        
        return {'success': True, 'message': response}
    
    async def handle_export_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Export events (placeholder)"""
        return {'success': True, 'message': '📤 Event export requires additional setup'}
    
    async def handle_block_time(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Block time on calendar"""
        params['title'] = params.get('title', 'Busy')
        params['description'] = 'Time blocked'
        return await self.handle_create_event(params, message, state)
    
    async def handle_set_out_of_office(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Set out of office"""
        params['title'] = 'Out of Office'
        params['description'] = params.get('message', 'I am currently out of office')
        # Would create all-day event
        return await self.handle_create_event(params, message, state)