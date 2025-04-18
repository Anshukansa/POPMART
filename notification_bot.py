import logging
import requests
import time
import json
from database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("notification_bot.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class NotificationBot:
    """Pure HTTP implementation of Telegram bot without telebot dependency"""
    
    def __init__(self, token):
        self.token = token
        self.db = Database()
        logger.info("Notification bot initialized with HTTP API approach")

    def send_message(self, chat_id, message):
        """Send a message to a Telegram chat using the HTTP API directly"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"Message sent to chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {str(e)}")
            return False

    def send_bulk_message(self, chat_ids, message):
        """Send the same message to multiple Telegram chats"""
        success_count = 0
        for chat_id in chat_ids:
            if self.send_message(chat_id, message):
                success_count += 1
            # Add a small delay to avoid hitting rate limits
            time.sleep(0.1)
        logger.info(f"Bulk message sent to {success_count}/{len(chat_ids)} chats")
        return success_count

    def send_stock_notification(self, product_id, product_name, product_url, is_global=True):
        """Send stock notification to all subscribed users"""
        try:
            # Get all subscribed users for this product
            subscribers = self.db.get_product_subscribers(product_id)
            
            if not subscribers:
                logger.info(f"No subscribers for product {product_name}")
                return
            
            store_type = "Global" if is_global else "AU"
            message = f"🔔 <b>STOCK ALERT!</b> 🔔\n\n"
            message += f"<b>{product_name}</b> is now in stock at {store_type} store!\n\n"
            message += f"<a href='{product_url}'>Click here to view</a>"
            
            chat_ids = [str(sub[0]) for sub in subscribers]  # Convert telegram_id to string
            
            sent_count = self.send_bulk_message(chat_ids, message)
            
            logger.info(f"Stock notification for {product_name} sent to {sent_count}/{len(chat_ids)} subscribers")
            
            # If database has this method
            if hasattr(self.db, 'log_notification'):
                self.db.log_notification(product_id, store_type, len(chat_ids), sent_count)
            
        except Exception as e:
            logger.error(f"Error sending stock notification for product {product_name}: {str(e)}")
            logger.exception("Detailed exception:")

    def send_welcome_message(self, chat_id, user_name=None):
        """Send welcome message to new user"""
        try:
            greeting = f"Hello {user_name}!" if user_name else "Hello!"
            message = f"{greeting}\n\n"
            message += "Welcome to the PopMart Stock Alert Bot. "
            message += "You'll receive notifications when products you subscribe to come back in stock.\n\n"
            message += "Use /subscribe to start tracking a product."
            
            self.send_message(chat_id, message)
            logger.info(f"Welcome message sent to chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error sending welcome message to chat {chat_id}: {str(e)}")