"""Google Drive service implementation"""
import logging
import os
from typing import Dict, List, Optional
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

class DriveService(BaseGoogleService):
    """Google Drive service implementation"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.search_results = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle Drive-specific actions"""
        
        action_handlers = {
            'SEARCH_FILES': self.handle_search_files,
            'CREATE_FOLDER': self.handle_create_folder,
            'UPLOAD_FILE': self.handle_upload_file,
            'DOWNLOAD_FILE': self.handle_download_file,
            'SHARE_FILE': self.handle_share_file,
            'DELETE_FILE': self.handle_delete_file,
            'MOVE_FILE': self.handle_move_file,
            'RENAME_FILE': self.handle_rename_file,
            'LIST_RECENT': self.handle_list_recent
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'Unknown Drive action: {action}'}
    
    async def handle_search_files(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file search"""
        try:
            query = params.get('query', '')
            file_type = params.get('file_type', '')
            folder_id = params.get('folder_id', '')
            
            # Build search query
            drive_query = self._build_search_query(query, file_type, folder_id)
            
            result = await self.search_files(drive_query)
            
            if not result['success']:
                return result
            
            files = result.get('data', [])
            
            if not files:
                return {'success': True, 'message': f'No files found for "{query}"'}
            
            response = f"📁 **Search results for '{query}':**\n\n"
            
            for i, file in enumerate(files[:15], 1):
                file_name = file.get('name', 'Untitled')
                file_type = self._get_file_type_emoji(file.get('mimeType', ''))
                modified = file.get('modifiedTime', '')[:10] if file.get('modifiedTime') else ''
                size = self._format_file_size(file.get('size', 0))
                
                response += f"{i}. {file_type} **{file_name}**\n"
                response += f"   Modified: {modified} | Size: {size}\n\n"
            
            # Store results
            user_id = message.from_user.id
            self.search_results[user_id] = files[:15]
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {'success': False, 'message': f'Error searching files: {str(e)}'}
    
    async def handle_create_folder(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle folder creation"""
        try:
            folder_name = params.get('name', 'New Folder')
            parent_id = params.get('parent_id', '')
            
            # Confirm creation
            confirm_msg = f"""📁 **Confirm Folder Creation:**

**Name:** {folder_name}
{f"**Parent Folder ID:** {parent_id}" if parent_id else "**Location:** My Drive (root)"}

Reply 'yes' to create or 'no' to cancel."""
            
            await state.update_data(
                service='drive',
                action='create_folder',
                params={'name': folder_name, 'parent_id': parent_id}
            )
            await state.set_state(BotStates.confirming_action)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {'success': False, 'message': f'Error creating folder: {str(e)}'}
    
    async def handle_share_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file sharing"""
        try:
            file_id = params.get('file_id')
            email = params.get('email', '')
            permission_type = params.get('type', 'user')  # user, group, domain, anyone
            role = params.get('role', 'reader')  # owner, organizer, fileOrganizer, writer, commenter, reader
            
            if not file_id:
                # Try to get from search results
                user_id = message.from_user.id
                if user_id in self.search_results:
                    files = self.search_results[user_id]
                    response = "📤 **Select file to share:**\n\n"
                    
                    for i, file in enumerate(files[:5], 1):
                        response += f"{i}. {file.get('name', 'Untitled')}\n"
                    
                    await state.update_data(
                        service='drive',
                        action='share',
                        params={'email': email, 'role': role}
                    )
                    await state.set_state(BotStates.selecting_file)
                    
                    await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                    return {'success': True}
                else:
                    return {'success': False, 'message': 'Please search for files first'}
            
            # Confirm sharing
            confirm_msg = f"""📤 **Confirm File Sharing:**

**File ID:** {file_id}
**Share with:** {email if email else 'Anyone with link'}
**Permission:** {role}

Reply 'yes' to share or 'no' to cancel."""
            
            await state.update_data(
                service='drive',
                action='share_confirm',
                params={
                    'file_id': file_id,
                    'email': email,
                    'type': permission_type,
                    'role': role
                }
            )
            await state.set_state(BotStates.confirming_share)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error sharing file: {e}")
            return {'success': False, 'message': f'Error sharing file: {str(e)}'}
    
    async def handle_delete_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file deletion"""
        try:
            file_id = params.get('file_id')
            
            if not file_id:
                # Search first
                search_query = params.get('name', '')
                if not search_query:
                    return {'success': False, 'message': 'Please provide file name or ID to delete'}
                
                search_result = await self.search_files(f"name contains '{search_query}'")
                if not search_result['success'] or not search_result.get('data'):
                    return {'success': False, 'message': f'File not found: {search_query}'}
                
                files = search_result['data']
                
                if len(files) == 1:
                    file = files[0]
                    # Confirm deletion
                    confirm_msg = f"🗑 **Confirm File Deletion:**\n\nDelete file: **{file.get('name', 'Untitled')}**?\n\nReply 'yes' to delete or 'no' to cancel."
                    
                    await state.update_data(
                        service='drive',
                        action='delete',
                        params={'file_id': file['id']}
                    )
                    await state.set_state(BotStates.confirming_action)
                    
                    await message.answer(confirm_msg, parse_mode='Markdown')
                    return {'success': True}
                else:
                    # Multiple matches
                    response = "🗑 **Multiple files found. Select which to delete:**\n\n"
                    
                    for i, file in enumerate(files[:5], 1):
                        response += f"{i}. {file.get('name', 'Untitled')}\n"
                    
                    user_id = message.from_user.id
                    self.search_results[user_id] = files[:5]
                    
                    await state.update_data(
                        service='drive',
                        action='delete'
                    )
                    await state.set_state(BotStates.selecting_file)
                    
                    await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                    return {'success': True}
            
            result = await self.delete_file(file_id)
            
            if result['success']:
                return {'success': True, 'message': '✅ File deleted successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {'success': False, 'message': f'Error deleting file: {str(e)}'}
    
    async def handle_rename_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file renaming"""
        try:
            file_id = params.get('file_id')
            new_name = params.get('new_name', '')
            
            if not new_name:
                return {'success': False, 'message': 'New name is required'}
            
            if not file_id:
                return {'success': False, 'message': 'File ID is required'}
            
            result = await self.rename_file(file_id, new_name)
            
            if result['success']:
                return {'success': True, 'message': f'✅ File renamed to "{new_name}"'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return {'success': False, 'message': f'Error renaming file: {str(e)}'}
    
    async def handle_move_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file moving"""
        try:
            file_id = params.get('file_id')
            folder_id = params.get('folder_id')
            
            if not file_id or not folder_id:
                return {'success': False, 'message': 'Both file ID and destination folder ID are required'}
            
            result = await self.move_file(file_id, folder_id)
            
            if result['success']:
                return {'success': True, 'message': '✅ File moved successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return {'success': False, 'message': f'Error moving file: {str(e)}'}
    
    async def handle_list_recent(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle listing recent files"""
        try:
            max_results = min(int(params.get('max_results', 10)), 20)
            
            result = await self.list_recent_files(max_results)
            
            if not result['success']:
                return result
            
            files = result.get('data', [])
            
            if not files:
                return {'success': True, 'message': 'No recent files found'}
            
            response = f"📁 **Recent files:**\n\n"
            
            for i, file in enumerate(files, 1):
                file_name = file.get('name', 'Untitled')
                file_type = self._get_file_type_emoji(file.get('mimeType', ''))
                modified = file.get('modifiedTime', '')[:16] if file.get('modifiedTime') else ''
                
                response += f"{i}. {file_type} **{file_name}**\n"
                response += f"   Modified: {modified}\n\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error listing recent files: {e}")
            return {'success': False, 'message': f'Error listing recent files: {str(e)}'}
    
    async def handle_upload_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file upload (placeholder - actual implementation would need file handling)"""
        return {'success': True, 'message': 'File upload requires sending the actual file to the bot. Please send the file you want to upload.'}
    
    async def handle_download_file(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle file download"""
        try:
            file_id = params.get('file_id')
            
            if not file_id:
                return {'success': False, 'message': 'File ID is required'}
            
            # Get file metadata
            result = await self.get_file_metadata(file_id)
            
            if result['success']:
                file_data = result['data']
                web_link = file_data.get('webViewLink', '')
                download_link = file_data.get('webContentLink', '')
                
                response = f"""📥 **File Download Links:**

**File:** {file_data.get('name', 'Unknown')}
**Size:** {self._format_file_size(file_data.get('size', 0))}

**View Online:** {web_link}
{f"**Direct Download:** {download_link}" if download_link else ""}"""
                
                return {'success': True, 'message': response}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return {'success': False, 'message': f'Error downloading file: {str(e)}'}
    
    async def search_files(self, query: str, max_results: int = 15) -> Dict:
        """Search for files"""
        params = {
            'q': query,
            'pageSize': max_results,
            'fields': 'files(id,name,mimeType,size,modifiedTime,parents,webViewLink,webContentLink)'
        }
        
        return await self.make_api_call('GET', 'files', params=params)
    
    async def create_folder(self, name: str, parent_id: str = None) -> Dict:
        """Create a folder"""
        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            metadata['parents'] = [parent_id]
        
        return await self.make_api_call('POST', 'files', json_data=metadata)
    
    async def share_file(self, file_id: str, email: str, role: str = 'reader', type: str = 'user') -> Dict:
        """Share a file"""
        permission = {
            'type': type,
            'role': role
        }
        
        if email and type == 'user':
            permission['emailAddress'] = email
        
        return await self.make_api_call('POST', f'files/{file_id}/permissions', json_data=permission)
    
    async def delete_file(self, file_id: str) -> Dict:
        """Delete a file"""
        return await self.make_api_call('DELETE', f'files/{file_id}')
    
    async def rename_file(self, file_id: str, new_name: str) -> Dict:
        """Rename a file"""
        metadata = {'name': new_name}
        return await self.make_api_call('PATCH', f'files/{file_id}', json_data=metadata)
    
    async def move_file(self, file_id: str, folder_id: str) -> Dict:
        """Move a file to another folder"""
        # First get current parents
        file_result = await self.get_file_metadata(file_id)
        
        if not file_result['success']:
            return file_result
        
        current_parents = ','.join(file_result['data'].get('parents', []))
        
        params = {
            'addParents': folder_id,
            'removeParents': current_parents
        }
        
        return await self.make_api_call('PATCH', f'files/{file_id}', params=params)
    
    async def get_file_metadata(self, file_id: str) -> Dict:
        """Get file metadata"""
        params = {
            'fields': 'id,name,mimeType,size,modifiedTime,parents,webViewLink,webContentLink'
        }
        
        return await self.make_api_call('GET', f'files/{file_id}', params=params)
    
    async def list_recent_files(self, max_results: int = 10) -> Dict:
        """List recently modified files"""
        params = {
            'pageSize': max_results,
            'orderBy': 'modifiedTime desc',
            'fields': 'files(id,name,mimeType,size,modifiedTime)'
        }
        
        return await self.make_api_call('GET', 'files', params=params)
    
    def _build_search_query(self, text_query: str, file_type: str = '', folder_id: str = '') -> str:
        """Build Drive search query"""
        query_parts = []
        
        if text_query:
            query_parts.append(f"name contains '{text_query}'")
        
        if file_type:
            mime_types = {
                'document': 'application/vnd.google-apps.document',
                'spreadsheet': 'application/vnd.google-apps.spreadsheet',
                'presentation': 'application/vnd.google-apps.presentation',
                'folder': 'application/vnd.google-apps.folder',
                'pdf': 'application/pdf',
                'image': 'mimeType contains "image/"',
                'video': 'mimeType contains "video/"'
            }
            
            if file_type in mime_types:
                query_parts.append(f"mimeType = '{mime_types[file_type]}'")
        
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        
        # Exclude trashed files
        query_parts.append("trashed = false")
        
        return ' and '.join(query_parts)
    
    def _get_file_type_emoji(self, mime_type: str) -> str:
        """Get emoji for file type"""
        if 'folder' in mime_type:
            return '📁'
        elif 'document' in mime_type:
            return '📄'
        elif 'spreadsheet' in mime_type:
            return '📊'
        elif 'presentation' in mime_type:
            return '📑'
        elif 'pdf' in mime_type:
            return '📕'
        elif 'image' in mime_type:
            return '🖼'
        elif 'video' in mime_type:
            return '🎬'
        elif 'audio' in mime_type:
            return '🎵'
        else:
            return '📎'
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size"""
        if not size_bytes:
            return 'N/A'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} TB"
