#!/usr/bin/env python3
"""
Voice AI Bot - Entry Point with Bot Selection
Supports: --sales-bot, --health-bot
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config

def print_banner(bot_name: str):
    """Print startup banner"""
    print('AI VoiceBot utilising OpenAI Realtime')
    print('=' * 40)
    print(f'Bot Type: {bot_name}')
    
    # Validate configuration and ensure that .env has been set up correctly
    try:
        Config.validate()
        print('Configuration valid')
        print(f'Company: {Config.COMPANY_NAME}')
        print(f'Server: {Config.SERVER_HOST}:{Config.SERVER_PORT}')
        print(f'Chunk size: {Config.AUDIO_CHUNK_SIZE}ms')
    except ValueError as e:
        print(f'Configuration error: {e}')
        print('Edit .env file with your settings')
        sys.exit(1)

def main():
    """Main entry point with bot selection"""
    
    # Parse CLI arguments
    bot_type = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--sales-bot':
            bot_type = 'sales'
        elif arg == '--health-bot':
            bot_type = 'health'
        else:
            print('Invalid argument')
            print('Usage: python main.py [--sales-bot|--health-bot]')
            print('  --sales-bot    : Start Sales Bot')
            print('  --health-bot   : Start Health Appointment Bot')
            sys.exit(1)
    else:
        print('No bot specified')
        print('Usage: python main.py [--sales-bot|--health-bot]')
        print('  --sales-bot    : Start Sales Bot')
        print('  --health-bot   : Start Health Appointment Bot')
        sys.exit(1)
    
    # Load appropriate bot
    try:
        if bot_type == 'sales':
            print_banner('Sales Bot')
            from core.sales_bot import main as bot_main
        else:  # health
            print_banner('Health Appointment Bot')
            from core.health_appointment_bot import main as bot_main
        
        print()
        print('Starting bot...')
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print()
        print('Bot stopped')
    except Exception as e:
        print()
        print(f'Error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
