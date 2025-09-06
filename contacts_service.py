"""Google Contacts (People API) service implementation"""
import logging
from typing import Dict, List, Optional
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.base_service import BaseGoogleService
from states.bot_states import BotStates

logger = logging.getLogger(__name__)

class ContactsService(BaseGoogleService):
    """Google Contacts service implementation"""
    
    def __init__(self, auth_manager, config: Dict):
        super().__init__(auth_manager, config)
        self.search_results = {}
    
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle Contacts-specific actions"""
        
        action_handlers = {
            'FIND_CONTACT': self.handle_find_contact,
            'ADD_CONTACT': self.handle_add_contact,
            'UPDATE_CONTACT': self.handle_update_contact,
            'DELETE_CONTACT': self.handle_delete_contact,
            'LIST_CONTACTS': self.handle_list_contacts,
            'GET_CONTACT_DETAILS': self.handle_get_contact_details
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(params, message, state)
        
        return {'success': False, 'message': f'Unknown contacts action: {action}'}
    
    async def handle_find_contact(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle finding a contact"""
        try:
            name = params.get('name', '')
            email = params.get('email', '')
            phone = params.get('phone', '')
            
            if not any([name, email, phone]):
                return {'success': False, 'message': 'Please provide a name, email, or phone number to search'}
            
            # Search contacts
            result = await self.search_contacts(name or email or phone)
            
            if not result['success']:
                return result
            
            contacts = result.get('data', [])
            
            if not contacts:
                return {'success': True, 'message': f'No contacts found for "{name or email or phone}"'}
            
            response = f"👥 **Contact search results:**\n\n"
            
            for i, contact in enumerate(contacts[:10], 1):
                contact_name = self._get_contact_name(contact)
                emails = self._get_contact_emails(contact)
                phones = self._get_contact_phones(contact)
                
                response += f"{i}. **{contact_name}**\n"
                if emails:
                    response += f"   📧 {', '.join(emails)}\n"
                if phones:
                    response += f"   📱 {', '.join(phones)}\n"
                response += "\n"
            
            # Store results
            user_id = message.from_user.id
            self.search_results[user_id] = contacts[:10]
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error finding contact: {e}")
            return {'success': False, 'message': f'Error finding contact: {str(e)}'}
    
    async def handle_add_contact(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle adding a new contact"""
        try:
            name = params.get('name', '')
            email = params.get('email', '')
            phone = params.get('phone', '')
            company = params.get('company', '')
            notes = params.get('notes', '')
            
            if not name:
                return {'success': False, 'message': 'Contact name is required'}
            
            # Create contact data
            contact_data = {
                'names': [{'givenName': name.split()[0], 'familyName': ' '.join(name.split()[1:])}] if len(name.split()) > 1 else [{'givenName': name}]
            }
            
            if email:
                contact_data['emailAddresses'] = [{'value': email}]
            if phone:
                contact_data['phoneNumbers'] = [{'value': phone}]
            if company:
                contact_data['organizations'] = [{'name': company}]
            if notes:
                contact_data['biographies'] = [{'value': notes}]
            
            # Confirm before creating
            confirm_msg = f"""👤 **Confirm Contact Creation:**

**Name:** {name}
{f"**Email:** {email}" if email else ""}
{f"**Phone:** {phone}" if phone else ""}
{f"**Company:** {company}" if company else ""}
{f"**Notes:** {notes}" if notes else ""}

Reply 'yes' to create or 'no' to cancel."""
            
            await state.update_data(
                service='contacts',
                action='create',
                params=contact_data
            )
            await state.set_state(BotStates.confirming_action)
            
            await message.answer(confirm_msg, parse_mode='Markdown')
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error adding contact: {e}")
            return {'success': False, 'message': f'Error adding contact: {str(e)}'}
    
    async def handle_update_contact(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle updating a contact"""
        try:
            contact_id = params.get('contact_id')
            
            if not contact_id:
                # Search first
                search_name = params.get('name', '')
                if not search_name:
                    return {'success': False, 'message': 'Please provide contact name or ID to update'}
                
                search_result = await self.search_contacts(search_name)
                if not search_result['success'] or not search_result.get('data'):
                    return {'success': False, 'message': f'Contact not found: {search_name}'}
                
                contacts = search_result['data']
                
                if len(contacts) == 1:
                    contact_id = contacts[0]['resourceName']
                else:
                    # Multiple matches
                    response = "👥 **Multiple contacts found. Select which to update:**\n\n"
                    
                    for i, contact in enumerate(contacts[:5], 1):
                        name = self._get_contact_name(contact)
                        response += f"{i}. {name}\n"
                    
                    user_id = message.from_user.id
                    self.search_results[user_id] = contacts[:5]
                    
                    await state.update_data(
                        service='contacts',
                        action='update',
                        params=params
                    )
                    await state.set_state(BotStates.selecting_contact)
                    
                    await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                    return {'success': True}
            
            # Update contact
            update_data = {}
            
            if params.get('new_email'):
                update_data['emailAddresses'] = [{'value': params['new_email']}]
            if params.get('new_phone'):
                update_data['phoneNumbers'] = [{'value': params['new_phone']}]
            if params.get('new_company'):
                update_data['organizations'] = [{'name': params['new_company']}]
            
            result = await self.update_contact(contact_id, update_data)
            
            if result['success']:
                return {'success': True, 'message': '✅ Contact updated successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            return {'success': False, 'message': f'Error updating contact: {str(e)}'}
    
    async def handle_delete_contact(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle deleting a contact"""
        try:
            contact_id = params.get('contact_id')
            
            if not contact_id:
                # Search first
                search_name = params.get('name', '')
                if not search_name:
                    return {'success': False, 'message': 'Please provide contact name or ID to delete'}
                
                search_result = await self.search_contacts(search_name)
                if not search_result['success'] or not search_result.get('data'):
                    return {'success': False, 'message': f'Contact not found: {search_name}'}
                
                contacts = search_result['data']
                
                if len(contacts) == 1:
                    contact = contacts[0]
                    # Confirm deletion
                    name = self._get_contact_name(contact)
                    
                    confirm_msg = f"🗑 **Confirm Contact Deletion:**\n\nDelete contact: **{name}**?\n\nReply 'yes' to delete or 'no' to cancel."
                    
                    await state.update_data(
                        service='contacts',
                        action='delete',
                        params={'contact_id': contact['resourceName']}
                    )
                    await state.set_state(BotStates.confirming_action)
                    
                    await message.answer(confirm_msg, parse_mode='Markdown')
                    return {'success': True}
                else:
                    # Multiple matches
                    response = "👥 **Multiple contacts found. Select which to delete:**\n\n"
                    
                    for i, contact in enumerate(contacts[:5], 1):
                        name = self._get_contact_name(contact)
                        response += f"{i}. {name}\n"
                    
                    user_id = message.from_user.id
                    self.search_results[user_id] = contacts[:5]
                    
                    await state.update_data(
                        service='contacts',
                        action='delete'
                    )
                    await state.set_state(BotStates.selecting_contact)
                    
                    await message.answer(response + "\nReply with the number.", parse_mode='Markdown')
                    return {'success': True}
            
            result = await self.delete_contact(contact_id)
            
            if result['success']:
                return {'success': True, 'message': '✅ Contact deleted successfully'}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error deleting contact: {e}")
            return {'success': False, 'message': f'Error deleting contact: {str(e)}'}
    
    async def handle_list_contacts(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle listing contacts"""
        try:
            max_results = min(int(params.get('max_results', 20)), 50)
            
            result = await self.list_contacts(max_results)
            
            if not result['success']:
                return result
            
            contacts = result.get('data', [])
            
            if not contacts:
                return {'success': True, 'message': 'No contacts found'}
            
            response = f"👥 **Your contacts ({len(contacts)}):**\n\n"
            
            for i, contact in enumerate(contacts, 1):
                name = self._get_contact_name(contact)
                emails = self._get_contact_emails(contact)
                
                response += f"{i}. **{name}**"
                if emails:
                    response += f" - {emails[0]}"
                response += "\n"
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error listing contacts: {e}")
            return {'success': False, 'message': f'Error listing contacts: {str(e)}'}
    
    async def handle_get_contact_details(self, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle getting detailed contact information"""
        try:
            contact_id = params.get('contact_id')
            
            if not contact_id:
                return {'success': False, 'message': 'Contact ID required'}
            
            result = await self.get_contact(contact_id)
            
            if not result['success']:
                return result
            
            contact = result['data']
            
            name = self._get_contact_name(contact)
            emails = self._get_contact_emails(contact)
            phones = self._get_contact_phones(contact)
            addresses = self._get_contact_addresses(contact)
            organizations = self._get_contact_organizations(contact)
            birthday = self._get_contact_birthday(contact)
            notes = self._get_contact_notes(contact)
            
            response = f"""👤 **Contact Details:**

**Name:** {name}
{f"**Emails:** {', '.join(emails)}" if emails else ""}
{f"**Phones:** {', '.join(phones)}" if phones else ""}
{f"**Addresses:** {', '.join(addresses)}" if addresses else ""}
{f"**Organizations:** {', '.join(organizations)}" if organizations else ""}
{f"**Birthday:** {birthday}" if birthday else ""}
{f"**Notes:** {notes}" if notes else ""}"""
            
            return {'success': True, 'message': response}
            
        except Exception as e:
            logger.error(f"Error getting contact details: {e}")
            return {'success': False, 'message': f'Error getting contact details: {str(e)}'}
    
    async def search_contacts(self, query: str) -> Dict:
        """Search for contacts"""
        params = {
            'query': query,
            'pageSize': 10,
            'readMask': 'names,emailAddresses,phoneNumbers,organizations'
        }
        
        result = await self.make_api_call('GET', 'people:searchContacts', params=params)
        
        if result['success'] and result.get('data', {}).get('results'):
            contacts = [r['person'] for r in result['data']['results']]
            result['data'] = contacts
        
        return result
    
    async def list_contacts(self, max_results: int = 20) -> Dict:
        """List all contacts"""
        params = {
            'pageSize': max_results,
            'personFields': 'names,emailAddresses,phoneNumbers'
        }
        
        result = await self.make_api_call('GET', 'people/me/connections', params=params)
        
        if result['success'] and result.get('data', {}).get('connections'):
            result['data'] = result['data']['connections']
        
        return result
    
    async def get_contact(self, resource_name: str) -> Dict:
        """Get a specific contact"""
        params = {
            'personFields': 'names,emailAddresses,phoneNumbers,addresses,organizations,birthdays,biographies'
        }
        
        return await self.make_api_call('GET', resource_name, params=params)
    
    async def create_contact(self, contact_data: Dict) -> Dict:
        """Create a new contact"""
        return await self.make_api_call('POST', 'people:createContact', json_data=contact_data)
    
    async def update_contact(self, resource_name: str, update_data: Dict) -> Dict:
        """Update a contact"""
        params = {
            'updatePersonFields': ','.join(update_data.keys())
        }
        
        return await self.make_api_call('PATCH', resource_name, params=params, json_data=update_data)
    
    async def delete_contact(self, resource_name: str) -> Dict:
        """Delete a contact"""
        return await self.make_api_call('DELETE', f'{resource_name}:deleteContact')
    
    def _get_contact_name(self, contact: Dict) -> str:
        """Extract contact name"""
        names = contact.get('names', [])
        if names:
            name = names[0]
            display_name = name.get('displayName')
            if display_name:
                return display_name
            
            given = name.get('givenName', '')
            family = name.get('familyName', '')
            return f"{given} {family}".strip()
        
        return 'Unknown'
    
    def _get_contact_emails(self, contact: Dict) -> List[str]:
        """Extract contact emails"""
        emails = contact.get('emailAddresses', [])
        return [email.get('value', '') for email in emails if email.get('value')]
    
    def _get_contact_phones(self, contact: Dict) -> List[str]:
        """Extract contact phone numbers"""
        phones = contact.get('phoneNumbers', [])
        return [phone.get('value', '') for phone in phones if phone.get('value')]
    
    def _get_contact_addresses(self, contact: Dict) -> List[str]:
        """Extract contact addresses"""
        addresses = contact.get('addresses', [])
        return [addr.get('formattedValue', '') for addr in addresses if addr.get('formattedValue')]
    
    def _get_contact_organizations(self, contact: Dict) -> List[str]:
        """Extract contact organizations"""
        orgs = contact.get('organizations', [])
        return [org.get('name', '') for org in orgs if org.get('name')]
    
    def _get_contact_birthday(self, contact: Dict) -> str:
        """Extract contact birthday"""
        birthdays = contact.get('birthdays', [])
        if birthdays:
            date = birthdays[0].get('date', {})
            return f"{date.get('month', '')}/{date.get('day', '')}/{date.get('year', '')}"
        return ''
    
    def _get_contact_notes(self, contact: Dict) -> str:
        """Extract contact notes"""
        bios = contact.get('biographies', [])
        if bios:
            return bios[0].get('value', '')
        return ''
