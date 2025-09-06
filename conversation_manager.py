"""Manages conversation history and context"""
import json
import logging
from collections import defaultdict, deque
from datetime import datetime
import os
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation history for each user"""
    
    def __init__(self, history_file: str = 'data/conversation_history.json'):
        self.history_file = history_file
        self.max_length = Config.MAX_CONVERSATION_LENGTH
        self.conversations = defaultdict(lambda: deque(maxlen=self.max_length))
        self.load_history()
    
    def load_history(self):
        """Load conversation history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, messages in data.items():
                        self.conversations[int(user_id)] = deque(
                            messages, 
                            maxlen=self.max_length
                        )
                logger.info(f"Loaded conversations for {len(self.conversations)} users")
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
    
    def save_history(self):
        """Save conversation history to file"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            data = {
                str(user_id): list(messages) 
                for user_id, messages in self.conversations.items()
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")
    
    def add_message(self, user_id: int, role: str, content: str):
        """Add a message to user's conversation history"""
        self.conversations[user_id].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        self.save_history()
    
    def get_context(self, user_id: int, num_messages: int = None) -> str:
        """Get formatted conversation context for the user"""
        if num_messages is None:
            num_messages = Config.MAX_CONTEXT_MESSAGES
            
        messages = list(self.conversations[user_id])[-num_messages:]
        
        if not messages:
            return ""
        
        context = "Previous conversation:\n"
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            content = msg['content']
            if len(content) > 500:
                content = content[:500] + "..."
            context += f"{role}: {content}\n"
        
        return context
    
    def clear_history(self, user_id: int):
        """Clear conversation history for a user"""
        if user_id in self.conversations:
            self.conversations[user_id].clear()
            self.save_history()
            logger.info(f"Cleared conversation history for user {user_id}")
    
    def get_last_message(self, user_id: int) -> Optional[Dict]:
        """Get the last message from user's conversation"""
        if user_id in self.conversations and self.conversations[user_id]:
            return self.conversations[user_id][-1]
        return None
