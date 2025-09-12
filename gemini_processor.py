"""
Enhanced Gemini AI processor with comprehensive calendar integration
=====================================================================
Fully integrated with all CalendarService capabilities including advanced
scheduling, conflict detection, and intelligent command parsing.
"""

import logging
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
import google.generativeai as genai
from config import Config

logger = logging.getLogger(__name__)


class GeminiProcessor:
    """Advanced Gemini processor with immediate calendar action execution"""
    
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            try:
                # Try different model versions
                model_names = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
                for model_name in model_names:
                    try:
                        self.model = genai.GenerativeModel(model_name)
                        logger.info(f"{model_name} initialized successfully")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to initialize {model_name}: {e}")
                        continue
                else:
                    logger.error("Failed to initialize any Gemini model")
                    self.model = None
            except Exception as e:
                logger.error(f"Critical error initializing Gemini: {e}")
                self.model = None
        else:
            self.model = None
            logger.warning("Gemini API key not configured")
        
        self.timezone = Config.DEFAULT_TIMEZONE
    
    async def process(self, user_message: str, user_id: int, context: str, available_services: Dict) -> Dict:
        """Process user message with immediate calendar action execution"""
        
        if not self.model:
            return {
                'text': "❌ Gemini AI is not configured. Please set up the API key.",
                'actions': []
            }
        
        try:
            # PRIORITY 1: Check for calendar-related keywords first
            if 'calendar' in available_services:
                calendar_action = self._check_calendar_intent(user_message)
                if calendar_action:
                    logger.info(f"Calendar intent detected: {calendar_action}")
                    return calendar_action
            
            # PRIORITY 2: Try quick pattern matching
            quick_action = self._quick_pattern_match(user_message, available_services)
            if quick_action:
                logger.info(f"Quick pattern matched: {quick_action}")
                return quick_action
            
            # PRIORITY 3: Use Gemini only if no patterns matched
            prompt = self._build_enhanced_prompt(user_message, context, available_services)
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse response for actions
            clean_text, actions = self._parse_and_validate_response(response_text, available_services)
            
            # Post-process actions
            actions = self._enhance_actions(actions, user_message)
            
            return {
                'text': clean_text,
                'actions': actions
            }
            
        except Exception as e:
            logger.error(f"Gemini processing error: {e}", exc_info=True)
            return self._fallback_processing(user_message, available_services)
    
    def _check_calendar_intent(self, message: str) -> Optional[Dict]:
        """Check for calendar-related intents and return immediate action"""
        message_lower = message.lower()
        
        # Direct calendar viewing requests - HIGHEST PRIORITY
        calendar_view_patterns = [
            r"what(?:'s| is)(?: on)?(?: my)? (?:for |on )?(?:calendar|schedule|agenda)?\s*(?:for |on )?\s*today",
            r"what(?:'s| is) (?:on )?(?:my )?calendar",
            r"what(?:'s| is) (?:on )?today",
            r"what(?:'s| is) for today",
            r"(?:show|display|list|view|check)(?: me)?(?: my)? (?:calendar|schedule|events?|agenda)",
            r"(?:my )?(?:calendar|schedule|events?|agenda)(?: for)?(?: today)?",
            r"what do i have (?:today|scheduled)",
            r"today(?:'s)? (?:calendar|schedule|events?|agenda)",
            r"(?:calendar|schedule) today",
        ]
        
        for pattern in calendar_view_patterns:
            if re.search(pattern, message_lower):
                # Determine the range
                if 'yesterday' in message_lower:
                    range_val = 'yesterday'
                elif 'tomorrow' in message_lower:
                    range_val = 'tomorrow'
                elif 'week' in message_lower or 'weekly' in message_lower:
                    range_val = 'week'
                elif 'month' in message_lower or 'monthly' in message_lower:
                    range_val = 'month'
                else:
                    range_val = 'today'  # Default to today
                
                return {
                    'text': "",  # No text response needed - let the action provide the response
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': range_val}}]
                }
        
        # Check for other calendar keywords
        calendar_keywords = ['schedule', 'meeting', 'appointment', 'event', 'calendar']
        if any(keyword in message_lower for keyword in calendar_keywords):
            # Check for creation intent
            if any(word in message_lower for word in ['create', 'add', 'schedule', 'book', 'set up']):
                event_info = self._extract_event_info(message_lower)
                return {
                    'text': "I'll help you schedule that.",
                    'actions': [{'service': 'calendar', 'action': 'CREATE_EVENT', 'params': event_info}]
                }
            
            # Check for deletion intent
            if any(word in message_lower for word in ['cancel', 'delete', 'remove']):
                params = self._extract_event_reference(message_lower)
                return {
                    'text': "I'll cancel that for you.",
                    'actions': [{'service': 'calendar', 'action': 'DELETE_EVENT', 'params': params}]
                }
        
        return None
    
    def _quick_pattern_match(self, message: str, services: Dict) -> Optional[Dict]:
        """Enhanced quick pattern matching for all services"""
        message_lower = message.lower()
        
        # Calendar patterns - comprehensive matching
        if 'calendar' in services:
            # Simple question patterns that should show today's calendar
            simple_patterns = [
                r"^\?+$",  # Just question marks
                r"^what(?:'s| is) (?:on )?(?:my )?calendar\??$",
                r"^calendar\??$",
                r"^schedule\??$",
                r"^today\??$",
                r"^what(?:'s| is) today\??$",
                r"^what(?:'s| is) for today\??$",
            ]
            
            for pattern in simple_patterns:
                if re.match(pattern, message_lower.strip()):
                    return {
                        'text': "",
                        'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'today'}}]
                    }
            
            # Yesterday's events
            if 'yesterday' in message_lower:
                return {
                    'text': "",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'yesterday'}}]
                }
            
            # Tomorrow's events
            if 'tomorrow' in message_lower:
                return {
                    'text': "",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'tomorrow'}}]
                }
            
            # Weekly events
            if any(phrase in message_lower for phrase in ['this week', 'weekly', 'week schedule']):
                return {
                    'text': "",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'week'}}]
                }
            
            # Monthly events
            if any(phrase in message_lower for phrase in ['this month', 'monthly', 'month schedule']):
                return {
                    'text': "",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'month'}}]
                }
            
            # Create event patterns
            if re.search(r'(schedule|create|add|book|set up).*(meeting|event|appointment|call)', message_lower):
                event_info = self._extract_event_info(message_lower)
                return {
                    'text': "I'll help you schedule that event.",
                    'actions': [{'service': 'calendar', 'action': 'CREATE_EVENT', 'params': event_info}]
                }
            
            # Find free time
            if re.search(r'(find|when|available|free).*(time|slot|availability)', message_lower):
                duration = self._extract_duration(message_lower)
                return {
                    'text': f"I'll find available {duration}h slots for you.",
                    'actions': [{'service': 'calendar', 'action': 'FIND_FREE_TIME', 
                               'params': {'duration': str(duration)}}]
                }
        
        # Gmail patterns
        if 'gmail' in services:
            if re.search(r'(show|list|check|get|view).*(unread|new).*(email|mail)', message_lower):
                return {
                    'text': "Let me check your unread emails.",
                    'actions': [{'service': 'gmail', 'action': 'LIST_UNREAD', 'params': {'max_results': '10'}}]
                }
            
            if re.search(r'delete.*(email|mail).*from\s+(\S+)', message_lower):
                match = re.search(r'from\s+([^\s]+)', message_lower)
                if match:
                    return {
                        'text': f"I'll find and help you delete emails from {match.group(1)}.",
                        'actions': [{'service': 'gmail', 'action': 'DELETE_EMAIL', 
                                   'params': {'description': f'from:{match.group(1)}'}}]
                    }
        
        # Tasks patterns
        if 'tasks' in services:
            if re.search(r'(add|create|new).*(task|todo|reminder)', message_lower):
                title = self._extract_task_title(message_lower)
                return {
                    'text': "I'll add that task for you.",
                    'actions': [{'service': 'tasks', 'action': 'ADD_TASK', 'params': {'title': title}}]
                }
        
        return None
    
    def _build_enhanced_prompt(self, user_message: str, context: str, services: Dict) -> str:
        """Build comprehensive prompt with full calendar capabilities"""
        current_date = datetime.now(self.timezone).strftime('%A, %B %d, %Y')
        current_time = datetime.now(self.timezone).strftime('%I:%M %p %Z')
        
        service_list = ', '.join(services.keys()) if services else 'No services'
        
        prompt = f"""You are an advanced Google Services Assistant with REAL API access.
Today is {current_date} at {current_time}.

Available services with FULL access: {service_list}

CRITICAL RULES:
1. ALWAYS generate a SERVICE_ACTION when user asks about calendar/schedule/events
2. For questions like "what is for today", "what's on my calendar", "?" - IMMEDIATELY generate VIEW_EVENTS action
3. NEVER just acknowledge without action - ALWAYS execute immediately
4. Do NOT wait for confirmation - execute immediately
5. Your response should be brief - let the action provide the details

{context}

User says: "{user_message}"

ACTION FORMAT (use EXACT format):
[SERVICE_ACTION: SERVICE_NAME | action: ACTION_TYPE | param1: "value1" | param2: "value2"]

CALENDAR SERVICE ACTIONS:

Viewing Events (USE IMMEDIATELY for any calendar query):
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today"]
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "tomorrow"]
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "week"]
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "month"]

Creating Events:
[SERVICE_ACTION: CALENDAR | action: CREATE_EVENT | title: "Meeting" | date: "tomorrow" | time: "2pm" | duration: "1 hour"]

Other Calendar Actions:
[SERVICE_ACTION: CALENDAR | action: DELETE_EVENT | title: "meeting name"]
[SERVICE_ACTION: CALENDAR | action: UPDATE_EVENT | title: "meeting" | new_time: "3pm"]
[SERVICE_ACTION: CALENDAR | action: FIND_FREE_TIME | duration: "2"]

CRITICAL EXAMPLES:

User: "what is for today"
Response: 
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today"]

User: "?"
Response:
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today"]

User: "what's on my calendar"
Response:
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today"]

User: "schedule meeting tomorrow 2pm"
Response: I'll schedule that meeting for you.
[SERVICE_ACTION: CALENDAR | action: CREATE_EVENT | title: "Meeting" | date: "tomorrow" | time: "2pm" | duration: "1 hour"]

Respond with the appropriate action:"""
        
        return prompt
    
    def _parse_and_validate_response(self, response: str, available_services: Dict) -> Tuple[str, List[Dict]]:
        """Parse and validate response for actions"""
        # Find all action tags
        action_pattern = r'\[SERVICE_ACTION:\s*([A-Z]+)\s*\|([^\]]+)\]'
        matches = re.findall(action_pattern, response)
        
        # Remove action tags from response text
        clean_text = re.sub(action_pattern, '', response).strip()
        
        # Clean up extra whitespace
        clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
        clean_text = clean_text.strip()
        
        # Parse and validate actions
        actions = []
        for service_name, params_str in matches:
            service_lower = service_name.lower()
            
            # Validate service exists
            if service_lower not in available_services:
                logger.warning(f"Service {service_name} not available")
                continue
            
            # Parse parameters
            params = {}
            parts = params_str.split('|')
            
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Validate and clean parameters
                    if key and value:
                        params[key] = value
            
            # Validate action exists
            action_name = params.get('action', '')
            if action_name:
                actions.append({
                    'service': service_lower,
                    'action': action_name,
                    'params': params
                })
            else:
                logger.warning(f"No action specified for service {service_name}")
        
        return clean_text, actions
    
    def _enhance_actions(self, actions: List[Dict], user_message: str) -> List[Dict]:
        """Enhance actions with additional context from user message"""
        message_lower = user_message.lower()
        
        for action in actions:
            # Enhance Calendar actions
            if action['service'] == 'calendar':
                # Add smart defaults for event creation
                if action['action'] in ['CREATE_EVENT', 'CREATE_RECURRING', 'BLOCK_TIME']:
                    if not action['params'].get('duration'):
                        # Smart duration defaults
                        if any(word in message_lower for word in ['standup', 'daily', 'sync']):
                            action['params']['duration'] = '30 minutes'
                        elif 'lunch' in message_lower:
                            action['params']['duration'] = '1 hour'
                        elif 'interview' in message_lower:
                            action['params']['duration'] = '1 hour'
                        elif 'call' in message_lower:
                            action['params']['duration'] = '30 minutes'
                        else:
                            action['params']['duration'] = '1 hour'
                    
                    # Smart title defaults
                    if not action['params'].get('title'):
                        if 'meeting' in message_lower:
                            action['params']['title'] = 'Meeting'
                        elif 'appointment' in message_lower:
                            action['params']['title'] = 'Appointment'
                        elif 'call' in message_lower:
                            action['params']['title'] = 'Call'
                        elif 'interview' in message_lower:
                            action['params']['title'] = 'Interview'
        
        return actions
    
    # ========================================================================
    # EXTRACTION HELPER METHODS
    # ========================================================================
    
    def _extract_event_info(self, message: str) -> Dict:
        """Extract event information from message"""
        params = {}
        
        # Extract title
        title_patterns = [
            r'(?:meeting|event|appointment|call) (?:with|about|for) ([^,\.\n]+)',
            r'(?:schedule|create|book) (?:a |an )?([^,\.\n]+?)(?:\s+(?:on|at|for))',
            r'"([^"]+)"',
            r'\'([^\']+)\''
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['title'] = match.group(1).strip()
                break
        
        # Extract date
        date_patterns = [
            r'(?:on |for )?(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(?:on |for )?next (week|month|monday|tuesday|wednesday|thursday|friday)',
            r'(?:on |for )?(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)',
            r'(?:on |for )?(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['date'] = match.group(1) if match.group(1) else match.group(0)
                break
        
        # Extract time
        time_patterns = [
            r'at (\d{1,2}(?::\d{2})?\s*(?:am|pm))',
            r'at (\d{1,2}(?::\d{2})?)',
            r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))',
            r'(morning|afternoon|evening|noon|midnight)'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['time'] = match.group(1)
                break
        
        # Extract duration
        duration = self._extract_duration(message)
        if duration:
            params['duration'] = f"{duration} {'hour' if duration == 1 else 'hours'}"
        
        return params
    
    def _extract_event_reference(self, message: str) -> Dict:
        """Extract reference to an existing event"""
        params = {}
        
        # Look for event title or description
        patterns = [
            r'(?:the |my )?"([^"]+)"',
            r'(?:the |my )?\'([^\']+)\'',
            r'(?:the |my )?([\w\s]+ (?:meeting|appointment|event|call))',
            r'with ([\w\s]+)',
            r'about ([\w\s]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['title'] = match.group(1).strip()
                break
        
        return params
    
    def _extract_duration(self, message: str) -> float:
        """Extract duration in hours"""
        patterns = [
            (r'(\d+\.?\d*)\s*hours?', 1),
            (r'(\d+\.?\d*)\s*hrs?', 1),
            (r'(\d+)\s*minutes?', 1/60),
            (r'(\d+)\s*mins?', 1/60),
            (r'half\s*(?:an\s*)?hour', 0.5),
            (r'(\d+)\s*days?', 24),
            (r'all\s*day', 24)
        ]
        
        for pattern, multiplier in patterns:
            if isinstance(multiplier, (int, float)):
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    if pattern in [r'half\s*(?:an\s*)?hour', r'all\s*day']:
                        return multiplier
                    value = float(match.group(1))
                    return value * multiplier
        
        return 1.0  # Default 1 hour
    
    def _extract_task_title(self, message: str) -> str:
        """Extract task title from message"""
        # Remove command words
        clean = re.sub(r'(add|create|new|task|todo|reminder)', '', message, flags=re.IGNORECASE)
        return clean.strip()[:100]  # Limit length
    
    def _fallback_processing(self, user_message: str, available_services: Dict) -> Dict:
        """Fallback processing when Gemini fails"""
        message_lower = user_message.lower()
        
        # Most common case - user wants to see calendar
        if any(word in message_lower for word in ['calendar', 'schedule', 'today', 'events', 'what']):
            return {
                'text': "",
                'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'today'}}]
            }
        
        # Try to understand intent from keywords
        intents = self._detect_intents(message_lower)
        
        if not intents:
            return {
                'text': "I understand you need help, but I'm not sure what you're asking for. Could you please be more specific? For example:\n"
                        "• 'Show my calendar'\n"
                        "• 'Schedule a meeting tomorrow at 2pm'\n"
                        "• 'Check my emails'",
                'actions': []
            }
        
        # Build response based on detected intents
        primary_intent = intents[0]
        
        if primary_intent['service'] == 'calendar':
            if primary_intent['action'] == 'view':
                return {
                    'text': "",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'today'}}]
                }
        
        return {
            'text': f"I think you want to {primary_intent['action']} something in {primary_intent['service']}. "
                   f"Let me help you with that.",
            'actions': []
        }
    
    def _detect_intents(self, message: str) -> List[Dict]:
        """Detect intents from message"""
        intents = []
        
        # Calendar intents
        calendar_keywords = ['calendar', 'schedule', 'event', 'meeting', 'appointment', 'today', 'tomorrow']
        if any(word in message for word in calendar_keywords):
            if any(word in message for word in ['show', 'view', 'check', 'what', 'list', '?']):
                intents.append({'service': 'calendar', 'action': 'view'})
            elif any(word in message for word in ['create', 'add', 'schedule', 'book', 'set']):
                intents.append({'service': 'calendar', 'action': 'create'})
            elif any(word in message for word in ['delete', 'cancel', 'remove']):
                intents.append({'service': 'calendar', 'action': 'delete'})
        
        # Gmail intents
        if any(word in message for word in ['email', 'mail', 'inbox', 'gmail']):
            if any(word in message for word in ['read', 'show', 'check', 'view', 'list']):
                intents.append({'service': 'gmail', 'action': 'list'})
        
        return intents
