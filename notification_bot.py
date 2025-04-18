import telebot
from database import Database

class NotificationBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.db = Database()
    
    def send_stock_notification(self, product_id, product_name, link, is_global=True):
        # Get all users monitoring this product
        subscribers = self.db.get_product_subscribers(product_id)
        
        if not subscribers:
            return 0
        
        message = f"🔔 *{product_name}* is now in stock!\n\n"
        message += f"Store: {'Popmart Global' if is_global else 'Popmart AU'}\n"
        message += f"Link: {link}"
        
        sent_count = 0
        for subscriber in subscribers:
            try:
                self.bot.send_message(
                    subscriber[0],
                    message,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                sent_count += 1
            except Exception as e:
                print(f"Error sending notification to {subscriber[0]}: {str(e)}")
        
        return sent_count