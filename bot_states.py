"""FSM states for the bot"""
from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    """All bot states"""
    
    # General states
    confirming_action = State()
    selecting_option = State()
    
    # Calendar states
    creating_event = State()
    updating_event = State()
    selecting_event = State()
    
    # Gmail states
    composing_email = State()
    selecting_email = State()
    confirming_send = State()
    
    # Contacts states
    adding_contact = State()
    selecting_contact = State()
    editing_contact = State()
    
    # Drive states
    selecting_file = State()
    uploading_file = State()
    confirming_share = State()
    
    # Tasks states
    adding_task = State()
    selecting_task = State()
    editing_task = State()
