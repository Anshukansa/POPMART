import os
import time
import sys
import logging
import argparse
from monitors.selenium_monitor import SeleniumMonitor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("worker.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description='PopMart Selenium Monitor Worker')
    parser.add_argument('--interval', type=int, default=10, 
                        help='Check interval in seconds (default: 10)')
    parser.add_argument('--token', type=str, 
                        help='Notification bot token (default: uses env var BOT_TOKEN)')
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Get bot token from arguments or environment variable
    bot_token = args.token or os.environ.get('BOT_TOKEN')
    if not bot_token:
        logger.error("No bot token provided. Set BOT_TOKEN environment variable or use --token")
        sys.exit(1)
    
    # Get check interval
    check_interval = args.interval
    logger.info(f"Using check interval of {check_interval} seconds")
    
    # Initialize the monitor
    logger.info("Initializing database for worker...")
    monitor = SeleniumMonitor(bot_token)
    logger.info("Database setup complete.")
    
    # Start monitoring
    logger.info("Starting settings bot...")
    logger.info("Starting worker processes...")
    logger.info("Starting monitoring...")
    
    logger.info(f"Monitoring schedule set to check every {check_interval} seconds")
    
    try:
        # Main monitoring loop
        while True:
            start_time = time.time()
            
            try:
                # Check all products
                monitor.check_all_monitored_products()
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {str(e)}")
                logger.exception("Detailed exception info:")
            
            # Calculate how long to wait until next check
            elapsed = time.time() - start_time
            wait_time = max(1, check_interval - elapsed)
            
            # Sleep until next check
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error in worker: {str(e)}")
        logger.exception("Detailed exception info:")
    finally:
        # Clean up resources
        try:
            monitor.cleanup()
            logger.info("Resources cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    main()