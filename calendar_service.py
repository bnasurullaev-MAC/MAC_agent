"""Google Calendar service implementation"""
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
    """Google Calendar service implementation"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.timezone = Config.DEFAULT_TIMEZONE
        self.date_parser = DateParser(self.timezone)
        self.pending_events = {}
        self.search_results = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle calendar-specific actions"""
        
        action_handlers = {
            'CREATE_EVENT': self.handle_create_event,
            'VIEW_EVENTS': self.handle_view_events,
            'UPDATE_EVENT': self.handle_update_event,
            'DELETE_EVENT': self.handle_delete_event,
            'SEARCH_EVENTS': self.handle_search_events
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'Unknown calendar action: {action}'}
    
    async def handle_create_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle event creation"""
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
            
            # Store for confirmation
            event_data = {
                'title': title,
                'start': start_dt,
                'end': end_dt,
                'description': params.get('description', ''),
                'location': params.get('location', ''),
                'attendees': params.get('attendees', '').split(',') if params.get('attendees') else []
            }
            
            # Ask for confirmation
            confirm_msg = f"""📅 **Confirm Event Creation:**

**Title:** {title}
**Date:** {start_dt.strftime('%A, %B %d, %Y')}
**Time:** {start_dt.strftime('%I:%M %p')}
**Duration:** {duration} hour{'s' if duration != 1 else ''}
{f"**Location:** {event_data['location']}" if event_data['location'] else ""}
{f"**Attendees:** {', '.join(event_data['attendees'])}" if event_data['attendees'] else ""}

