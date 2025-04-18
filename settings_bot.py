import logging
import requests
import json
import time
from database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("settings_bot.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class SettingsBot:
    """Simple HTTP implementation of Settings Bot without telebot dependency"""
    
    def __init__(self, token):
        self.token = token
        self.db = Database()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0  # For update polling
        logger.info("Settings bot initialized with HTTP API approach")
    
    def get_updates(self, timeout=30):
        """Get updates from Telegram Bot API"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                "offset": self.offset,
                "timeout": timeout,
                "allowed_updates": json.dumps(["message", "callback_query"])
            }
            response = requests.get(url, params=params, timeout=timeout+5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting updates: {str(e)}")
            # Sleep before retrying to avoid overwhelming the API
            time.sleep(1)
            return {"ok": False, "result": []}
    
    def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML"):
        """Send a message to a chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)
                
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {str(e)}")
            return None
    
    def create_inline_keyboard(self, buttons):
        """Create an inline keyboard markup"""
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button in row:
                keyboard_row.append({
                    "text": button["text"],
                    "callback_data": button["callback_data"]
                })
            keyboard.append(keyboard_row)
        
        return {"inline_keyboard": keyboard}
    
    def show_main_menu(self, chat_id):
        """Show the main menu"""
        markup = self.create_inline_keyboard([
            [
                {"text": "📊 My Balance", "callback_data": "balance"},
                {"text": "🛒 Products", "callback_data": "products"}
            ],
            [
                {"text": "ℹ️ My Monitoring", "callback_data": "monitoring"}
            ]
        ])
        
        self.send_message(
            chat_id, 
            "Welcome to Popmart Product Monitor! What would you like to do?",
            reply_markup=markup
        )
    
    def show_balance(self, chat_id, user_id):
        """Show user balance"""
        user = self.db.get_user(user_id)
        if user:
            markup = self.create_inline_keyboard([
                [{"text": "◀️ Back", "callback_data": "back"}]
            ])
            
            self.send_message(
                chat_id,
                f"Your current balance: ${user[2]:.2f}\n\n"
                f"Balance is added by admins for product monitoring.",
                reply_markup=markup
            )
        else:
            self.send_message(chat_id, "User not found. Please restart with /start")
    
    def show_products(self, chat_id):
        """Show available products"""
        products = self.db.get_all_products()
        
        if not products:
            markup = self.create_inline_keyboard([
                [{"text": "◀️ Back", "callback_data": "back"}]
            ])
            self.send_message(
                chat_id,
                "No products available for monitoring yet.",
                reply_markup=markup
            )
            return
        
        for product in products:
            markup = self.create_inline_keyboard([
                [{"text": f"Monitor (${product[4]:.2f})", "callback_data": f"monitor_{product[0]}"}]
            ])
            
            self.send_message(
                chat_id,
                f"*{product[1]}*\n"
                f"Global: {product[2]}\n"
                f"AU: {product[3]}\n"
                f"Price: ${product[4]:.2f} for 30 days monitoring",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        
        # Add a back button after listing all products
        markup = self.create_inline_keyboard([
            [{"text": "◀️ Back to Main Menu", "callback_data": "back"}]
        ])
        self.send_message(chat_id, "Select a product to monitor", reply_markup=markup)
    
    def show_monitoring(self, chat_id, user_id):
        """Show user's active monitoring subscriptions"""
        monitoring = self.db.get_user_monitoring(user_id)
        
        markup = self.create_inline_keyboard([
            [{"text": "◀️ Back", "callback_data": "back"}]
        ])
        
        if not monitoring:
            self.send_message(
                chat_id,
                "You're not monitoring any products yet.",
                reply_markup=markup
            )
            return
        
        message = "Your active monitoring subscriptions:\n\n"
        
        for item in monitoring:
            expiry = item[4].strftime("%Y-%m-%d") if item[4] else "Unknown"
            message += f"*{item[1]}*\n"
            message += f"Expires: {expiry}\n\n"
        
        self.send_message(
            chat_id,
            message,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    def subscribe_to_product(self, chat_id, user_id, product_id):
        """Subscribe user to a product"""
        success, message = self.db.add_monitoring(user_id, product_id)
        
        markup = self.create_inline_keyboard([
            [{"text": "◀️ Back", "callback_data": "back"}]
        ])
        
        self.send_message(chat_id, message, reply_markup=markup)
    
    def process_update(self, update):
        """Process a single update from Telegram"""
        try:
            # Update the offset for next polling
            update_id = update.get("update_id", 0)
            self.offset = max(self.offset, update_id + 1)
            
            # Handle message update
            if "message" in update:
                message = update["message"]
                chat_id = message["chat"]["id"]
                user_id = message["from"]["id"]
                username = message["from"].get("username") or message["from"].get("first_name", "User")
                
                # Handle /start command
                if "text" in message and message["text"] == "/start":
                    # Register user
                    self.db.add_user(user_id, username)
                    # Show main menu
                    self.show_main_menu(chat_id)
            
            # Handle callback query (inline button press)
            elif "callback_query" in update:
                callback = update["callback_query"]
                message = callback["message"]
                chat_id = message["chat"]["id"]
                user_id = callback["from"]["id"]
                data = callback["data"]
                
                # Process different callback data
                if data == "balance":
                    self.show_balance(chat_id, user_id)
                elif data == "products":
                    self.show_products(chat_id)
                elif data == "monitoring":
                    self.show_monitoring(chat_id, user_id)
                elif data.startswith("monitor_"):
                    product_id = data.split("_")[1]
                    self.subscribe_to_product(chat_id, user_id, product_id)
                elif data == "back":
                    self.show_main_menu(chat_id)
                
                # Answer callback query to remove the loading indicator
                try:
                    requests.post(
                        f"{self.base_url}/answerCallbackQuery",
                        data={"callback_query_id": callback["id"]}
                    )
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error processing update: {str(e)}")
            logger.exception("Detailed exception:")
    
    def run(self):
        """Run the bot polling loop"""
        logger.info("Starting settings bot polling")
        
        try:
            while True:
                updates = self.get_updates()
                
                if updates.get("ok", False):
                    for update in updates.get("result", []):
                        self.process_update(update)
                
                # Short delay to avoid excessive CPU usage if there's an error
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Error in main bot loop: {str(e)}")
            logger.exception("Detailed exception:")