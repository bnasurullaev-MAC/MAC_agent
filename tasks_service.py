"""Google Tasks service implementation"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates
from utils.date_parser import DateParser
from config import Config

logger = logging.getLogger(__name__)

class TasksService(BaseGoogleService):
    """Google Tasks service implementation"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.date_parser = DateParser(Config.DEFAULT_TIMEZONE)
        self.task_lists = {}
        self.search_results = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle Tasks-specific actions"""
        
        action_handlers = {
            'ADD_TASK': self.handle_add_task,
            'LIST_TASKS': self.handle_list_tasks,
            'COMPLETE_TASK': self.handle_complete_task,
            'UPDATE_TASK': self.handle_update_task,
            'DELETE_TASK': self.handle_delete_task,
            'CREATE_LIST': self.handle_create_list,
            'DELETE_LIST': self.handle_delete_list
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'Unknown tasks action: {action}'}
    
    async def handle_add_task(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle adding a new task"""
        try:
            title = params.get('title', 'New Task')
            notes = params.get('notes', '')
            due_date = params.get('due_date', '')
            list_name = params.get('list', '')
            
            # Parse due date if provided
            due = None
            if due_date:
                due = self.date_parser.parse_date(due_date)
                due_str = due.strftime('%Y-%m-%dT00:00:00.000Z')
            else:
                due_str = None
            
            # Get or create task list
            list_id = await self._get_or_create_list(list_name)
            
            # Confirm task creation
            confirm_msg = f"""✅ **Confirm Task Creation:**

**Task:** {title}
{f"**Notes:** {notes}" if notes else ""}
{f"**Due Date:** {due.strftime('%B %d, %Y')}" if due else ""}
**List:** {list_name or 'Default'}

Reply 'yes' to create or 'no' to cancel."""
            
            await state.update_data(
                service='tasks',
                action='create',
                params={
                    'title': title,
                    'notes': notes,
                    'due': due_str,
                    'list_id': list_id
                }
            )
            await state.set_state(BotStates.confirming_action)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            return {'success': False, 'message': f'Error adding task: {str(e)}'}
    
    async def handle_list_tasks(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle listing tasks"""
        try:
            list_name = params.get('list', '')
            show_completed = params.get('show_completed', False)
            show_hidden = params.get('show_hidden', False)
            
            # Get task list
            list_id = await self._get_list_id(list_name)
            
            if not list_id:
                return {'success': False, 'message': f'Task list not found: {list_name or "Default"}'}
            
            # Get tasks
            result = await self.list_tasks(list_id, show_completed, show_hidden)
            
            if not result['success']:
                return result
            
            tasks = result.get('data', [])
            
            if not tasks:
                return {'success': True, 'message': f'No tasks found in {list_name or "Default"} list'}
            
            response = f"✅ **Tasks in {list_name or 'Default'} list:**\n\n"
            
            incomplete_tasks = [t for t in tasks if t.get('status') != 'completed']
            completed_tasks = [t for t in tasks if t.get('status') == 'completed']
            
            if incomplete_tasks:
                response += "**📝 To Do:**\n"
                for i, task in enumerate(incomplete_tasks, 1):
                    title = task.get('title', 'Untitled')
                    due = task.get('due', '')
                    if due:
                        due_date = datetime.fromisoformat(due.replace('Z', '+00:00'))
                        due_str = f" (Due: {due_date.strftime('%b %d')})"
                    else:
                        due_str = ""
                    
                    response += f"{i}. {title}{due_str}\n"
            
            if show_completed and completed_tasks:
                response += "\n**✅ Completed:**\n"
                for task in completed_tasks[:5]:
                    title = task.get('title', 'Untitled')
                    response += f"• ~~{title}~~\n"
            
            # Store results for potential actions
            user_id = message.from_user.id
            self.search_results[user_id] = incomplete_tasks
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return {'success': False, 'message': f'Error listing tasks: {str(e)}'}
    
    async def handle_complete_task(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle marking task as complete"""
        try:
            task_id = params.get('task_id')
            task_title = params.get('title', '')
            
            if not task_id:
                # Search by title
                if not task_title:
                    # Show list of tasks to complete
                    user_id = message.from_user.id
                    if user_id in self.search_results:
                        tasks = self.search_results[user_id]
                        response = "✅ **Select task to complete:**\n\n"
                        
                        for i, task in enumerate(tasks[:10], 1):
                            response += f"{i}. {task.get('title', 'Untitled')}\n"
                        
                        await state.update_data(
                            service='tasks',
                            action='complete'
                        )
                        await state.set_state(BotStates.selecting_task)
                        
                        await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                        return {'success': True}
                    else:
                        return {'success': False, 'message': 'Please list tasks first'}
                
                # Find task by title
                result = await self.find_task_by_title(task_title)
                if not result:
                    return {'success': False, 'message': f'Task not found: {task_title}'}
                
                task_id = result['id']
            
            # Complete the task
            result = await self.complete_task(task_id)
            
            if result['success']:
                return {'success': True, 'message': '✅ Task marked as complete!'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return {'success': False, 'message': f'Error completing task: {str(e)}'}
    
    async def handle_update_task(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle updating a task"""
        try:
            task_id = params.get('task_id')
            new_title = params.get('new_title')
            new_notes = params.get('new_notes')
            new_due = params.get('new_due')
            
            if not task_id:
                return {'success': False, 'message': 'Task ID or title required for update'}
            
            update_data = {}
            if new_title:
                update_data['title'] = new_title
            if new_notes:
                update_data['notes'] = new_notes
            if new_due:
                due_date = self.date_parser.parse_date(new_due)
                update_data['due'] = due_date.strftime('%Y-%m-%dT00:00:00.000Z')
            
            result = await self.update_task(task_id, update_data)
            
            if result['success']:
                return {'success': True, 'message': '✅ Task updated successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return {'success': False, 'message': f'Error updating task: {str(e)}'}
    
    async def handle_delete_task(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle deleting a task"""
        try:
            task_id = params.get('task_id')
            task_title = params.get('title', '')
            
            if not task_id:
                # Search by title
                if not task_title:
                    # Show list of tasks to delete
                    user_id = message.from_user.id
                    if user_id in self.search_results:
                        tasks = self.search_results[user_id]
                        response = "🗑 **Select task to delete:**\n\n"
                        
                        for i, task in enumerate(tasks[:10], 1):
                            response += f"{i}. {task.get('title', 'Untitled')}\n"
                        
                        await state.update_data(
                            service='tasks',
                            action='delete'
                        )
                        await state.set_state(BotStates.selecting_task)
                        
                        await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                        return {'success': True}
                    else:
                        return {'success': False, 'message': 'Please list tasks first'}
                
                # Find task by title
                result = await self.find_task_by_title(task_title)
                if not result:
                    return {'success': False, 'message': f'Task not found: {task_title}'}
                
                task = result
                
                # Confirm deletion
                confirm_msg = f"🗑 **Confirm Task Deletion:**\n\nDelete task: **{task.get('title', 'Untitled')}**?\n\nReply 'yes' to delete or 'no' to cancel."
                
                await state.update_data(
                    service='tasks',
                    action='delete_confirm',
                    params={'task_id': task['id']}
                )
                await state.set_state(BotStates.confirming_action)
                
                await message.answer(confirm_msg, parse_mode='Markdown')
                return {'success': True}
            
            result = await self.delete_task(task_id)
            
            if result['success']:
                return {'success': True, 'message': '✅ Task deleted successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            return {'success': False, 'message': f'Error deleting task: {str(e)}'}
    
    async def handle_create_list(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle creating a new task list"""
        try:
            list_name = params.get('name', 'New List')
            
            result = await self.create_task_list(list_name)
            
            if result['success']:
                return {'success': True, 'message': f'✅ Task list "{list_name}" created successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error creating task list: {e}")
            return {'success': False, 'message': f'Error creating task list: {str(e)}'}
    
    async def handle_delete_list(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle deleting a task list"""
        try:
            list_name = params.get('name', '')
            
            if not list_name:
                return {'success': False, 'message': 'List name is required'}
            
            list_id = await self._get_list_id(list_name)
            
            if not list_id:
                return {'success': False, 'message': f'Task list not found: {list_name}'}
            
            result = await self.delete_task_list(list_id)
            
            if result['success']:
                return {'success': True, 'message': f'✅ Task list "{list_name}" deleted successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error deleting task list: {e}")
            return {'success': False, 'message': f'Error deleting task list: {str(e)}'}
    
    async def create_task(self, list_id: str, task_data: Dict) -> Dict:
        """Create a new task"""
        return await self.make_api_call('POST', f'lists/{list_id}/tasks', json_data=task_data)
    
    async def list_tasks(self, list_id: str, show_completed: bool = False, show_hidden: bool = False) -> Dict:
        """List tasks in a task list"""
        params = {
            'showCompleted': show_completed,
            'showHidden': show_hidden,
            'maxResults': 100
        }
        
        return await self.make_api_call('GET', f'lists/{list_id}/tasks', params=params)
    
    async def get_task(self, list_id: str, task_id: str) -> Dict:
        """Get a specific task"""
        return await self.make_api_call('GET', f'lists/{list_id}/tasks/{task_id}')
    
    async def update_task(self, task_id: str, update_data: Dict, list_id: str = '@default') -> Dict:
        """Update a task"""
        return await self.make_api_call('PATCH', f'lists/{list_id}/tasks/{task_id}', json_data=update_data)
    
    async def complete_task(self, task_id: str, list_id: str = '@default') -> Dict:
        """Mark task as complete"""
        update_data = {'status': 'completed'}
        return await self.update_task(task_id, update_data, list_id)
    
    async def delete_task(self, task_id: str, list_id: str = '@default') -> Dict:
        """Delete a task"""
        return await self.make_api_call('DELETE', f'lists/{list_id}/tasks/{task_id}')
    
    async def list_task_lists(self) -> Dict:
        """List all task lists"""
        return await self.make_api_call('GET', 'users/@me/lists')
    
    async def create_task_list(self, title: str) -> Dict:
        """Create a new task list"""
        return await self.make_api_call('POST', 'users/@me/lists', json_data={'title': title})
    
    async def delete_task_list(self, list_id: str) -> Dict:
        """Delete a task list"""
        return await self.make_api_call('DELETE', f'users/@me/lists/{list_id}')
    
    async def find_task_by_title(self, title: str, list_id: str = '@default') -> Optional[Dict]:
        """Find a task by title"""
        result = await self.list_tasks(list_id)
        
        if result['success'] and result.get('data'):
            tasks = result['data'].get('items', [])
            for task in tasks:
                if title.lower() in task.get('title', '').lower():
                    return task
        
        return None
    
    async def _get_list_id(self, list_name: str) -> Optional[str]:
        """Get task list ID by name"""
        if not list_name:
            return '@default'
        
        # Check cache
        if list_name in self.task_lists:
            return self.task_lists[list_name]
        
        # Get all lists
        result = await self
        result = await self.list_task_lists()
        
        if result['success'] and result.get('data'):
            lists = result['data'].get('items', [])
            for task_list in lists:
                self.task_lists[task_list['title']] = task_list['id']
                if task_list['title'].lower() == list_name.lower():
                    return task_list['id']
        
        return None
    
    async def _get_or_create_list(self, list_name: str) -> str:
        """Get or create task list"""
        if not list_name:
            return '@default'
        
        list_id = await self._get_list_id(list_name)
        
        if not list_id:
            # Create new list
            result = await self.create_task_list(list_name)
            if result['success']:
                list_id = result['data']['id']
                self.task_lists[list_name] = list_id
            else:
                list_id = '@default'
        
        return list_id

