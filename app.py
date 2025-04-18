import os
from settings_bot import SettingsBot
from notification_bot import NotificationBot
from admin_panel import AdminPanel
from monitors.selenium_monitor import GlobalMonitor
from monitors.au_monitor import AUMonitor
import threading
import time
import schedule

# Load environment variables
SETTINGS_BOT_TOKEN = os.environ.get("SETTINGS_BOT_TOKEN")
NOTIFICATION_BOT_TOKEN = os.environ.get("NOTIFICATION_BOT_TOKEN")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")

def run_settings_bot():
    """Run the settings bot"""
    if SETTINGS_BOT_TOKEN:
        bot = SettingsBot(SETTINGS_BOT_TOKEN)
        bot.run()
    else:
        print("Settings bot token not found!")

def run_admin_panel():
    """Run the admin panel"""
    panel = AdminPanel(ADMIN_USERNAME, ADMIN_PASSWORD, NOTIFICATION_BOT_TOKEN)
    panel.run()

def run_monitors():
    """Run the monitoring scripts"""
    if NOTIFICATION_BOT_TOKEN:
        global_monitor = GlobalMonitor(NOTIFICATION_BOT_TOKEN)
        au_monitor = AUMonitor(NOTIFICATION_BOT_TOKEN)
        
        # Schedule monitoring runs every 10 seconds
        schedule.every(10).seconds.do(global_monitor.check_all_monitored_products)
        schedule.every(10).seconds.do(au_monitor.check_all_monitored_products)
        
        while True:
            schedule.run_pending()
            time.sleep(1)  # Sleep for 1 second between schedule checks
    else:
        print("Notification bot token not found!")

# Create the admin panel and expose its Flask app for Gunicorn
panel = AdminPanel(ADMIN_USERNAME, ADMIN_PASSWORD, NOTIFICATION_BOT_TOKEN)
app = panel.app  # Expose the Flask app for Gunicorn

if __name__ == "__main__":
    # Start settings bot in a separate thread
    settings_bot_thread = threading.Thread(target=run_settings_bot)
    settings_bot_thread.daemon = True
    settings_bot_thread.start()
    
    # Start monitoring in a separate thread
    monitors_thread = threading.Thread(target=run_monitors)
    monitors_thread.daemon = True
    monitors_thread.start()
    
    # Run admin panel in the main thread
    panel.run()