Reply 'yes' to create or 'no' to cancel."""
            
            await state.update_data(
                service='calendar',
                action='create',
                params=event_data
            )
            await state.set_state(BotStates.confirming_action)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling create event: {e}")
            return {'success': False, 'message': f'Error creating event: {str(e)}'}
    
    async def handle_view_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle viewing events"""
        try:
            range_filter = params.get('range', 'today')
            events = await self.get_events(range_filter)
            
            if not events['success']:
                return {'success': False, 'message': 'Failed to fetch events'}
            
            if not events['data']:
                return {'success': True, 'message': f'No events found for {range_filter}'}
            
            # Format events for display
            response = f"📅 **Your {range_filter}'s events:**\n\n"
            
            for i, event in enumerate(events['data'][:20], 1):
                title = event.get('summary', 'Untitled')
                start = event.get('start', {})
                
                if 'dateTime' in start:
                    dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    dt_local = dt.astimezone(self.timezone)
                    time_str = dt_local.strftime('%b %d at %I:%M %p')
                elif 'date' in start:
                    time_str = start['date']
                else:
                    time_str = 'Time not specified'
                
                location = event.get('location', '')
                location_str = f" 📍{location}" if location else ""
                
                response += f"{i}. **{title}**\n   {time_str}{location_str}\n\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error viewing events: {e}")
            return {'success': False, 'message': f'Error viewing events: {str(e)}'}
    
    async def handle_update_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle event update"""
        try:
            # Search for the event first
            search_query = params.get('old_description', params.get('title', ''))
            events = await self.search_events_by_description(search_query)
            
            if not events:
                return {'success': False, 'message': 'No events found matching your description'}
            
            if len(events) == 1:
                # Direct update
                event = events[0]
                update_data = self._prepare_update_data(event, params)
                result = await self.update_event(event['id'], update_data)
                return result
            else:
                # Multiple matches - ask for selection
                response = "🔍 **Multiple events found. Select which to update:**\n\n"
                
                for i, event in enumerate(events[:5], 1):
                    title = event.get('summary', 'Untitled')
                    start = self._format_event_time(event)
                    response += f"{i}. {title} - {start}\n"
                
                # Store search results
                user_id = message.from_user.id
                self.search_results[user_id] = events[:5]
                
                await state.update_data(
                    service='calendar',
                    action='update',
                    params=params
                )
                await state.set_state(BotStates.selecting_event)
                
                await message.answer(response + "\nReply with the number to update.", parse_mode='Markdown')
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error handling update: {e}")
            return {'success': False, 'message': f'Error updating event: {str(e)}'}
    
    async def handle_delete_event(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle event deletion"""
        try:
            description = params.get('description', '')
            events = await self.search_events_by_description(description)
            
            if not events:
                return {'success': False, 'message': 'No events found matching your description'}
            
            if len(events) == 1:
                # Direct delete
                event = events[0]
                result = await self.delete_event(event['id'])
                if result['success']:
                    return {'success': True, 'message': f"✅ Deleted: {event.get('summary', 'Event')}"}
                else:
                    return result
            else:
                # Multiple matches
                response = "🔍 **Multiple events found. Select which to delete:**\n\n"
                
                for i, event in enumerate(events[:5], 1):
                    title = event.get('summary', 'Untitled')
                    start = self._format_event_time(event)
                    response += f"{i}. {title} - {start}\n"
                
                user_id = message.from_user.id
                self.search_results[user_id] = events[:5]
                
                await state.update_data(
                    service='calendar',
                    action='delete'
                )
                await state.set_state(BotStates.selecting_event)
                
                await message.answer(response + "\nReply with the number to delete.", parse_mode='Markdown')
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error handling delete: {e}")
            return {'success': False, 'message': f'Error deleting event: {str(e)}'}
    
    async def handle_search_events(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle event search"""
        query = params.get('query', '')
        events = await self.search_events_by_description(query)
        
        if not events:
            return {'success': True, 'message': f'No events found matching "{query}"'}
        
        response = f"🔍 **Search results for '{query}':**\n\n"
        for i, event in enumerate(events[:10], 1):
            title = event.get('summary', 'Untitled')
            start = self._format_event_time(event)
            response += f"{i}. **{title}**\n   {start}\n\n"
        
        return {'success': True, 'message': response}
    
    async def get_events(self, range_filter: str) -> Dict:
        """Get calendar events for a specific range"""
        now = datetime.now(self.timezone)
        
        # Determine time range
        if range_filter == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'tomorrow':
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif range_filter == 'week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif range_filter == 'month':
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
        
        return await self.make_api_call('GET', 'calendars/primary/events', params=params)
    
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
            'location': event_data.get('location', '')
        }
        
        if event_data.get('attendees'):
            event['attendees'] = [{'email': email.strip()} for email in event_data['attendees']]
        
        return await self.make_api_call('POST', 'calendars/primary/events', json_data=event)
    
    async def update_event(self, event_id: str, update_data: Dict) -> Dict:
        """Update a calendar event"""
        return await self.make_api_call('PUT', f'calendars/primary/events/{event_id}', json_data=update_data)
    
    async def delete_event(self, event_id: str) -> Dict:
        """Delete a calendar event"""
        return await self.make_api_call('DELETE', f'calendars/primary/events/{event_id}')
    
    async def search_events_by_description(self, description: str) -> List[Dict]:
        """Search for events by description"""
        # Get events from the next month
        events_result = await self.get_events('month')
        
        if not events_result['success'] or not events_result.get('data'):
            return []
        
        events = events_result['data'].get('items', [])
        matching_events = []
        
        description_lower = description.lower()
        
        for event in events:
            score = 0
            title = event.get('summary', '').lower()
            
            # Check title match
            if description_lower in title or title in description_lower:
                score += 5
            
            # Check word matches
            desc_words = description_lower.split()
            title_words = title.split()
            for word in desc_words:
                if word in title_words:
                    score += 2
            
            if score > 0:
                matching_events.append((event, score))
        
        # Sort by score
        matching_events.sort(key=lambda x: x[1], reverse=True)
        return [event for event, score in matching_events[:10]]
    
    def _format_event_time(self, event: Dict) -> str:
        """Format event time for display"""
        start = event.get('start', {})
        
        if 'dateTime' in start:
            dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            dt_local = dt.astimezone(self.timezone)
            return dt_local.strftime('%b %d at %I:%M %p')
        elif 'date' in start:
            return start['date']
        
        return 'Time not specified'
    
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
                # Keep original date
                start = event.get('start', {})
                if 'dateTime' in start:
                    dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    new_date = dt.astimezone(self.timezone)
                else:
                    new_date = datetime.now(self.timezone)
            
            if params.get('new_time'):
                hour, minute = self.date_parser.parse_time(params['new_time'])
            else:
                # Keep original time
                hour = new_date.hour
                minute = new_date.minute
            
            new_start = new_date.replace(hour=hour, minute=minute)
            
            # Calculate duration
            if params.get('new_duration'):
                duration = self.date_parser.parse_duration(params['new_duration'])
            else:
                # Keep original duration
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