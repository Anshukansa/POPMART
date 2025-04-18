import os
import time
import sys
import logging
import argparse
import json
import requests
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("worker.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import database
try:
    from database import Database
    db = Database()
except Exception as e:
    logger.error(f"Error importing database: {e}")
    db = None

# Simple product checker without Selenium
def check_product_http(product_id, product_name, product_url):
    """Check product stock using direct HTTP request instead of Selenium"""
    logger.info(f"Checking product: {product_name} (ID: {product_id}, URL: {product_url})")
    
    try:
        # Extract product ID from URL
        url_product_id = product_url.strip().split('/')[-1].split('?')[0]
        
        # Request product page
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # First try standard HTTP GET
        logger.info(f"Sending HTTP request to {product_url}")
        response = requests.get(product_url, headers=headers, timeout=15)
        
        # Check for out of stock indicators in the HTML
        out_of_stock_phrases = [
            "out of stock", 
            "notify me when available",
            "sold out",
            "currently unavailable"
        ]
        
        html_lower = response.text.lower()
        
        # Check if any out-of-stock phrases exist in the HTML
        is_out_of_stock = any(phrase in html_lower for phrase in out_of_stock_phrases)
        in_stock = not is_out_of_stock
        
        status = "IN STOCK" if in_stock else "OUT OF STOCK"
        logger.info(f"HTTP check for {product_name}: {status}")
        
        return {
            "db_product_id": product_id,
            "title": product_name,
            "price": "Not checked",
            "status": status,
            "in_stock": in_stock,
            "url": product_url
        }
            
    except Exception as e:
        logger.error(f"Error checking {product_url}: {str(e)}")
        return {
            "db_product_id": product_id,
            "title": product_name,
            "price": "Unknown",
            "status": "ERROR",
            "in_stock": False,
            "url": product_url,
            "error": str(e)
        }

def check_all_products():
    """Check all monitored products"""
    try:
        if not db:
            logger.error("Database not initialized")
            return []
            
        monitored_products = db.get_all_active_monitoring()
        
        if not monitored_products:
            logger.info("No products being monitored")
            return []
            
        logger.info(f"Checking {len(monitored_products)} monitored products")
        
        results = []
        for product in monitored_products:
            # Ensure that we unpack only the expected number of columns
            if len(product) < 3:
                logger.warning(f"Skipping product due to unexpected data structure: {product}")
                continue
                
            db_product_id, product_name, global_link = product[:3]  # Only unpack the first three values
            
            if not global_link:
                logger.warning(f"No global link for product {product_name} (DB ID: {db_product_id})")
                continue
            
            # Check product using HTTP
            result = check_product_http(db_product_id, product_name, global_link)
            results.append(result)
        
        # Process results and update database/send notifications
        notify_results(results)
        
        return results
            
    except Exception as e:
        logger.error(f"Error in check_all_monitored_products: {str(e)}")
        logger.exception("Detailed exception info:")
        return []

def notify_results(results):
    """Process results and send notifications if needed"""
    if not db:
        logger.error("Database not initialized for notifications")
        return
        
    for result in results:
        if result.get("status") == "ERROR":
            logger.warning(f"Error checking {result.get('title', 'Unknown')}: {result.get('error', 'Unknown error')}")
            continue
        
        db_product_id = result.get("db_product_id")
        product_name = result.get("title")
        in_stock = result.get("in_stock", False)
        
        # Check if we should notify based on stock status change
        should_notify = db.should_notify_stock_change(db_product_id, "GLOBAL", in_stock)
        
        if in_stock:
            if should_notify:
                logger.info(f"[GLOBAL] {product_name} is now in stock! Sending notifications.")
                send_notification(db_product_id, product_name, result.get("url"))
                logger.info(f"[GLOBAL] Notifications sent for {product_name}.")
            else:
                logger.info(f"[GLOBAL] {product_name} is still in stock. No notifications sent.")
        else:
            logger.info(f"[GLOBAL] {product_name} is out of stock.")

def send_notification(product_id, product_name, product_url):
    """Send notification to subscribed users"""
    try:
        # Get bot token
        bot_token = os.environ.get('BOT_TOKEN')
        if not bot_token:
            logger.error("No bot token provided. Cannot send notifications.")
            return
            
        # Get subscribers
        subscribers = db.get_product_subscribers(product_id)
        if not subscribers:
            logger.info(f"No subscribers for product {product_name}")
            return
            
        # Prepare message
        message = f"🔔 <b>STOCK ALERT!</b> 🔔\n\n"
        message += f"<b>{product_name}</b> is now in stock at Global store!\n\n"
        message += f"<a href='{product_url}'>Click here to view</a>"
        
        # Send to each subscriber
        success_count = 0
        for subscriber in subscribers:
            chat_id = subscriber[0]
            
            try:
                # Send message using Telegram API
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, data=data, timeout=10)
                response.raise_for_status()
                
                success_count += 1
                logger.info(f"Message sent to chat {chat_id}")
                
                # Small delay to avoid rate limits
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error sending message to chat {chat_id}: {str(e)}")
        
        logger.info(f"Stock notification for {product_name} sent to {success_count}/{len(subscribers)} subscribers")
        
    except Exception as e:
        logger.error(f"Error sending stock notification for product {product_name}: {str(e)}")
        logger.exception("Detailed exception:")

def parse_arguments():
    parser = argparse.ArgumentParser(description='PopMart HTTP Monitor Worker')
    parser.add_argument('--interval', type=int, default=30, 
                        help='Check interval in seconds (default: 30)')
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
    
    # Start monitoring
    logger.info("Starting worker processes...")
    logger.info("Starting simple HTTP monitoring...")
    logger.info(f"Monitoring schedule set to check every {check_interval} seconds")
    
    try:
        # Main monitoring loop
        while True:
            start_time = time.time()
            
            try:
                # Check all products using HTTP
                check_all_products()
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

if __name__ == "__main__":
    main()