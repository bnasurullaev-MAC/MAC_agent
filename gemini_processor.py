# =====================================
# FILE: core/gemini_processor.py (FIXED WORKING VERSION)
# =====================================
"""Enhanced Gemini AI processor with superior intent recognition"""
import logging
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import google.generativeai as genai
from config import Config

logger = logging.getLogger(__name__)

class GeminiProcessor:
    """Advanced Gemini processor with comprehensive understanding"""
    
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Use the correct model name
            try:
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Gemini 2.5 Flash initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize gemini-2.5-flash, trying gemini-pro: {e}")
                try:
                    self.model = genai.GenerativeModel('gemini-pro')
                    logger.info("Gemini Pro initialized successfully")
                except Exception as e2:
                    logger.error(f"Failed to initialize any Gemini model: {e2}")
                    self.model = None
        else:
            self.model = None
            logger.warning("Gemini API key not configured")
        
        self.timezone = Config.DEFAULT_TIMEZONE
    
    async def process(self, 
                     user_message: str, 
                     user_id: int,
                     context: str,
                     available_services: Dict) -> Dict:
        """Process user message with enhanced understanding"""
        
        if not self.model:
            return {
                'text': "❌ Gemini AI is not configured. Please set up the API key.",
                'actions': []
            }
        
        try:
            # First, try to match direct patterns for faster response
            quick_action = self._quick_pattern_match(user_message, available_services)
            if quick_action:
                return quick_action
            
            # Build comprehensive prompt
            prompt = self._build_enhanced_prompt(user_message, context, available_services)
            
            # Generate response
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse response for actions with validation
            clean_text, actions = self._parse_and_validate_response(response_text, available_services)
            
            # Post-process actions for better accuracy
            actions = self._enhance_actions(actions, user_message)
            
            return {
                'text': clean_text,
                'actions': actions
            }
            
        except Exception as e:
            logger.error(f"Gemini processing error: {e}", exc_info=True)
            # Fallback to pattern matching
            return self._fallback_processing(user_message, available_services)
    
    def _quick_pattern_match(self, message: str, services: Dict) -> Optional[Dict]:
        """Quick pattern matching for common requests"""
        message_lower = message.lower()
        
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
            
            if re.search(r'send.*(email|mail).*to\s+([^\s]+)', message_lower):
                match = re.search(r'to\s+([^\s]+)', message_lower)
                if match:
                    return {
                        'text': "I'll help you compose and send that email.",
                        'actions': [{'service': 'gmail', 'action': 'SEND_EMAIL',
                                   'params': {'to': match.group(1)}}]
                    }
        
        # Calendar patterns
        if 'calendar' in services:
            if re.search(r'(schedule|create|add).*(meeting|event|appointment)', message_lower):
                return {
                    'text': "I'll help you schedule that event.",
                    'actions': [{'service': 'calendar', 'action': 'CREATE_EVENT', 'params': {}}]
                }
            
            if re.search(r'(what|show|list).*(calendar|schedule|event).*(today|tomorrow)', message_lower):
                range_val = 'today' if 'today' in message_lower else 'tomorrow'
                return {
                    'text': f"Let me show you your {range_val}'s schedule.",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 
                               'params': {'range': range_val}}]
                }
        
        return None
    
    def _build_enhanced_prompt(self, user_message: str, context: str, services: Dict) -> str:
        """Build enhanced prompt for Gemini"""
        current_date = datetime.now(self.timezone).strftime('%A, %B %d, %Y')
        current_time = datetime.now(self.timezone).strftime('%I:%M %p %Z')
        
        service_list = ', '.join(services.keys()) if services else 'No services'
        
        prompt = f"""You are an advanced Google Services Assistant with REAL API access.
Today is {current_date} at {current_time}.

Available services with FULL access: {service_list}

CRITICAL: You have ACTUAL access to:
✅ Read, send, delete, manage emails (Gmail)
✅ Create, update, delete calendar events (Calendar)
✅ Search, create, share files (Drive)
✅ Add, update, find contacts (Contacts)
✅ Create, complete, manage tasks (Tasks)

{context}

User says: "{user_message}"

RESPONSE RULES:
1. Be helpful, friendly, and conversational
2. USE the actual service actions - you have real access
3. For ambiguous requests, make intelligent assumptions
4. Handle typos and variations gracefully
5. Chain multiple actions if needed

ACTION FORMAT (use EXACT format):
[SERVICE_ACTION: SERVICE_NAME | action: ACTION_TYPE | param1: "value1" | param2: "value2"]

SERVICE ACTIONS:

Gmail:
[SERVICE_ACTION: GMAIL | action: LIST_UNREAD | max_results: "10"]
[SERVICE_ACTION: GMAIL | action: SEARCH_EMAILS | query: "search terms" | max_results: "10"]
[SERVICE_ACTION: GMAIL | action: DELETE_EMAIL | description: "from:sender or subject:topic"]
[SERVICE_ACTION: GMAIL | action: SEND_EMAIL | to: "email@example.com" | subject: "Subject" | body: "Message"]
[SERVICE_ACTION: GMAIL | action: READ_EMAIL | email_id: "id"]
[SERVICE_ACTION: GMAIL | action: REPLY_EMAIL | to: "email" | body: "reply text"]
[SERVICE_ACTION: GMAIL | action: MARK_READ | email_id: "id"]
[SERVICE_ACTION: GMAIL | action: ARCHIVE_EMAIL | email_id: "id"]
[SERVICE_ACTION: GMAIL | action: STAR_EMAIL | email_id: "id"]

Calendar:
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today/tomorrow/week/month"]
[SERVICE_ACTION: CALENDAR | action: CREATE_EVENT | title: "Event" | date: "tomorrow" | time: "2pm" | duration: "1 hour"]
[SERVICE_ACTION: CALENDAR | action: DELETE_EVENT | description: "event name"]
[SERVICE_ACTION: CALENDAR | action: UPDATE_EVENT | old_description: "current" | new_date: "date" | new_time: "time"]
[SERVICE_ACTION: CALENDAR | action: SEARCH_EVENTS | query: "search term"]
[SERVICE_ACTION: CALENDAR | action: CHECK_AVAILABILITY | date: "date"]

Drive:
[SERVICE_ACTION: DRIVE | action: SEARCH_FILES | query: "filename" | file_type: "document/spreadsheet/presentation"]
[SERVICE_ACTION: DRIVE | action: CREATE_FOLDER | name: "Folder Name"]
[SERVICE_ACTION: DRIVE | action: LIST_RECENT | max_results: "10"]
[SERVICE_ACTION: DRIVE | action: DELETE_FILE | name: "filename"]
[SERVICE_ACTION: DRIVE | action: SHARE_FILE | name: "filename" | email: "user@example.com" | role: "reader/writer"]
[SERVICE_ACTION: DRIVE | action: DOWNLOAD_FILE | file_id: "id"]

Contacts:
[SERVICE_ACTION: CONTACTS | action: FIND_CONTACT | name: "John Doe"]
[SERVICE_ACTION: CONTACTS | action: ADD_CONTACT | name: "Name" | email: "email" | phone: "phone"]
[SERVICE_ACTION: CONTACTS | action: UPDATE_CONTACT | name: "Name" | new_email: "email"]
[SERVICE_ACTION: CONTACTS | action: DELETE_CONTACT | name: "Name"]
[SERVICE_ACTION: CONTACTS | action: LIST_CONTACTS | max_results: "20"]

Tasks:
[SERVICE_ACTION: TASKS | action: ADD_TASK | title: "Task" | due_date: "tomorrow"]
[SERVICE_ACTION: TASKS | action: LIST_TASKS | show_completed: "false"]
[SERVICE_ACTION: TASKS | action: COMPLETE_TASK | title: "task name"]
[SERVICE_ACTION: TASKS | action: DELETE_TASK | title: "task name"]

SMART EXAMPLES:

User: "Delete all spam"
Response: I'll help you find and delete spam emails.
[SERVICE_ACTION: GMAIL | action: DELETE_EMAIL | description: "is:spam"]

User: "What's my day look like?"
Response: Let me show you today's schedule.
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today"]

User: "Email John about the meeting"
Response: I'll help you send an email to John about the meeting.
[SERVICE_ACTION: GMAIL | action: SEND_EMAIL | to: "john@example.com" | subject: "Meeting" | body: "Hi John,\n\nRegarding our meeting..."]

User: "Find the budget spreadsheet"
Response: I'll search for the budget spreadsheet in your Drive.
[SERVICE_ACTION: DRIVE | action: SEARCH_FILES | query: "budget" | file_type: "spreadsheet"]

User: "Remind me to call mom tomorrow"
Response: I'll add that task for tomorrow.
[SERVICE_ACTION: TASKS | action: ADD_TASK | title: "Call mom" | due_date: "tomorrow"]

INTELLIGENT INTERPRETATION:
- "check mail" → LIST_UNREAD emails
- "free tomorrow?" → CHECK_AVAILABILITY for tomorrow
- "John's number" → FIND_CONTACT John
- "clean inbox" → DELETE_EMAIL old or spam
- "busy today" → VIEW_EVENTS today

Respond naturally and execute the appropriate action(s):"""
        
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
            # Enhance Gmail actions
            if action['service'] == 'gmail':
                if action['action'] == 'DELETE_EMAIL':
                    # Add more specific query if available
                    if 'old' in message_lower:
                        action['params']['description'] = 'older_than:30d'
                    elif 'spam' in message_lower:
                        action['params']['description'] = 'is:spam'
                    elif 'promotional' in message_lower or 'promotion' in message_lower:
                        action['params']['description'] = 'category:promotions'
                    elif 'unread' in message_lower:
                        action['params']['description'] = 'is:unread'
                
                elif action['action'] == 'SEND_EMAIL':
                    # Extract subject from context if not provided
                    if not action['params'].get('subject'):
                        if 'meeting' in message_lower:
                            action['params']['subject'] = 'Meeting Follow-up'
                        elif 'report' in message_lower:
                            action['params']['subject'] = 'Report'
                        elif 'question' in message_lower:
                            action['params']['subject'] = 'Question'
            
            # Enhance Calendar actions
            elif action['service'] == 'calendar':
                if action['action'] == 'CREATE_EVENT':
                    # Add smart defaults
                    if not action['params'].get('duration'):
                        if 'meeting' in message_lower:
                            action['params']['duration'] = '1 hour'
                        elif 'call' in message_lower:
                            action['params']['duration'] = '30 minutes'
                        elif 'lunch' in message_lower:
                            action['params']['duration'] = '1 hour'
                    
                    if not action['params'].get('title'):
                        if 'meeting' in message_lower:
                            action['params']['title'] = 'Meeting'
                        elif 'appointment' in message_lower:
                            action['params']['title'] = 'Appointment'
                        elif 'call' in message_lower:
                            action['params']['title'] = 'Call'
            
            # Enhance Drive actions
            elif action['service'] == 'drive':
                if action['action'] == 'SEARCH_FILES':
                    # Detect file type from message
                    if not action['params'].get('file_type'):
                        if any(word in message_lower for word in ['doc', 'document', 'letter']):
                            action['params']['file_type'] = 'document'
                        elif any(word in message_lower for word in ['sheet', 'spreadsheet', 'excel', 'csv']):
                            action['params']['file_type'] = 'spreadsheet'
                        elif any(word in message_lower for word in ['presentation', 'slides', 'powerpoint']):
                            action['params']['file_type'] = 'presentation'
                        elif any(word in message_lower for word in ['pdf']):
                            action['params']['file_type'] = 'pdf'
        
        return actions
    
    def _fallback_processing(self, user_message: str, available_services: Dict) -> Dict:
        """Fallback processing when Gemini fails"""
        message_lower = user_message.lower()
        
        # Try to understand intent from keywords
        intents = self._detect_intents(message_lower)
        
        if not intents:
            return {
                'text': "I understand you need help, but I'm not sure what you're asking for. Could you please be more specific? For example:\n"
                        "• 'Show my unread emails'\n"
                        "• 'Schedule a meeting tomorrow'\n"
                        "• 'Search for budget file'",
                'actions': []
            }
        
        # Build response based on detected intents
        primary_intent = intents[0]
        
        if primary_intent['service'] == 'gmail':
            if primary_intent['action'] == 'list':
                return {
                    'text': "I'll check your emails for you.",
                    'actions': [{'service': 'gmail', 'action': 'LIST_UNREAD', 'params': {'max_results': '10'}}]
                }
            elif primary_intent['action'] == 'delete':
                return {
                    'text': "I'll help you delete emails. Let me search for them first.",
                    'actions': [{'service': 'gmail', 'action': 'DELETE_EMAIL', 'params': {'description': 'is:unread'}}]
                }
        
        elif primary_intent['service'] == 'calendar':
            if primary_intent['action'] == 'view':
                return {
                    'text': "Let me show you your calendar.",
                    'actions': [{'service': 'calendar', 'action': 'VIEW_EVENTS', 'params': {'range': 'today'}}]
                }
            elif primary_intent['action'] == 'create':
                return {
                    'text': "I'll help you create an event. Please provide more details.",
                    'actions': []
                }
        
        # Default response
        return {
            'text': f"I think you want to {primary_intent['action']} something in {primary_intent['service']}. "
                   f"Let me help you with that.",
            'actions': []
        }
    
    def _detect_intents(self, message: str) -> List[Dict]:
        """Detect intents from message"""
        intents = []
        
        # Gmail intents
        if any(word in message for word in ['email', 'mail', 'inbox', 'gmail', 'message']):
            if any(word in message for word in ['delete', 'remove', 'trash', 'clean']):
                intents.append({'service': 'gmail', 'action': 'delete'})
            elif any(word in message for word in ['send', 'write', 'compose', 'reply']):
                intents.append({'service': 'gmail', 'action': 'send'})
            elif any(word in message for word in ['read', 'show', 'check', 'view', 'list', 'see']):
                intents.append({'service': 'gmail', 'action': 'list'})
            elif any(word in message for word in ['search', 'find', 'look']):
                intents.append({'service': 'gmail', 'action': 'search'})
        
        # Calendar intents
        if any(word in message for word in ['calendar', 'schedule', 'event', 'meeting', 'appointment']):
            if any(word in message for word in ['create', 'add', 'schedule', 'book', 'set']):
                intents.append({'service': 'calendar', 'action': 'create'})
            elif any(word in message for word in ['delete', 'cancel', 'remove']):
                intents.append({'service': 'calendar', 'action': 'delete'})
            elif any(word in message for word in ['show', 'view', 'check', 'what', 'list']):
                intents.append({'service': 'calendar', 'action': 'view'})
            elif any(word in message for word in ['update', 'change', 'modify', 'reschedule']):
                intents.append({'service': 'calendar', 'action': 'update'})
        
        # Drive intents
        if any(word in message for word in ['file', 'document', 'folder', 'drive', 'sheet', 'spreadsheet']):
            if any(word in message for word in ['search', 'find', 'look', 'where']):
                intents.append({'service': 'drive', 'action': 'search'})
            elif any(word in message for word in ['create', 'make', 'new']):
                intents.append({'service': 'drive', 'action': 'create'})
            elif any(word in message for word in ['delete', 'remove', 'trash']):
                intents.append({'service': 'drive', 'action': 'delete'})
            elif any(word in message for word in ['share', 'send', 'collaborate']):
                intents.append({'service': 'drive', 'action': 'share'})
        
        # Contacts intents
        if any(word in message for word in ['contact', 'phone', 'number', 'address', 'person']):
            if any(word in message for word in ['find', 'search', 'look', 'get']):
                intents.append({'service': 'contacts', 'action': 'find'})
            elif any(word in message for word in ['add', 'create', 'new', 'save']):
                intents.append({'service': 'contacts', 'action': 'add'})
            elif any(word in message for word in ['delete', 'remove']):
                intents.append({'service': 'contacts', 'action': 'delete'})
            elif any(word in message for word in ['update', 'change', 'edit']):
                intents.append({'service': 'contacts', 'action': 'update'})
        
        # Tasks intents
        if any(word in message for word in ['task', 'todo', 'reminder', 'to-do', 'remind']):
            if any(word in message for word in ['add', 'create', 'new', 'set']):
                intents.append({'service': 'tasks', 'action': 'add'})
            elif any(word in message for word in ['complete', 'done', 'finish', 'check']):
                intents.append({'service': 'tasks', 'action': 'complete'})
            elif any(word in message for word in ['delete', 'remove']):
                intents.append({'service': 'tasks', 'action': 'delete'})
            elif any(word in message for word in ['show', 'list', 'view', 'what']):
                intents.append({'service': 'tasks', 'action': 'list'})
        
        return intents