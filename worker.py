import os
import time
import threading
import schedule
import sys
from database_setup import setup_database

# Ensure database is set up
print("Initializing database for worker...")
if not setup_database():
    print("Error: Database setup failed. Exiting worker.")
    sys.exit(1)

# Import after successful database setup
from settings_bot import SettingsBot
from monitors.global_monitor import GlobalMonitor
from monitors.au_monitor import AUMonitor

# Load environment variables
SETTINGS_BOT_TOKEN = os.environ.get("SETTINGS_BOT_TOKEN")
NOTIFICATION_BOT_TOKEN = os.environ.get("NOTIFICATION_BOT_TOKEN")

def run_settings_bot():
    """Run the settings bot"""
    if SETTINGS_BOT_TOKEN:
        try:
            print("Starting settings bot...")
            bot = SettingsBot(SETTINGS_BOT_TOKEN)
            bot.run()
        except Exception as e:
            print(f"Error running settings bot: {e}")
    else:
        print("Settings bot token not found!")

def run_monitors():
    """Run the monitoring scripts"""
    if NOTIFICATION_BOT_TOKEN:
        try:
            print("Starting monitoring...")
            global_monitor = GlobalMonitor(NOTIFICATION_BOT_TOKEN)
            au_monitor = AUMonitor(NOTIFICATION_BOT_TOKEN)
            
            # Schedule monitoring runs every 10 seconds
            schedule.every(10).seconds.do(global_monitor.check_all_monitored_products)
            schedule.every(10).seconds.do(au_monitor.check_all_monitored_products)
            
            print("Monitoring schedule set to check every 10 seconds")
            
            while True:
                schedule.run_pending()
                time.sleep(1)  # Sleep for 1 second between schedule checks
        except Exception as e:
            print(f"Error running monitors: {e}")
            time.sleep(10)  # Wait and retry
    else:
        print("Notification bot token not found!")

if __name__ == "__main__":
    # Start settings bot in a separate thread
    settings_bot_thread = threading.Thread(target=run_settings_bot)
    settings_bot_thread.daemon = True
    settings_bot_thread.start()
    
    # Run monitors in the main thread
    print("Starting worker processes...")
    run_monitors()