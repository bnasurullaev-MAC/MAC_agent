"""Gemini AI processing for intent recognition and response generation"""
import logging
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import google.generativeai as genai
from config import Config

logger = logging.getLogger(__name__)

class GeminiProcessor:
    """Processes user messages with Gemini AI"""
    
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None
            logger.warning("Gemini API key not configured")
        
        self.timezone = Config.DEFAULT_TIMEZONE
    
    async def process(self, 
                     user_message: str, 
                     user_id: int,
                     context: str,
                     available_services: Dict) -> Dict:
        """Process user message and return structured response with actions"""
        
        if not self.model:
            return {
                'text': "I need Gemini AI to process your request. Please configure the API key.",
                'actions': []
            }
        
        try:
            # Build the prompt
            prompt = self._build_prompt(user_message, context, available_services)
            
            # Generate response
            response = await self.model.generate_content_async(prompt)
            response_text = response.text.strip()
            
            # Parse response for actions
            clean_text, actions = self._parse_response(response_text)
            
            return {
                'text': clean_text,
                'actions': actions
            }
            
        except Exception as e:
            logger.error(f"Gemini processing error: {e}")
            return {
                'text': "I encountered an error processing your request. Please try again.",
                'actions': []
            }
    
    def _build_prompt(self, user_message: str, context: str, services: Dict) -> str:
        """Build the prompt for Gemini with real service access"""
        current_date = datetime.now(self.timezone).strftime('%A, %B %d, %Y')
        current_time = datetime.now(self.timezone).strftime('%I:%M %p %Z')
        
        # Get available service names
        service_list = ', '.join(services.keys()) if services else 'No services available'
        
        prompt = f"""You are an AI assistant with FULL ACCESS to the user's Google services through APIs.
Today is {current_date} at {current_time}.

Available services: {service_list}

IMPORTANT CAPABILITIES:
✅ You have FULL ACCESS to actually:
- Send, read, search, and manage Gmail emails
- Create, update, delete calendar events  
- Manage contacts
- Search and manage Google Drive files
- Create and manage tasks

You are NOT simulating - you have REAL API access to these services.

{context}

Current user message: "{user_message}"

RESPONSE INSTRUCTIONS:
1. Respond naturally and helpfully
2. When the user asks about emails, calendar, files, etc., USE the actual service actions
3. Do NOT say you can't access their data - you CAN through the APIs
4. Do NOT simulate or make up data - use real API calls

ACTION FORMATS (use these exact formats):

Gmail Actions:
[SERVICE_ACTION: GMAIL | action: SEND_EMAIL | to: "email@example.com" | subject: "Subject" | body: "Message text"]
[SERVICE_ACTION: GMAIL | action: SEARCH_EMAILS | query: "search terms" | max_results: "5"]
[SERVICE_ACTION: GMAIL | action: LIST_UNREAD | max_results: "5"]
[SERVICE_ACTION: GMAIL | action: GET_LAST_EMAIL]
[SERVICE_ACTION: GMAIL | action: READ_EMAIL | email_id: "id"]
[SERVICE_ACTION: GMAIL | action: DELETE_EMAIL | email_id: "id"]
[SERVICE_ACTION: GMAIL | action: DRAFT_EMAIL | to: "email" | subject: "subject" | body: "text"]
[SERVICE_ACTION: GMAIL | action: MARK_READ | email_id: "id"]

Calendar Actions:
[SERVICE_ACTION: CALENDAR | action: CREATE_EVENT | title: "Meeting" | date: "tomorrow" | time: "2pm" | duration: "1 hour"]
[SERVICE_ACTION: CALENDAR | action: VIEW_EVENTS | range: "today/tomorrow/week/month"]
[SERVICE_ACTION: CALENDAR | action: UPDATE_EVENT | old_description: "old event" | new_date: "date" | new_time: "time"]
[SERVICE_ACTION: CALENDAR | action: DELETE_EVENT | description: "event to delete"]
[SERVICE_ACTION: CALENDAR | action: SEARCH_EVENTS | query: "search term"]

Contacts Actions:
[SERVICE_ACTION: CONTACTS | action: FIND_CONTACT | name: "John Doe"]
[SERVICE_ACTION: CONTACTS | action: ADD_CONTACT | name: "Name" | email: "email" | phone: "phone"]
[SERVICE_ACTION: CONTACTS | action: UPDATE_CONTACT | name: "Name" | new_email: "email"]
[SERVICE_ACTION: CONTACTS | action: DELETE_CONTACT | name: "Name"]
[SERVICE_ACTION: CONTACTS | action: LIST_CONTACTS | max_results: "20"]

Drive Actions:
[SERVICE_ACTION: DRIVE | action: SEARCH_FILES | query: "filename" | file_type: "type"]
[SERVICE_ACTION: DRIVE | action: CREATE_FOLDER | name: "Folder Name"]
[SERVICE_ACTION: DRIVE | action: LIST_RECENT | max_results: "10"]
[SERVICE_ACTION: DRIVE | action: DELETE_FILE | name: "filename"]
[SERVICE_ACTION: DRIVE | action: SHARE_FILE | name: "filename" | email: "user@example.com" | role: "reader"]

Tasks Actions:
[SERVICE_ACTION: TASKS | action: ADD_TASK | title: "Task name" | due_date: "tomorrow"]
[SERVICE_ACTION: TASKS | action: LIST_TASKS | show_completed: "false"]
[SERVICE_ACTION: TASKS | action: COMPLETE_TASK | title: "task name"]
[SERVICE_ACTION: TASKS | action: DELETE_TASK | title: "task name"]

EXAMPLES:

User: "Send email to john@example.com saying hello"
Response: I'll send that email to John for you.
[SERVICE_ACTION: GMAIL | action: SEND_EMAIL | to: "john@example.com" | subject: "Hello" | body: "Hello John,\n\nI hope this message finds you well.\n\nBest regards"]

User: "Show me my last unread email"
Response: Let me check your unread emails.
[SERVICE_ACTION: GMAIL | action: LIST_UNREAD | max_results: "1"]

User: "Schedule a meeting tomorrow at 2pm"
Response: I'll schedule that meeting for tomorrow at 2pm.
[SERVICE_ACTION: CALENDAR | action: CREATE_EVENT | title: "Meeting" | date: "tomorrow" | time: "2pm" | duration: "1 hour"]

User: "Find Sarah's contact"
Response: I'll search for Sarah's contact information.
[SERVICE_ACTION: CONTACTS | action: FIND_CONTACT | name: "Sarah"]

Remember:
- You HAVE access to their real data through APIs
- Always use the service actions when asked about emails, calendar, etc.
- Don't make up or simulate data
- Be helpful and execute the requested actions

Respond naturally and trigger appropriate actions:"""
        
        return prompt
    
    def _parse_response(self, response: str) -> Tuple[str, List[Dict]]:
        """Parse response for action tags and clean the text"""
        # Find all action tags
        action_pattern = r'\[SERVICE_ACTION:\s*([A-Z]+)\s*\|([^\]]+)\]'
        matches = re.findall(action_pattern, response)
        
        # Remove action tags from response text
        clean_text = re.sub(action_pattern, '', response).strip()
        
        # Clean up extra whitespace and empty lines
        clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
        clean_text = clean_text.strip()
        
        # Parse actions
        actions = []
        for service, params_str in matches:
            params = {}
            parts = params_str.split('|')
            
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    params[key] = value
            
            actions.append({
                'service': service.lower(),
                'action': params.get('action', ''),
                'params': params
            })
        
        return clean_text, actions