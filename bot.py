# =====================================
# FILE: core/bot.py (FINAL CORRECTED VERSION)
# =====================================
"""Core bot implementation with service orchestration"""
import os
import logging
import re
from typing import Dict, List, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from auth.google_auth import GoogleAuthManager
from core.conversation_manager import ConversationManager
from core.gemini_processor import GeminiProcessor
from states.bot_states import BotStates
from config import Config

# Import services
from services.calendar.calendar_service import CalendarService
from services.gmail.gmail_service import GmailService
from services.contacts.contacts_service import ContactsService
from services.drive.drive_service import DriveService
from services.tasks.tasks_service import TasksService

logger = logging.getLogger(__name__)

class GoogleAssistantBot:
    """Main bot class that orchestrates all services"""
    
    def __init__(self):
        self.bot = Bot(token=Config.BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.auth_manager = GoogleAuthManager()
        self.conversation_manager = ConversationManager()
        self.gemini_processor = GeminiProcessor()
        self.services = {}
        self.initialize_services()
        self.setup_handlers()
        logger.info("Bot initialized successfully")
    
    def initialize_services(self):
        service_classes = {
            'calendar': CalendarService, 'gmail': GmailService, 'contacts': ContactsService,
            'drive': DriveService, 'tasks': TasksService
        }
        for name, service_class in service_classes.items():
            config = Config.get_service_config(name)
            if config.get('enabled', False):
                try:
                    self.services[name] = service_class(self.auth_manager, config)
                    logger.info(f"Initialized {name} service")
                except Exception as e:
                    logger.error(f"Failed to initialize {name} service: {e}")
    
    def setup_handlers(self):
        # --- State Handlers (MUST BE REGISTERED BEFORE GENERAL HANDLERS) ---
        @self.dp.message(BotStates.selecting_email)
        async def select_email(message: types.Message, state: FSMContext):
            text = message.text.strip().lower()
            user_id = message.from_user.id
            
            if text in ['cancel', 'no', 'stop', 'nevermind']:
                await message.answer("Action cancelled.")
                await state.clear()
                return

            try:
                data = await state.get_data()
                action = data.get('action')
                if 'gmail' not in self.services or user_id not in self.services['gmail'].search_results:
                    await message.answer("Your session seems to have expired. Please start your search again.")
                    await state.clear()
                    return
                    
                gmail_service = self.services['gmail']
                emails = gmail_service.search_results.get(user_id, [])
                choice = None

                if len(emails) == 1 and any(word in text for word in ['yes', 'y', 'ok', 'confirm', 'delete', 'sure', 'do it']):
                    choice = 1
                
                if choice is None:
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        choice = int(numbers[0])

                if choice and 1 <= choice <= len(emails):
                    await self.bot.send_chat_action(message.chat.id, 'typing')
                    selected_email = emails[choice - 1]
                    email_id = selected_email.get('id')
                    
                    result = {}
                    if action == 'delete':
                        result = await gmail_service.perform_actual_delete(email_id)
                    elif action == 'read':
                        result = await gmail_service.handle_read_email({'email_id': email_id}, message, state)
                    
                    if result.get('message'):
                        await message.answer(result['message'], parse_mode='Markdown')

                    gmail_service.search_results.pop(user_id, None)
                    await state.clear()
                else:
                    await message.answer(f"Sorry, I didn't understand that. Please reply with a number (from 1 to {len(emails)}) or 'cancel'.")

            except Exception as e:
                logger.error(f"Critical error in select_email state: {e}")
                await message.answer("A critical error occurred. Resetting conversation.")
                await state.clear()

        # Add other state handlers like confirming_send here...

        # --- Command and General Handlers ---
        @self.dp.message(Command("start", "help", "clear"))
        async def handle_commands(message: types.Message, state: FSMContext):
            await state.clear()
            if message.text.startswith("/start"):
                 await message.answer("Welcome to the Google Assistant Bot! How can I help you?")
            elif message.text.startswith("/help"):
                await message.answer("You can ask me to manage your Gmail, Calendar, and more. For example: 'show my unread emails'.")
            elif message.text.startswith("/clear"):
                self.conversation_manager.clear_history(message.from_user.id)
                await message.answer("Conversation history cleared.")

        # --- MAIN MESSAGE HANDLER (WITH CRITICAL FIX) ---
        @self.dp.message(F.text, StateFilter(None))
        async def handle_message(message: types.Message, state: FSMContext):
            user_id = message.from_user.id
            await self.bot.send_chat_action(message.chat.id, 'typing')
            
            self.conversation_manager.add_message(user_id, 'user', message.text)
            context = self.conversation_manager.get_context(user_id)
            
            response = await self.gemini_processor.process(message.text, user_id, context, self.services)
            
            if response.get('text'):
                clean_text = re.sub(r'\[SERVICE_ACTION:[^\]]+\]', '', response['text']).strip()
                if clean_text:
                    await message.answer(clean_text)
                    self.conversation_manager.add_message(user_id, 'assistant', clean_text)
            
            for action in response.get('actions', []):
                await self.execute_service_action(action, message, state)
    
    async def execute_service_action(self, action: Dict, message: types.Message, state: FSMContext):
        service_name = action.get('service', '').lower()
        if service_name not in self.services:
            if service_name: await message.answer(f"❌ Service '{service_name}' is not available")
            return
        
        try:
            service = self.services[service_name]
            result = await service.handle_action(action.get('action'), action.get('params', {}), message, state)
            if result and result.get('message'):
                await message.answer(result['message'], parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error executing {service_name} action: {e}")
            await message.answer(f"❌ Error with {service_name}: {str(e)}")
    
    async def run(self):
        try:
            logger.info("Starting bot polling...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
        finally:
            await self.bot.session.close()