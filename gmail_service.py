"""Gmail service with comprehensive functionality and error handling"""
import logging
import base64
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

class GmailService(BaseGoogleService):
    """Gmail service with full functionality"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.search_results = {}
        self.draft_storage = {}
        self.labels_cache = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle all Gmail actions"""
        action_handlers = {
            'SEND_EMAIL': self.handle_send_email,
            'SEARCH_EMAILS': self.handle_search_emails,
            'READ_EMAIL': self.handle_read_email,
            'DRAFT_EMAIL': self.handle_draft_email,
            'DELETE_EMAIL': self.handle_delete_email,
            'LIST_UNREAD': self.handle_list_unread,
            'MARK_READ': self.handle_mark_read,
            'MARK_UNREAD': self.handle_mark_unread,
            'REPLY_EMAIL': self.handle_reply_email,
            'FORWARD_EMAIL': self.handle_forward_email,
            'STAR_EMAIL': self.handle_star_email,
            'ARCHIVE_EMAIL': self.handle_archive_email,
            'SPAM_EMAIL': self.handle_spam_email,
            'LIST_IMPORTANT': self.handle_list_important,
            'LIST_SENT': self.handle_list_sent,
            'LIST_DRAFTS': self.handle_list_drafts,
            'ATTACH_FILE': self.handle_attach_file,
            'CREATE_LABEL': self.handle_create_label,
            'APPLY_LABEL': self.handle_apply_label,
            'GET_LAST_EMAIL': self.handle_get_last_email
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'❌ Unknown Gmail action: {action}'}
    
    async def perform_actual_delete(self, email_id: str) -> Dict:
        """Delete an email (move to trash)"""
        if not email_id:
            return {'success': False, 'message': '❌ No email ID provided'}
        
        logger.info(f"Deleting email ID: {email_id}")
        
        # First verify the email exists
        check_result = await self.make_api_call('GET', f'users/me/messages/{email_id}')
        
        if not check_result.get('success'):
            error = check_result.get('error', '')
            if '404' in str(error):
                return {'success': True, 'message': '✅ Email already deleted or not found'}
            return {'success': False, 'message': f'❌ Cannot access email: {error}'}
        
        # Move to trash
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/trash')
        
        if result.get('success'):
            return {'success': True, 'message': '✅ **Email moved to trash successfully!**'}
        else:
            error = result.get('error', 'Unknown error')
            if '404' in str(error):
                return {'success': True, 'message': '✅ Email already deleted'}
            return {'success': False, 'message': f'❌ Failed to delete: {error}'}
    
    async def handle_send_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Send an email with enhanced features"""
        to = params.get('to', '').strip()
        subject = params.get('subject', 'No Subject')
        body = params.get('body', '')
        cc = params.get('cc', '')
        bcc = params.get('bcc', '')
        
        if not to:
            return {'success': False, 'message': '❌ Recipient email required'}
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', to):
            return {'success': False, 'message': f'❌ Invalid email address: {to}'}
        
        # Create message
        msg = MIMEMultipart() if params.get('attachments') else MIMEText(body)
        
        if isinstance(msg, MIMEMultipart):
            msg.attach(MIMEText(body, 'plain'))
        
        msg['To'] = to
        msg['From'] = 'me'
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        
        # Handle attachments if any
        if params.get('attachments'):
            for attachment in params['attachments']:
                await self._add_attachment(msg, attachment)
        
        # Send email
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        result = await self.make_api_call('POST', 'users/me/messages/send', json_data={'raw': raw})
        
        if result.get('success'):
            return {'success': True, 'message': f'✅ **Email sent to {to}!**\nSubject: {subject}'}
        
        return {'success': False, 'message': f'❌ Failed to send: {result.get("error")}'}
    
    async def handle_search_emails(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Search emails with advanced query support"""
        query = params.get('query', '')
        max_results = min(int(params.get('max_results', 10)), 20)
        
        # Build advanced query
        if params.get('from'):
            query += f' from:{params["from"]}'
        if params.get('to'):
            query += f' to:{params["to"]}'
        if params.get('subject'):
            query += f' subject:{params["subject"]}'
        if params.get('has_attachment'):
            query += ' has:attachment'
        if params.get('date_after'):
            query += f' after:{params["date_after"]}'
        if params.get('date_before'):
            query += f' before:{params["date_before"]}'
        
        query = query.strip() or 'is:unread'
        
        logger.info(f"Searching emails: {query}")
        
        # Search emails
        result = await self.make_api_call('GET', 'users/me/messages', 
                                         params={'q': query, 'maxResults': max_results})
        
        if not result.get('success'):
            return {'success': False, 'message': f'❌ Search failed: {result.get("error")}'}
        
        messages = result.get('data', {}).get('messages', [])
        
        if not messages:
            return {'success': True, 'message': f'📭 **No emails found for:** "{query}"'}
        
        # Get details for each message
        response_text = f"📧 **Search Results** ({len(messages)} found):\n\n"
        email_list = []
        
        for i, msg in enumerate(messages, 1):
            msg_id = msg.get('id')
            if not msg_id:
                continue
            
            # Get full message
            msg_details = await self.make_api_call('GET', f'users/me/messages/{msg_id}')
            
            if msg_details.get('success'):
                email_data = msg_details['data']
                # CRITICAL: Preserve the ID
                email_data['id'] = msg_id
                
                headers = self._parse_headers(email_data)
                snippet = email_data.get('snippet', '')[:100]
                
                # Format display
                subject = headers.get('Subject', 'No Subject')
                from_addr = headers.get('From', 'Unknown')
                date = self._format_date(headers.get('Date', ''))
                
                # Check for attachments
                has_attach = self._has_attachments(email_data)
                attach_icon = "📎" if has_attach else ""
                
                # Check if unread
                unread = 'UNREAD' in email_data.get('labelIds', [])
                unread_icon = "🔵" if unread else ""
                
                response_text += f"**{i}.** {unread_icon}{attach_icon} **{subject}**\n"
                response_text += f"   From: {from_addr}\n"
                response_text += f"   Date: {date}\n"
                response_text += f"   {snippet}...\n\n"
                
                email_list.append(email_data)
        
        # Store results
        user_id = message.from_user.id
        self.search_results[user_id] = email_list
        
        return {'success': True, 'message': response_text}
    
    async def handle_delete_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle email deletion with search and selection"""
        # Direct deletion if ID provided
        email_id = params.get('email_id')
        if email_id:
            return await self.perform_actual_delete(email_id)
        
        # Search for emails to delete
        description = params.get('description', '')
        query = params.get('query', description)
        
        # Build smart query
        if not query:
            query = 'is:unread'
        elif 'spam' in query.lower():
            query = 'is:spam'
        elif 'old' in query.lower():
            query = 'older_than:30d'
        elif 'promotional' in query.lower():
            query = 'category:promotions'
        
        logger.info(f"Searching emails to delete: {query}")
        
        # Search
        result = await self.make_api_call('GET', 'users/me/messages', 
                                         params={'q': query, 'maxResults': 10})
        
        if not result.get('success'):
            return {'success': False, 'message': f'❌ Search failed: {result.get("error")}'}
        
        messages = result.get('data', {}).get('messages', [])
        
        if not messages:
            return {'success': True, 'message': f'📭 No emails found to delete for: "{query}"'}
        
        # Get details and prepare selection
        email_list = []
        response_text = "🗑 **Select email to delete:**\n\n"
        
        for i, msg in enumerate(messages[:10], 1):
            msg_id = msg.get('id')
            if not msg_id:
                continue
            
            msg_details = await self.make_api_call('GET', f'users/me/messages/{msg_id}')
            
            if msg_details.get('success'):
                email_data = msg_details['data']
                email_data['id'] = msg_id  # Preserve ID
                
                headers = self._parse_headers(email_data)
                subject = headers.get('Subject', 'No Subject')[:50]
                from_addr = headers.get('From', 'Unknown')[:30]
                
                response_text += f"**{i}. {subject}**\n"
                response_text += f"   From: {from_addr}\n\n"
                
                email_list.append(email_data)
        
        # Store and set state
        user_id = message.from_user.id
        self.search_results[user_id] = email_list
        
        await state.set_state(BotStates.selecting_email)
        await state.update_data(action='delete')
        
        # Clear instructions
        if len(email_list) == 1:
            response_text += "✅ **Reply 'yes' or '1' to delete**\n"
        else:
            response_text += f"**Reply with number (1-{len(email_list)}) to delete**\n"
        response_text += "❌ **Or 'cancel' to stop**"
        
        await message.answer(response_text, parse_mode='Markdown')
        return {'success': True}
    
    async def handle_read_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Read full email content"""
        email_id = params.get('email_id')
        
        if not email_id:
            # Try to get from last search
            user_id = message.from_user.id
            if user_id in self.search_results and self.search_results[user_id]:
                # Set up selection
                await state.set_state(BotStates.selecting_email)
                await state.update_data(action='read')
                
                response = "📖 **Select email to read:**\n\n"
                for i, email in enumerate(self.search_results[user_id][:10], 1):
                    headers = self._parse_headers(email)
                    response += f"{i}. {headers.get('Subject', 'No Subject')}\n"
                
                response += "\n**Reply with number or 'cancel'**"
                return {'success': True, 'message': response}
            
            return {'success': False, 'message': '❌ No email selected. Search first!'}
        
        # Get email
        result = await self.make_api_call('GET', f'users/me/messages/{email_id}')
        
        if not result.get('success'):
            return {'success': False, 'message': f'❌ Failed to read: {result.get("error")}'}
        
        email_data = result['data']
        headers = self._parse_headers(email_data)
        body = self._get_email_body(email_data)
        
        # Format response
        response = f"""📧 **Email Content**
        
**From:** {headers.get('From', 'Unknown')}
**To:** {headers.get('To', 'Unknown')}
**Subject:** {headers.get('Subject', 'No Subject')}
**Date:** {self._format_date(headers.get('Date', ''))}

**Message:**
{body[:2000]}"""
        
        if len(body) > 2000:
            response += f"\n\n... (Message truncated, {len(body)-2000} chars remaining)"
        
        # Check attachments
        if self._has_attachments(email_data):
            attachments = self._get_attachment_info(email_data)
            response += f"\n\n📎 **Attachments:** {', '.join(attachments)}"
        
        return {'success': True, 'message': response}
    
    async def handle_list_unread(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List unread emails"""
        max_results = min(int(params.get('max_results', 5)), 20)
        return await self.handle_search_emails({
            'query': 'is:unread',
            'max_results': str(max_results)
        }, message, state)
    
    async def handle_list_important(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List important emails"""
        return await self.handle_search_emails({
            'query': 'is:important',
            'max_results': params.get('max_results', '10')
        }, message, state)
    
    async def handle_list_sent(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List sent emails"""
        return await self.handle_search_emails({
            'query': 'is:sent',
            'max_results': params.get('max_results', '10')
        }, message, state)
    
    async def handle_mark_read(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Mark email as read"""
        email_id = params.get('email_id')
        
        if not email_id:
            return {'success': False, 'message': '❌ Email ID required'}
        
        body = {'removeLabelIds': ['UNREAD']}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify', 
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': '✅ **Email marked as read**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_mark_unread(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Mark email as unread"""
        email_id = params.get('email_id')
        
        if not email_id:
            return {'success': False, 'message': '❌ Email ID required'}
        
        body = {'addLabelIds': ['UNREAD']}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify', 
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': '✅ **Email marked as unread**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_reply_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Reply to an email"""
        to = params.get('to', '')
        body = params.get('body', '')
        
        if not to:
            return {'success': False, 'message': '❌ Recipient required'}
        
        # Find original email
        search_query = f'from:{to} OR to:{to}'
        search_result = await self.make_api_call('GET', 'users/me/messages', 
                                                params={'q': search_query, 'maxResults': 1})
        
        if search_result.get('success') and search_result.get('data', {}).get('messages'):
            original = search_result['data']['messages'][0]
            original_id = original['id']
            
            # Get original details
            orig_result = await self.make_api_call('GET', f'users/me/messages/{original_id}')
            
            if orig_result['success']:
                orig_data = orig_result['data']
                headers = self._parse_headers(orig_data)
                thread_id = orig_data.get('threadId')
                
                # Prepare reply
                subject = headers.get('Subject', '')
                if not subject.lower().startswith('re:'):
                    subject = f'Re: {subject}'
                
                reply = MIMEText(body)
                reply['To'] = to
                reply['From'] = 'me'
                reply['Subject'] = subject
                reply['In-Reply-To'] = headers.get('Message-ID', '')
                reply['References'] = headers.get('Message-ID', '')
                
                raw = base64.urlsafe_b64encode(reply.as_bytes()).decode('utf-8')
                
                result = await self.make_api_call('POST', 'users/me/messages/send',
                                                 json_data={'raw': raw, 'threadId': thread_id})
                
                if result['success']:
                    return {'success': True, 'message': f'✅ **Reply sent to {to}**'}
                
                return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
        
        # No original found, send as new
        return await self.handle_send_email({
            'to': to,
            'subject': 'Re: Your message',
            'body': body
        }, message, state)
    
    async def handle_draft_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create a draft email"""
        msg = MIMEText(params.get('body', ''))
        msg['To'] = params.get('to', '')
        msg['From'] = 'me'
        msg['Subject'] = params.get('subject', 'Draft')
        
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        body = {'message': {'raw': raw}}
        
        result = await self.make_api_call('POST', 'users/me/drafts', json_data=body)
        
        if result['success']:
            draft_id = result.get('data', {}).get('id')
            return {'success': True, 'message': f'✅ **Draft created!**\nDraft ID: {draft_id}'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_archive_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Archive an email"""
        email_id = params.get('email_id')
        
        if not email_id:
            return {'success': False, 'message': '❌ Email ID required'}
        
        body = {'removeLabelIds': ['INBOX']}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify',
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': '✅ **Email archived**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_star_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Star/unstar an email"""
        email_id = params.get('email_id')
        star = params.get('star', True)
        
        if not email_id:
            return {'success': False, 'message': '❌ Email ID required'}
        
        if star:
            body = {'addLabelIds': ['STARRED']}
            action = 'starred'
        else:
            body = {'removeLabelIds': ['STARRED']}
            action = 'unstarred'
        
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify',
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': f'✅ **Email {action}**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_spam_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Mark email as spam"""
        email_id = params.get('email_id')
        
        if not email_id:
            return {'success': False, 'message': '❌ Email ID required'}
        
        body = {'addLabelIds': ['SPAM'], 'removeLabelIds': ['INBOX']}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify',
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': '✅ **Email marked as spam**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_forward_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Forward an email"""
        email_id = params.get('email_id')
        to = params.get('to')
        
        if not email_id or not to:
            return {'success': False, 'message': '❌ Email ID and recipient required'}
        
        # Get original email
        result = await self.make_api_call('GET', f'users/me/messages/{email_id}')
        
        if not result.get('success'):
            return {'success': False, 'message': f'❌ Cannot get email: {result.get("error")}'}
        
        orig_data = result['data']
        headers = self._parse_headers(orig_data)
        body = self._get_email_body(orig_data)
        
        # Create forward message
        fwd_subject = headers.get('Subject', 'No Subject')
        if not fwd_subject.lower().startswith('fwd:'):
            fwd_subject = f'Fwd: {fwd_subject}'
        
        fwd_body = f"""---------- Forwarded message ----------
From: {headers.get('From', 'Unknown')}
Date: {headers.get('Date', 'Unknown')}
Subject: {headers.get('Subject', 'No Subject')}
To: {headers.get('To', 'Unknown')}

{body}"""
        
        # Send as new email
        return await self.handle_send_email({
            'to': to,
            'subject': fwd_subject,
            'body': fwd_body
        }, message, state)
    
    async def handle_get_last_email(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Get the most recent email"""
        return await self.handle_search_emails({
            'query': 'in:inbox',
            'max_results': '1'
        }, message, state)
    
    async def handle_list_drafts(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """List draft emails"""
        result = await self.make_api_call('GET', 'users/me/drafts',
                                         params={'maxResults': 10})
        
        if not result.get('success'):
            return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
        
        drafts = result.get('data', {}).get('drafts', [])
        
        if not drafts:
            return {'success': True, 'message': '📭 **No drafts found**'}
        
        response = "📝 **Your Drafts:**\n\n"
        
        for i, draft in enumerate(drafts[:10], 1):
            draft_id = draft['id']
            msg_id = draft['message']['id']
            
            # Get draft details
            msg_result = await self.make_api_call('GET', f'users/me/messages/{msg_id}')
            
            if msg_result.get('success'):
                msg_data = msg_result['data']
                headers = self._parse_headers(msg_data)
                
                response += f"{i}. **{headers.get('Subject', 'No Subject')}**\n"
                response += f"   To: {headers.get('To', 'Not specified')}\n\n"
        
        return {'success': True, 'message': response}
    
    async def handle_create_label(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Create a new label"""
        name = params.get('name', '')
        
        if not name:
            return {'success': False, 'message': '❌ Label name required'}
        
        label_data = {
            'name': name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        
        result = await self.make_api_call('POST', 'users/me/labels', json_data=label_data)
        
        if result['success']:
            return {'success': True, 'message': f'✅ **Label "{name}" created**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_apply_label(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Apply label to email"""
        email_id = params.get('email_id')
        label = params.get('label')
        
        if not email_id or not label:
            return {'success': False, 'message': '❌ Email ID and label required'}
        
        # Get label ID
        labels_result = await self.make_api_call('GET', 'users/me/labels')
        
        if not labels_result['success']:
            return {'success': False, 'message': '❌ Cannot get labels'}
        
        label_id = None
        for l in labels_result.get('data', {}).get('labels', []):
            if l['name'].lower() == label.lower():
                label_id = l['id']
                break
        
        if not label_id:
            return {'success': False, 'message': f'❌ Label "{label}" not found'}
        
        body = {'addLabelIds': [label_id]}
        result = await self.make_api_call('POST', f'users/me/messages/{email_id}/modify',
                                         json_data=body)
        
        if result['success']:
            return {'success': True, 'message': f'✅ **Label "{label}" applied**'}
        
        return {'success': False, 'message': f'❌ Failed: {result.get("error")}'}
    
    async def handle_attach_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file attachment (placeholder for actual implementation)"""
        return {'success': True, 'message': '📎 To attach files, please send them directly to the bot after composing your email.'}
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _parse_headers(self, email_data: Dict) -> Dict:
        """Parse email headers"""
        headers = {}
        payload = email_data.get('payload', {})
        for header in payload.get('headers', []):
            headers[header['name']] = header['value']
        return headers
    
    def _get_email_body(self, email_data: Dict) -> str:
        """Extract email body text"""
        payload = email_data.get('payload', {})
        
        # Try direct body
        if 'data' in payload.get('body', {}):
            try:
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', 'ignore')
            except Exception as e:
                logger.error(f"Error decoding body: {e}")
        
        # Try multipart
        if 'parts' in payload:
            for part in payload['parts']:
                # Prefer plain text
                if part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                    try:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', 'ignore')
                    except Exception as e:
                        logger.error(f"Error decoding part: {e}")
                
                # Recursively check nested parts
                if 'parts' in part:
                    for subpart in part['parts']:
                        if subpart['mimeType'] == 'text/plain' and 'data' in subpart.get('body', {}):
                            try:
                                return base64.urlsafe_b64decode(subpart['body']['data']).decode('utf-8', 'ignore')
                            except Exception as e:
                                logger.error(f"Error decoding subpart: {e}")
        
        # Fallback to snippet
        return email_data.get('snippet', 'No content available')
    
    def _has_attachments(self, email_data: Dict) -> bool:
        """Check if email has attachments"""
        payload = email_data.get('payload', {})
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    return True
                if 'parts' in part:
                    for subpart in part['parts']:
                        if subpart.get('filename'):
                            return True
        
        return False
    
    def _get_attachment_info(self, email_data: Dict) -> List[str]:
        """Get attachment filenames"""
        attachments = []
        payload = email_data.get('payload', {})
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    attachments.append(part['filename'])
                if 'parts' in part:
                    for subpart in part['parts']:
                        if subpart.get('filename'):
                            attachments.append(subpart['filename'])
        
        return attachments
    
    def _format_date(self, date_str: str) -> str:
        """Format date string for display"""
        if not date_str:
            return 'Unknown'
        
        try:
            # Parse various date formats
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            
            # Format based on age
            now = datetime.now(dt.tzinfo)
            diff = now - dt
            
            if diff.days == 0:
                return dt.strftime("Today %I:%M %p")
            elif diff.days == 1:
                return dt.strftime("Yesterday %I:%M %p")
            elif diff.days < 7:
                return dt.strftime("%A %I:%M %p")
            elif diff.days < 365:
                return dt.strftime("%b %d")
            else:
                return dt.strftime("%b %d, %Y")
                
        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return date_str[:20]
    
    async def _add_attachment(self, msg: MIMEMultipart, attachment: Dict):
        """Add attachment to email"""
        try:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment['data'])
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={attachment["filename"]}')
            msg.attach(part)
        except Exception as e:
            logger.error(f"Error adding attachment: {e}")