"""Date and time parsing utilities"""
import re
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
import pytz

logger = logging.getLogger(__name__)

class DateParser:
    """Parse dates, times, and durations from natural language"""
    
    def __init__(self, timezone=None):
        self.timezone = timezone or pytz.UTC
    
    def parse_date(self, date_str: str) -> datetime:
        """Parse date from string"""
        date_lower = date_str.lower()
        now = datetime.now(self.timezone)
        
        # Handle relative dates
        if 'today' in date_lower:
            return now
        elif 'tomorrow' in date_lower:
            return now + timedelta(days=1)
        elif 'yesterday' in date_lower:
            return now - timedelta(days=1)
        
        # Handle "in X days"
        in_days = re.search(r'in\s+(\d+)\s+days?', date_lower)
        if in_days:
            days = int(in_days.group(1))
            return now + timedelta(days=days)
        
        # Handle "next week"
        if 'next week' in date_lower:
            return now + timedelta(weeks=1)
        
        # Handle day names
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_num in days.items():
            if day_name in date_lower:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                if 'next' in date_lower:
                    days_ahead += 7
                return now + timedelta(days=days_ahead)
        
        # Handle month and day
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for month_name, month_num in months.items():
            if month_name in date_lower:
                # Extract day
                day_match = re.search(r'(\d{1,2})', date_str)
                if day_match:
                    day = int(day_match.group(1))
                    year = now.year
                    
                    try:
                        result = self.timezone.localize(datetime(year, month_num, day))
                        # If date is in the past, assume next year
                        if result.date() < now.date():
                            result = self.timezone.localize(datetime(year + 1, month_num, day))
                        return result
                    except ValueError:
                        pass
        
        # Handle MM/DD/YYYY or DD/MM/YYYY
        date_pattern = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', date_str)
        if date_pattern:
            month = int(date_pattern.group(1))
            day = int(date_pattern.group(2))
            year = int(date_pattern.group(3)) if date_pattern.group(3) else now.year
            
            # Handle 2-digit year
            if year < 100:
                year += 2000
            
            try:
                return self.timezone.localize(datetime(year, month, day))
            except ValueError:
                # Try DD/MM format
                try:
                    return self.timezone.localize(datetime(year, day, month))
                except ValueError:
                    pass
        
        # Default to today
        return now
    
    def parse_time(self, time_str: str) -> Tuple[int, int]:
        """Parse time string and return hour, minute"""
        time_lower = time_str.lower()
        
        # Default time
        hour, minute = 12, 0
        
        # Handle special cases
        if 'noon' in time_lower or 'midday' in time_lower:
            return 12, 0
        elif 'midnight' in time_lower:
            return 0, 0
        elif 'morning' in time_lower:
            return 9, 0
        elif 'afternoon' in time_lower:
            return 14, 0
        elif 'evening' in time_lower:
            return 18, 0
        elif 'night' in time_lower:
            return 20, 0
        
        # Parse time patterns (e.g., "3:30 PM", "15:30", "3pm")
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)
            
            # Handle AM/PM
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            elif not period and hour < 8:  # Assume PM for small numbers without AM/PM
                hour += 12
        
        return hour, minute
    
    def parse_duration(self, text: str) -> float:
        """Parse duration from text - returns hours as float"""
        text_lower = text.lower()
        
        # Check for specific patterns
        patterns = [
            (r'(\d+\.?\d*)\s*hours?', 1),           # "2 hours", "1.5 hour"
            (r'(\d+\.?\d*)\s*hrs?', 1),             # "2 hrs", "1.5 hr"
            (r'(\d+)\s*minutes?', 1/60),            # "30 minutes" -> 0.5 hours
            (r'(\d+)\s*mins?', 1/60),               # "30 mins" -> 0.5 hours
            (r'half\s*(?:an\s*)?hour', 0.5),        # "half hour", "half an hour"
            (r'(\d+)\s*days?', 24),                 # "2 days" -> 48 hours
            (r'all\s*day', 24),                     # "all day" -> 24 hours
        ]
        
        for pattern, multiplier in patterns:
            if isinstance(multiplier, (int, float)):
                match = re.search(pattern, text_lower)
                if match:
                    if pattern in [r'half\s*(?:an\s*)?hour', r'all\s*day']:
                        return multiplier
                    value = float(match.group(1))
                    return value * multiplier
        
        # Default to 1 hour if no duration specified
        return 1.0
    
    def parse_datetime(self, text: str) -> Optional[datetime]:
        """Parse both date and time from text"""
        # Look for date
        date = self.parse_date(text)
        
        # Look for time
        hour, minute = self.parse_time(text)
        
        # Combine
        result = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if not result.tzinfo:
            result = self.timezone.localize(result)
        
        return result
    
    def format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time (e.g., 'in 2 hours', 'tomorrow')"""
        now = datetime.now(self.timezone)
        
        if not dt.tzinfo:
            dt = self.timezone.localize(dt)
        
        diff = dt - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if days == 0:
            if hours == 0:
                if minutes < 5:
                    return "now"
                return f"in {minutes} minutes"
            elif hours == 1:
                return "in 1 hour"
            else:
                return f"in {hours} hours"
        elif days == 1:
            return "tomorrow"
        elif days == -1:
            return "yesterday"
        elif 0 < days < 7:
            return f"in {days} days"
        elif days == 7:
            return "next week"
        elif days > 7:
            return dt.strftime('%B %d')
        else:
            return f"{abs(days)} days ago"
