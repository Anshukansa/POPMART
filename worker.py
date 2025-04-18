import os
import time
import threading
import schedule
from settings_bot import SettingsBot
from monitors.global_monitor import GlobalMonitor
from monitors.au_monitor import AUMonitor

# Load environment variables
SETTINGS_BOT_TOKEN = os.environ.get("SETTINGS_BOT_TOKEN")
NOTIFICATION_BOT_TOKEN = os.environ.get("NOTIFICATION_BOT_TOKEN")

def run_settings_bot():
    """Run the settings bot"""
    if SETTINGS_BOT_TOKEN:
        print("Starting settings bot...")
        bot = SettingsBot(SETTINGS_BOT_TOKEN)
        bot.run()
    else:
        print("Settings bot token not found!")

def run_monitors():
    """Run the monitoring scripts"""
    if NOTIFICATION_BOT_TOKEN:
        print("Starting monitoring...")
        global_monitor = GlobalMonitor(NOTIFICATION_BOT_TOKEN)
        au_monitor = AUMonitor(NOTIFICATION_BOT_TOKEN)
        
        # Run once immediately
        global_monitor.check_all_monitored_products()
        au_monitor.check_all_monitored_products()
        
        # Schedule monitoring runs
        schedule.every(30).minutes.do(global_monitor.check_all_monitored_products)
        schedule.every(30).minutes.do(au_monitor.check_all_monitored_products)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
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