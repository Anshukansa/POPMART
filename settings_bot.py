# Import telebot with error handling
try:
    import telebot
    from telebot import types
except ImportError:
    # For debugging purposes, print a clear message
    import sys
    print("ERROR: Failed to import telebot. Make sure PyTelegramBotAPI is installed properly.", file=sys.stderr)
    # Create a simple fallback class
    class telebot:
        class TeleBot:
            def __init__(self, *args, **kwargs):
                pass
            def polling(self, *args, **kwargs):
                pass
    class types:
        class InlineKeyboardMarkup:
            def __init__(self):
                pass
            def row(self, *args):
                return self
        class InlineKeyboardButton:
            def __init__(self, *args, **kwargs):
                pass

from database import Database

class SettingsBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.db = Database()
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            # Register user
            user_id = message.from_user.id
            username = message.from_user.username or message.from_user.first_name
            
            self.db.add_user(user_id, username)
            
            # Send welcome message with main menu
            self.show_main_menu(message.chat.id)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            if call.data == "balance":
                self.show_balance(call.message.chat.id, call.from_user.id)
            elif call.data == "products":
                self.show_products(call.message.chat.id)
            elif call.data == "monitoring":
                self.show_monitoring(call.message.chat.id, call.from_user.id)
            elif call.data.startswith("monitor_"):
                product_id = call.data.split("_")[1]
                self.subscribe_to_product(call.message.chat.id, call.from_user.id, product_id)
            elif call.data == "back":
                self.show_main_menu(call.message.chat.id)
    
    def show_main_menu(self, chat_id):
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📊 My Balance", callback_data="balance"),
            types.InlineKeyboardButton("🛒 Products", callback_data="products")
        )
        markup.row(
            types.InlineKeyboardButton("ℹ️ My Monitoring", callback_data="monitoring")
        )
        
        self.bot.send_message(
            chat_id, 
            "Welcome to Popmart Product Monitor! What would you like to do?",
            reply_markup=markup
        )
    
    def show_balance(self, chat_id, user_id):
        user = self.db.get_user(user_id)
        if user:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back"))
            
            self.bot.send_message(
                chat_id,
                f"Your current balance: ${user[2]:.2f}\n\n"
                f"Balance is added by admins for product monitoring.",
                reply_markup=markup
            )
        else:
            self.bot.send_message(chat_id, "User not found. Please restart with /start")
    
    def show_products(self, chat_id):
        products = self.db.get_all_products()
        
        if not products:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back"))
            self.bot.send_message(
                chat_id,
                "No products available for monitoring yet.",
                reply_markup=markup
            )
            return
        
        for product in products:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton(
                    f"Monitor (${product[4]:.2f})", 
                    callback_data=f"monitor_{product[0]}"
                )
            )
            
            self.bot.send_message(
                chat_id,
                f"*{product[1]}*\n"
                f"Global: {product[2]}\n"
                f"AU: {product[3]}\n"
                f"Price: ${product[4]:.2f} for 30 days monitoring",
                parse_mode="Markdown",
                reply_markup=markup
            )
        
        # Add a back button after listing all products
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back"))
        self.bot.send_message(chat_id, "Select a product to monitor", reply_markup=markup)
    
    def show_monitoring(self, chat_id, user_id):
        monitoring = self.db.get_user_monitoring(user_id)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back"))
        
        if not monitoring:
            self.bot.send_message(
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
        
        self.bot.send_message(
            chat_id,
            message,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    def subscribe_to_product(self, chat_id, user_id, product_id):
        success, message = self.db.add_monitoring(user_id, product_id)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back"))
        
        self.bot.send_message(chat_id, message, reply_markup=markup)
    
    def run(self):
        try:
            self.bot.polling(none_stop=True)
        except Exception as e:
            import sys
            print(f"Error in bot polling: {e}", file=sys.stderr)