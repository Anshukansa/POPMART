"""
Main application entry point for the Popmart monitoring system
"""
import threading
import logging
import database as db
import admin_panel
import telegram_bot
import monitor_global
import monitor_au

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Start all system components"""
    # Initialize database
    logger.info("Initializing database...")
    db.init_db()
    
    # Start admin panel in a separate thread
    logger.info("Starting admin panel...")
    admin_thread = threading.Thread(target=admin_panel.run_admin_panel)
    admin_thread.daemon = True
    admin_thread.start()
    
    # Start monitoring scripts in separate threads
    logger.info("Starting Popmart Global monitoring...")
    global_monitor_thread = threading.Thread(target=monitor_global.start_monitoring)
    global_monitor_thread.daemon = True
    global_monitor_thread.start()
    
    logger.info("Starting Popmart AU monitoring...")
    au_monitor_thread = threading.Thread(target=monitor_au.start_monitoring)
    au_monitor_thread.daemon = True
    au_monitor_thread.start()
    
    # Start settings bot (this will block the main thread)
    logger.info("Starting settings bot...")
    telegram_bot.run_settings_bot()

if __name__ == "__main__":
    main()