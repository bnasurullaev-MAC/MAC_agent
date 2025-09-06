"""Main entry point for the Google Assistant Bot"""
import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# IMPORTANT: Load .env file FIRST before any other imports or checks
load_dotenv()

# Now import other modules that might use env variables
from core.bot import GoogleAssistantBot
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the bot"""
    print("=" * 60)
    print("🤖 Google Assistant Bot - Multi-Service Integration")
    print("=" * 60)
    
    # Debug: Check if env variables are loaded
    print(f"Bot Token exists: {bool(os.getenv('TELEGRAM_BOT_TOKEN'))}")
    print(f"Gemini Key exists: {bool(os.getenv('GEMINI_API_KEY'))}")
    
    # Check configuration
    if not Config.BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env")
        print(f"Current working directory: {os.getcwd()}")
        print(f".env file exists: {os.path.exists('.env')}")
        return
    
    if not Config.GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not found in .env")
        return
    
    # Rest of your code...
    
    print("\n✅ Configuration loaded")
    print(f"📦 Enabled services: {', '.join(Config.get_enabled_services())}")
    print(f"🔐 Required scopes: {len(Config.get_all_scopes())} scopes")
    
    try:
        # Initialize and run the bot
        bot = GoogleAssistantBot()
        
        print("\n🚀 Starting bot...")
        print("📱 Send /start to your bot to begin")
        
        await bot.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Bot crashed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
