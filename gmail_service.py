# =====================================
# FILE: services/gmail/gmail_service.py (FINAL COMPLETE VERSION)
# =====================================
"""Gmail service implementation with full functionality"""
import logging
import base64
import re
from email.mime.text import MIMEText
from typing import Dict
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

class GmailService(BaseGoogleService):
    """Gmail service implementation with full functionality"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.search_results = {}

    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle Gmail-specific actions"""
        action_handlers = {
            'SEND_EMAIL': self.handle_send_email,
            'SEARCH_EMAILS': self.handle_search_emails,
            'READ_EMAIL': self.handle_read_email,
            'DRAFT_EMAIL': self.handle_draft_email,
            'DELETE_EMAIL': self.handle_delete_email,
            'LIST_UNREAD': self.handle_list_unread,
            'MARK_READ': self.handle_mark_read,
            'REPLY_EMAIL': self.handle_reply_email
        }
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        return {'success': False, 'message': f'Unknown Gmail action: {action}'}

    async def perform_actual_delete(self, email_id: str) -> Dict:
        """Takes an email ID and performs the API call to move it to the trash."""
        if not email_id:
            return {'success': False, 'message': 'Cannot delete: No email ID was provided.'}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/trash')
        if result.get('success'):
            return {'success': True, 'message': '✅ Email moved to trash successfully!'}
        return {'success': False, 'message': f"❌ Failed to delete email: {result.get('error', 'Unknown error')}"}

    async def handle_send_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Sends an email."""
        to = params.get('to')
        subject = params.get('subject', 'No Subject')
        body = params.get('body', '')
        if not to:
            return {'success': False, 'message': 'Recipient email address is required.'}
        
        email = MIMEText(body)
        email['To'], email['From'], email['Subject'] = to, 'me', subject
        raw_message = base64.urlsafe_b64encode(email.as_bytes()).decode('utf-8')
        
        result = await self.make_api_call('POST', 'users/me/messages/send', json_data={'raw': raw_message})
        return {'success': True, 'message': f"✅ Email sent to {to}"} if result.get('success') else {'success': False, 'message': f"Failed to send: {result.get('error')}"}

    async def handle_search_emails(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Searches for emails and lists them."""
        query = params.get('query', '')
        result = await self.make_api_call('GET', 'users/me/messages', params={'q': query, 'maxResults': 5})
        if not result.get('success'):
            return {'success': False, 'message': f"Search failed: {result.get('error')}"}
        
        messages = result.get('data', {}).get('messages', [])
        if not messages:
            return {'success': True, 'message': f'No emails found for: "{query}"'}
        
        response_text, email_list = "📧 **Search results:**\n\n", []
        for i, msg in enumerate(messages, 1):
            msg_details = await self.make_api_call('GET', f'users/me/messages/{msg["id"]}')
            if msg_details.get('success'):
                email_data = msg_details['data']
                headers = self._parse_headers(email_data)
                response_text += f"**{i}. {headers.get('Subject', 'No Subject')}**\n   From: {headers.get('From', 'Unknown')}\n\n"
                email_list.append(email_data)
        
        self.search_results[message.from_user.id] = email_list
        return {'success': True, 'message': response_text}

    async def handle_read_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Reads the content of a specific email."""
        email_id = params.get('email_id')
        if not email_id:
            return {'success': False, 'message': 'Please search for an email first.'}

        result = await self.make_api_call('GET', f'users/me/messages/{email_id}')
        if not result.get('success'):
            return {'success': False, 'message': f"Failed to read email: {result.get('error')}"}
        
        email_data = result['data']
        headers = self._parse_headers(email_data)
        body = self._get_email_body(email_data)
        response = f"""**From:** {headers.get('From')}\n**Subject:** {headers.get('Subject')}\n\n{body[:1000]}"""
        return {'success': True, 'message': response}

    async def handle_delete_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Finds emails to delete and asks the user for confirmation."""
        query = params.get('description', 'is:unread')
        search_results_msg = await self.handle_search_emails({'query': query}, message, state)
        if not self.search_results.get(message.from_user.id):
            return {'success': True, 'message': f'No emails found matching "{query}" to delete.'}
        
        await state.set_state(BotStates.selecting_email)
        await state.update_data(action='delete')
        
        response_text = "📧 **Which email would you like to delete?**\n\n" + search_results_msg['message']
        response_text += "\n**Reply with the number to delete, or 'cancel'.**"
        return {'success': True, 'message': response_text}

    async def handle_list_unread(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Lists unread emails by calling the search function."""
        return await self.handle_search_emails({'query': 'is:unread'}, message, state)

    async def handle_draft_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Creates a draft email."""
        draft_message = MIMEText(params.get('body', ''))
        draft_message['To'] = params.get('to', '')
        draft_message['From'] = 'me'
        draft_message['Subject'] = params.get('subject', 'Draft')
        raw_message = base64.urlsafe_b64encode(draft_message.as_bytes()).decode('utf-8')
        body = {'message': {'raw': raw_message}}
        result = await self.make_api_call('POST', 'users/me/drafts', json_data=body)
        if result['success']:
            return {'success': True, 'message': '✅ Draft created successfully'}
        return {'success': False, 'message': f"Failed to create draft: {result.get('error')}"}

    async def handle_mark_read(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Marks an email as read by removing the UNREAD label."""
        email_id = params.get('email_id')
        if not email_id:
            return {'success': False, 'message': 'Email ID required'}
        body = {'removeLabelIds': ['UNREAD']}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify', json_data=body)
        if result['success']:
            return {'success': True, 'message': '✅ Email marked as read'}
        return {'success': False, 'message': f"Failed: {result.get('error')}"}

    async def handle_reply_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Replies to an email, maintaining the thread."""
        reply_body = params.get('body', '')
        to_email = params.get('to', '')
        if not to_email:
            return {'success': False, 'message': 'Recipient email required for reply'}

        search_query = f'from:{to_email} OR to:{to_email}'
        search_result = await self.make_api_call('GET', 'users/me/messages', params={'q': search_query, 'maxResults': 1})
        
        if not search_result.get('success') or not search_result.get('data', {}).get('messages'):
            return await self.handle_send_email({'to': to_email, 'subject': 'Re:', 'body': reply_body}, message, state)

        original_id = search_result['data']['messages'][0]['id']
        original_result = await self.make_api_call('GET', f'users/me/messages/{original_id}')
        
        if original_result['success']:
            email_data = original_result['data']
            headers = self._parse_headers(email_data)
            thread_id = email_data.get('threadId')
            original_subject = headers.get('Subject', '')
            reply_subject = f"Re: {original_subject}" if not original_subject.lower().startswith('re:') else original_subject
            
            reply_message = MIMEText(reply_body)
            reply_message['To'], reply_message['From'], reply_message['Subject'] = to_email, 'me', reply_subject
            raw_message = base64.urlsafe_b64encode(reply_message.as_bytes()).decode('utf-8')
            body = {'raw': raw_message, 'threadId': thread_id}
            
            send_result = await self.make_api_call('POST', 'users/me/messages/send', json_data=body)
            if send_result['success']:
                return {'success': True, 'message': f"✅ Reply sent to {to_email}"}
            return {'success': False, 'message': f"Failed to send reply: {send_result.get('error')}"}
        
        return {'success': False, 'message': 'Could not find original email to reply to.'}

    def _parse_headers(self, email_data: Dict) -> Dict:
        """Helper to parse headers from email data."""
        return {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}

    def _get_email_body(self, email_data: Dict) -> str:
        """Helper to extract the plain text body from email data."""
        payload = email_data.get('payload', {})
        if 'data' in payload.get('body', {}):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', 'ignore')
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', 'ignore')
        return email_data.get('snippet', '')