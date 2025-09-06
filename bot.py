# =====================================
# FILE: core/bot.py (COMPLETE OPTIMIZED VERSION)
# =====================================
"""Core bot implementation with comprehensive service orchestration"""
import asyncio
import os
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from auth.google_auth import GoogleAuthManager
from core.conversation_manager import ConversationManager
from core.gemini_processor import GeminiProcessor
from states.bot_states import BotStates
from config import Config

# Import all services
from services.calendar.calendar_service import CalendarService
from services.gmail.gmail_service import GmailService
from services.contacts.contacts_service import ContactsService
from services.drive.drive_service import DriveService
from services.tasks.tasks_service import TasksService

logger = logging.getLogger(__name__)

class GoogleAssistantBot:
    """Main bot class with comprehensive service orchestration"""
    
    def __init__(self):
        """Initialize bot with all components"""
        self.bot = Bot(token=Config.BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.auth_manager = GoogleAuthManager()
        self.conversation_manager = ConversationManager()
        self.gemini_processor = GeminiProcessor()
        self.services = {}
        self.user_preferences = {}  # Store user preferences
        self.initialize_services()
        self.setup_handlers()
        logger.info("Bot initialized successfully with all services")
    
    def initialize_services(self):
        """Initialize all available services"""
        service_classes = {
            'calendar': CalendarService, 
            'gmail': GmailService, 
            'contacts': ContactsService,
            'drive': DriveService, 
            'tasks': TasksService
        }
        
        for name, service_class in service_classes.items():
            config = Config.get_service_config(name)
            if config.get('enabled', False):
                try:
                    self.services[name] = service_class(self.auth_manager, config)
                    logger.info(f"Initialized {name} service successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize {name} service: {e}")
    
    def setup_handlers(self):
        """Setup all message and callback handlers"""
        
        # ============================================================
        # COMMAND HANDLERS - Handle all bot commands
        # ============================================================
        
        @self.dp.message(Command("start", "help", "clear", "status", "services", "preferences"))
        async def handle_commands(message: types.Message, state: FSMContext):
            """Handle all bot commands"""
            await state.clear()  # Clear any existing state
            
            if message.text.startswith("/start"):
                # Welcome message with inline keyboard
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📧 Gmail", callback_data="help_gmail"),
                        InlineKeyboardButton(text="📅 Calendar", callback_data="help_calendar")
                    ],
                    [
                        InlineKeyboardButton(text="📁 Drive", callback_data="help_drive"),
                        InlineKeyboardButton(text="👥 Contacts", callback_data="help_contacts")
                    ],
                    [
                        InlineKeyboardButton(text="✅ Tasks", callback_data="help_tasks"),
                        InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")
                    ]
                ])
                
                await message.answer(
                    "👋 **Welcome to Google Assistant Bot!**\n\n"
                    "I'm your AI-powered assistant for all Google services.\n\n"
                    "**What I can do:**\n"
                    "📧 Manage emails - read, send, delete, search\n"
                    "📅 Handle calendar - create events, check schedule\n"
                    "📁 Browse Drive - search files, create folders\n"
                    "👥 Manage contacts - add, find, update\n"
                    "✅ Track tasks - create, complete, organize\n\n"
                    "Just tell me what you need in plain English!\n"
                    "Try: 'Show my unread emails' or 'Schedule a meeting tomorrow'",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                
            elif message.text.startswith("/help"):
                help_text = """📚 **Complete Command Guide**

**📧 Gmail Commands:**
• Show my [unread/important/recent] emails
• Search emails [from someone/about topic]
• Delete email [from sender/about subject]
• Send email to [email] about [subject]
• Reply to [person's] email
• Mark email as read/unread
• Create draft email

**📅 Calendar Commands:**
• Show my events [today/tomorrow/this week/month]
• Schedule [event] [date] at [time]
• Cancel/Delete [event name]
• Update [event] to [new time/date]
• Find meetings with [person]
• Check my availability [date]
• Add reminder for [event]

**📁 Drive Commands:**
• Search for [filename/filetype]
• Create folder named [name]
• Share [file] with [email]
• Delete file [name]
• Show recent files
• Move [file] to [folder]
• Rename [file] to [new name]

**👥 Contacts Commands:**
• Find contact [name/email/phone]
• Add contact [name] [email] [phone]
• Update [contact] email/phone
• Delete contact [name]
• Show all contacts
• Search contacts at [company]

**✅ Tasks Commands:**
• Add task [description] due [date]
• Show my tasks [today/pending/completed]
• Complete task [name]
• Delete task [name]
• Create task list [name]
• Move task to [list]

**💡 Pro Tips:**
• Use natural language - I understand context!
• Chain commands: "Find John's email and reply"
• Ask follow-ups: "Delete the third one"
• Say "cancel" anytime to stop an action"""
                
                await message.answer(help_text, parse_mode='Markdown')
                
            elif message.text.startswith("/clear"):
                self.conversation_manager.clear_history(message.from_user.id)
                await message.answer("🗑 **Conversation cleared!**\nFresh start - how can I help?", parse_mode='Markdown')
                
            elif message.text.startswith("/status"):
                services_status = []
                for name, service in self.services.items():
                    # Check if service is working
                    emoji = "✅" if service else "❌"
                    services_status.append(f"{emoji} {name.capitalize()}")
                
                current_state = await state.get_state()
                state_info = f"State: {current_state.split('.')[-1] if current_state else 'Ready'}"
                
                status_msg = f"""**🤖 Bot Status**
                
**Services:**
{chr(10).join(services_status)}

**System:**
• {state_info}
• Memory: {len(self.conversation_manager.conversations)} conversations
• Uptime: Online

Type /help for commands or just chat naturally!"""
                
                await message.answer(status_msg, parse_mode='Markdown')
                
            elif message.text.startswith("/services"):
                # Show detailed service status
                for name, service in self.services.items():
                    await message.answer(f"**{name.upper()}:** Active ✅", parse_mode='Markdown')
                    
            elif message.text.startswith("/preferences"):
                # User preferences management
                user_id = message.from_user.id
                prefs = self.user_preferences.get(user_id, {})
                await message.answer(
                    f"**Your Preferences:**\n"
                    f"• Default calendar: {prefs.get('calendar', 'primary')}\n"
                    f"• Email display: {prefs.get('email_count', 5)} at a time\n"
                    f"• Time zone: {prefs.get('timezone', 'Auto')}\n",
                    parse_mode='Markdown'
                )
        
        # ============================================================
        # CALLBACK QUERY HANDLERS - Handle inline keyboard buttons
        # ============================================================
        
        @self.dp.callback_query()
        async def handle_callback(callback: types.CallbackQuery):
            """Handle inline keyboard callbacks"""
            data = callback.data
            
            if data.startswith("help_"):
                service = data.replace("help_", "")
                help_texts = {
                    'gmail': "📧 **Gmail Help:**\n• 'Show unread emails'\n• 'Delete spam emails'\n• 'Send email to john@example.com'",
                    'calendar': "📅 **Calendar Help:**\n• 'What's on my calendar today?'\n• 'Schedule meeting tomorrow at 3pm'\n• 'Cancel dentist appointment'",
                    'drive': "📁 **Drive Help:**\n• 'Search for presentation.pptx'\n• 'Create folder Reports'\n• 'Share budget.xlsx with team'",
                    'contacts': "👥 **Contacts Help:**\n• 'Find John Doe's contact'\n• 'Add contact sarah@email.com'\n• 'Update Mike's phone number'",
                    'tasks': "✅ **Tasks Help:**\n• 'Add task Buy groceries'\n• 'Show today's tasks'\n• 'Complete workout task'"
                }
                await callback.message.answer(help_texts.get(service, "Service help not available"), parse_mode='Markdown')
            
            elif data == "settings":
                await callback.message.answer("⚙️ **Settings:**\nCustomization coming soon!\nFor now, use natural language to specify preferences.", parse_mode='Markdown')
            
            await callback.answer()
        
        # ============================================================
        # STATE HANDLERS - Handle multi-step interactions
        # ============================================================
        
        @self.dp.message(StateFilter(BotStates.selecting_email))
        async def handle_email_selection(message: types.Message, state: FSMContext):
            """Handle email selection for various actions"""
            try:
                text = message.text.strip().lower()
                user_id = message.from_user.id
                
                logger.info(f"Email selection handler triggered: {text}")
                
                # Handle cancellation
                if any(word in text for word in ['cancel', 'stop', 'nevermind', 'back', 'exit']):
                    await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Get stored data
                data = await state.get_data()
                action = data.get('action', 'delete')
                
                if 'gmail' not in self.services:
                    await message.answer("❌ Gmail service not available", parse_mode='Markdown')
                    await state.clear()
                    return
                
                gmail_service = self.services['gmail']
                emails = gmail_service.search_results.get(user_id, [])
                
                if not emails:
                    await message.answer("❌ Session expired. Please search again.", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Determine selection
                choice = None
                
                # For single email - accept various confirmations
                if len(emails) == 1:
                    confirm_words = ['yes', 'y', 'ok', 'okay', 'sure', 'confirm', 
                                   'delete', 'delete it', 'do it', 'go', 'proceed',
                                   '1', 'one', 'first', 'this one', 'that one']
                    if any(word in text or text == word for word in confirm_words):
                        choice = 1
                
                # Extract number for multiple emails
                if not choice:
                    # Check for number words
                    number_words = {
                        'one': 1, 'first': 1, 'two': 2, 'second': 2,
                        'three': 3, 'third': 3, 'four': 4, 'fourth': 4,
                        'five': 5, 'fifth': 5, 'six': 6, 'sixth': 6,
                        'seven': 7, 'seventh': 7, 'eight': 8, 'eighth': 8,
                        'nine': 9, 'ninth': 9, 'ten': 10, 'tenth': 10
                    }
                    
                    for word, num in number_words.items():
                        if word in text:
                            choice = num
                            break
                    
                    # Check for digits
                    if not choice:
                        match = re.search(r'\d+', text)
                        if match:
                            choice = int(match.group())
                
                # Execute action
                if choice and 1 <= choice <= len(emails):
                    selected_email = emails[choice - 1]
                    email_id = selected_email.get('id')
                    
                    if not email_id:
                        logger.error(f"No ID found for email at index {choice-1}")
                        await message.answer("❌ **Error:** Cannot find email ID. Please try again.", parse_mode='Markdown')
                        await state.clear()
                        return
                    
                    await self.bot.send_chat_action(message.chat.id, 'typing')
                    
                    # Execute the action based on type
                    if action == 'delete':
                        result = await gmail_service.perform_actual_delete(email_id)
                    elif action == 'read':
                        result = await gmail_service.handle_read_email({'email_id': email_id}, message, state)
                    elif action == 'mark_read':
                        result = await gmail_service.handle_mark_read({'email_id': email_id}, message, state)
                    elif action == 'mark_unread':
                        result = await gmail_service.handle_mark_unread({'email_id': email_id}, message, state)
                    elif action == 'reply':
                        # Set up reply state
                        await state.set_state(BotStates.composing_email)
                        await state.update_data(reply_to=email_id, email_data=selected_email)
                        await message.answer("📝 **Type your reply:**", parse_mode='Markdown')
                        return
                    else:
                        result = {'success': False, 'message': f'Unknown action: {action}'}
                    
                    # Send result
                    if result.get('message'):
                        await message.answer(result['message'], parse_mode='Markdown')
                    
                    # Clean up
                    gmail_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    # Invalid choice - provide helpful feedback
                    if len(emails) == 1:
                        await message.answer(
                            "❗ **To proceed with this email:**\n"
                            "• Type 'yes' or '1' to confirm\n"
                            "• Type 'cancel' to stop",
                            parse_mode='Markdown'
                        )
                    else:
                        await message.answer(
                            f"❗ **Please choose:**\n"
                            f"• Type a number (1-{len(emails)})\n"
                            f"• Or type 'cancel' to stop",
                            parse_mode='Markdown'
                        )
                    
            except Exception as e:
                logger.error(f"Error in email selection: {e}", exc_info=True)
                await message.answer("❌ An error occurred. Please try again.", parse_mode='Markdown')
                await state.clear()
        
        @self.dp.message(StateFilter(BotStates.composing_email))
        async def handle_email_composition(message: types.Message, state: FSMContext):
            """Handle email composition"""
            data = await state.get_data()
            
            if message.text.lower() in ['cancel', 'stop']:
                await message.answer("❌ Email cancelled", parse_mode='Markdown')
                await state.clear()
                return
            
            # Handle reply or new email
            if 'reply_to' in data:
                # Send reply
                email_data = data.get('email_data', {})
                headers = self.services['gmail']._parse_headers(email_data)
                to_email = headers.get('From', '').split('<')[-1].strip('>')
                
                result = await self.services['gmail'].handle_reply_email({
                    'to': to_email,
                    'body': message.text
                }, message, state)
            else:
                # Send new email
                result = await self.services['gmail'].handle_send_email({
                    'to': data.get('to'),
                    'subject': data.get('subject', 'No Subject'),
                    'body': message.text
                }, message, state)
            
            if result.get('message'):
                await message.answer(result['message'], parse_mode='Markdown')
            
            await state.clear()
        
        @self.dp.message(StateFilter(BotStates.selecting_event))
        async def handle_event_selection(message: types.Message, state: FSMContext):
            """Handle calendar event selection"""
            try:
                text = message.text.strip().lower()
                user_id = message.from_user.id
                
                if any(word in text for word in ['cancel', 'stop', 'back']):
                    await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                    await state.clear()
                    return
                
                data = await state.get_data()
                action = data.get('action')
                
                if 'calendar' not in self.services:
                    await message.answer("❌ Calendar service not available", parse_mode='Markdown')
                    await state.clear()
                    return
                
                calendar_service = self.services['calendar']
                events = calendar_service.search_results.get(user_id, [])
                
                if not events:
                    await message.answer("❌ No events found. Please search again.", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Parse choice
                choice = None
                match = re.search(r'\d+', text)
                if match:
                    choice = int(match.group())
                
                if choice and 1 <= choice <= len(events):
                    selected_event = events[choice - 1]
                    
                    if action == 'delete':
                        result = await calendar_service.delete_event(selected_event['id'])
                        msg = f"✅ Deleted: {selected_event.get('summary')}" if result['success'] else "❌ Failed to delete"
                    elif action == 'update':
                        params = data.get('params', {})
                        update_data = calendar_service._prepare_update_data(selected_event, params)
                        result = await calendar_service.update_event(selected_event['id'], update_data)
                        msg = "✅ Event updated!" if result['success'] else "❌ Failed to update"
                    else:
                        msg = "❌ Unknown action"
                    
                    await message.answer(msg, parse_mode='Markdown')
                    calendar_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    await message.answer(f"Please select 1-{len(events)} or 'cancel'", parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Error in event selection: {e}")
                await message.answer("❌ An error occurred", parse_mode='Markdown')
                await state.clear()
        
        @self.dp.message(StateFilter(BotStates.selecting_file))
        async def handle_file_selection(message: types.Message, state: FSMContext):
            """Handle Drive file selection"""
            try:
                text = message.text.strip().lower()
                user_id = message.from_user.id
                
                if any(word in text for word in ['cancel', 'stop', 'back']):
                    await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                    await state.clear()
                    return
                
                data = await state.get_data()
                action = data.get('action')
                
                if 'drive' not in self.services:
                    await message.answer("❌ Drive service not available", parse_mode='Markdown')
                    await state.clear()
                    return
                
                drive_service = self.services['drive']
                files = drive_service.search_results.get(user_id, [])
                
                if not files:
                    await message.answer("❌ No files found. Please search again.", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Parse choice
                choice = None
                match = re.search(r'\d+', text)
                if match:
                    choice = int(match.group())
                
                if choice and 1 <= choice <= len(files):
                    selected_file = files[choice - 1]
                    file_id = selected_file['id']
                    
                    if action == 'delete':
                        result = await drive_service.delete_file(file_id)
                        msg = "✅ File deleted!" if result['success'] else "❌ Failed to delete"
                    elif action == 'share':
                        email = data.get('email', '')
                        result = await drive_service.share_file(file_id, email)
                        msg = f"✅ Shared with {email}!" if result['success'] else "❌ Failed to share"
                    elif action == 'download':
                        result = await drive_service.handle_download_file({'file_id': file_id}, message, state)
                        msg = result.get('message', 'Download processed')
                    else:
                        msg = "❌ Unknown action"
                    
                    await message.answer(msg, parse_mode='Markdown')
                    drive_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    await message.answer(f"Please select 1-{len(files)} or 'cancel'", parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Error in file selection: {e}")
                await message.answer("❌ An error occurred", parse_mode='Markdown')
                await state.clear()
        
        @self.dp.message(StateFilter(BotStates.selecting_contact))
        async def handle_contact_selection(message: types.Message, state: FSMContext):
            """Handle contact selection"""
            try:
                text = message.text.strip().lower()
                user_id = message.from_user.id
                
                if any(word in text for word in ['cancel', 'stop', 'back']):
                    await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                    await state.clear()
                    return
                
                data = await state.get_data()
                action = data.get('action')
                
                if 'contacts' not in self.services:
                    await message.answer("❌ Contacts service not available", parse_mode='Markdown')
                    await state.clear()
                    return
                
                contacts_service = self.services['contacts']
                contacts = contacts_service.search_results.get(user_id, [])
                
                if not contacts:
                    await message.answer("❌ No contacts found. Please search again.", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Parse choice
                choice = None
                match = re.search(r'\d+', text)
                if match:
                    choice = int(match.group())
                
                if choice and 1 <= choice <= len(contacts):
                    selected_contact = contacts[choice - 1]
                    resource_name = selected_contact.get('resourceName')
                    
                    if action == 'delete':
                        result = await contacts_service.delete_contact(resource_name)
                        msg = "✅ Contact deleted!" if result['success'] else "❌ Failed to delete"
                    elif action == 'update':
                        # Would need additional state for update details
                        msg = "Contact update requires additional information"
                    else:
                        msg = "❌ Unknown action"
                    
                    await message.answer(msg, parse_mode='Markdown')
                    contacts_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    await message.answer(f"Please select 1-{len(contacts)} or 'cancel'", parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Error in contact selection: {e}")
                await message.answer("❌ An error occurred", parse_mode='Markdown')
                await state.clear()
        
        @self.dp.message(StateFilter(BotStates.selecting_task))
        async def handle_task_selection(message: types.Message, state: FSMContext):
            """Handle task selection"""
            try:
                text = message.text.strip().lower()
                user_id = message.from_user.id
                
                if any(word in text for word in ['cancel', 'stop', 'back']):
                    await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                    await state.clear()
                    return
                
                data = await state.get_data()
                action = data.get('action')
                
                if 'tasks' not in self.services:
                    await message.answer("❌ Tasks service not available", parse_mode='Markdown')
                    await state.clear()
                    return
                
                tasks_service = self.services['tasks']
                tasks = tasks_service.search_results.get(user_id, [])
                
                if not tasks:
                    await message.answer("❌ No tasks found. Please list tasks again.", parse_mode='Markdown')
                    await state.clear()
                    return
                
                # Parse choice
                choice = None
                match = re.search(r'\d+', text)
                if match:
                    choice = int(match.group())
                
                if choice and 1 <= choice <= len(tasks):
                    selected_task = tasks[choice - 1]
                    task_id = selected_task['id']
                    
                    if action == 'complete':
                        result = await tasks_service.complete_task(task_id)
                        msg = "✅ Task completed!" if result['success'] else "❌ Failed to complete"
                    elif action == 'delete':
                        result = await tasks_service.delete_task(task_id)
                        msg = "✅ Task deleted!" if result['success'] else "❌ Failed to delete"
                    else:
                        msg = "❌ Unknown action"
                    
                    await message.answer(msg, parse_mode='Markdown')
                    tasks_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    await message.answer(f"Please select 1-{len(tasks)} or 'cancel'", parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Error in task selection: {e}")
                await message.answer("❌ An error occurred", parse_mode='Markdown')
                await state.clear()
        
        @self.dp.message(StateFilter(BotStates.confirming_action))
        async def handle_confirmation(message: types.Message, state: FSMContext):
            """Handle yes/no confirmations"""
            text = message.text.strip().lower()
            
            if any(word in text for word in ['yes', 'y', 'confirm', 'ok', 'sure', 'do it', 'go ahead', 'proceed']):
                data = await state.get_data()
                service_name = data.get('service')
                action = data.get('action')
                params = data.get('params', {})
                
                if service_name in self.services:
                    service = self.services[service_name]
                    
                    # Execute confirmed action
                    result = None
                    if service_name == 'calendar' and action == 'create':
                        result = await service.create_event(params)
                    elif service_name == 'contacts' and action == 'create':
                        result = await service.create_contact(params)
                    elif service_name == 'drive' and action == 'create_folder':
                        result = await service.create_folder(params.get('name'), params.get('parent_id'))
                    elif service_name == 'tasks' and action == 'create':
                        result = await service.create_task(params.get('list_id', '@default'), params)
                    
                    if result:
                        msg = "✅ **Success!**" if result.get('success') else f"❌ **Failed:** {result.get('error', 'Unknown error')}"
                        await message.answer(msg, parse_mode='Markdown')
                
                await state.clear()
                
            elif any(word in text for word in ['no', 'n', 'cancel', 'stop', 'nevermind']):
                await message.answer("❌ **Cancelled**", parse_mode='Markdown')
                await state.clear()
            else:
                await message.answer("Please reply with **'yes'** to confirm or **'no'** to cancel.", parse_mode='Markdown')
        
        # ============================================================
        # GENERAL MESSAGE HANDLER - Must be last!
        # ============================================================
        
        @self.dp.message(F.text)
        async def handle_message(message: types.Message, state: FSMContext):
            """Handle all general text messages"""
            try:
                # Check if we're in a state - if so, warn user
                current_state = await state.get_state()
                if current_state:
                    logger.warning(f"Message in unhandled state {current_state}: {message.text}")
                    await message.answer(
                        "⚠️ **Please complete the current action first**\n"
                        "Type 'cancel' to stop and start over.",
                        parse_mode='Markdown'
                    )
                    return
                
                user_id = message.from_user.id
                await self.bot.send_chat_action(message.chat.id, 'typing')
                
                # Add to conversation history
                self.conversation_manager.add_message(user_id, 'user', message.text)
                context = self.conversation_manager.get_context(user_id)
                
                # Process with Gemini AI
                response = await self.gemini_processor.process(
                    message.text, 
                    user_id, 
                    context, 
                    self.services
                )
                
                # Send AI response if any
                if response.get('text'):
                    # Clean action tags from response
                    clean_text = re.sub(r'\[SERVICE_ACTION:[^\]]+\]', '', response['text']).strip()
                    if clean_text:
                        # Split long messages
                        if len(clean_text) > 4000:
                            parts = [clean_text[i:i+4000] for i in range(0, len(clean_text), 4000)]
                            for part in parts:
                                await message.answer(part)
                        else:
                            await message.answer(clean_text)
                        
                        self.conversation_manager.add_message(user_id, 'assistant', clean_text)
                
                # Execute service actions
                for action in response.get('actions', []):
                    await self.execute_service_action(action, message, state)
                    
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)
                await message.answer(
                    "❌ **An error occurred**\n"
                    "Please try again or type /clear to reset.",
                    parse_mode='Markdown'
                )
                await state.clear()
    
    async def execute_service_action(self, action: Dict, message: types.Message, state: FSMContext):
        """Execute a service action with comprehensive error handling"""
        try:
            service_name = action.get('service', '').lower()
            action_type = action.get('action', '').upper()
            params = action.get('params', {})
            
            logger.info(f"Executing: {service_name}.{action_type} with params: {params}")
            
            if service_name not in self.services:
                if service_name:
                    await message.answer(f"❌ **Service '{service_name}' not available**", parse_mode='Markdown')
                return
            
            service = self.services[service_name]
            
            # Execute the action
            result = await service.handle_action(action_type, params, message, state)
            
            # Check if we entered a state
            current_state = await state.get_state()
            
            # Send result message only if appropriate
            if result and result.get('message') and not current_state:
                # These actions handle their own messaging
                skip_actions = ['DELETE_EMAIL', 'SEARCH_EMAILS', 'LIST_UNREAD']
                if action_type not in skip_actions:
                    await message.answer(result['message'], parse_mode='Markdown')
                    
        except Exception as e:
            logger.error(f"Error executing {service_name}.{action_type}: {e}", exc_info=True)
            error_msg = str(e)[:200]  # Limit error message length
            await message.answer(
                f"❌ **Error with {service_name}:**\n{error_msg}\n\nPlease try again.",
                parse_mode='Markdown'
            )
    
    async def run(self):
        """Run the bot with error recovery"""
        try:
            logger.info("🚀 Starting bot polling...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            # Attempt to restart after error
            await asyncio.sleep(5)
            await self.run()
        finally:
            await self.bot.session.close()