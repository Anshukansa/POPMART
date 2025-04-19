"""
Telegram bot functionality for the Popmart monitoring system
Includes both settings bot and notification bot
"""
import logging
# For compatibility with older python-telegram-bot versions
try:
    # Try imports for version 20.x
    import telegram
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, CallbackQueryHandler,
        ContextTypes, filters
    )
    PTB_VERSION = 20
except ImportError:
    # Fallback to version 13.x
    import telegram
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Updater, CommandHandler, MessageHandler, CallbackQueryHandler,
        CallbackContext, Filters
    )
    PTB_VERSION = 13
import database as db
from config import SETTINGS_BOT_TOKEN, NOTIFICATION_BOT_TOKEN

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Settings Bot handlers
async def start_command(update: Update, context) -> None:
    """Handle the /start command - register user and show main menu"""
    user = update.effective_user
    
    # Register user in database if not already registered
    db.add_user(user.id, user.username or user.first_name)
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context) -> None:
    """Show the main menu with buttons"""
    keyboard = [
        [InlineKeyboardButton("📊 My Balance", callback_data="balance")],
        [InlineKeyboardButton("🛒 Products to Monitor", callback_data="products")],
        [InlineKeyboardButton("ℹ️ My Monitoring List", callback_data="my_monitoring")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        "Welcome to the Popmart Monitoring Bot!\n\n"
        "What would you like to do?",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context) -> None:
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        await show_balance(update, context)
    elif query.data == "products":
        await show_products(update, context)
    elif query.data == "my_monitoring":
        await show_my_monitoring(update, context)
    elif query.data.startswith("monitor_"):
        product_id = int(query.data.split("_")[1])
        await confirm_monitoring(update, context, product_id)
    elif query.data.startswith("confirm_"):
        product_id = int(query.data.split("_")[1])
        await add_monitoring(update, context, product_id)
    elif query.data == "back_to_menu":
        await show_main_menu(update, context)

async def show_balance(update: Update, context) -> None:
    """Show user's current balance"""
    query = update.callback_query
    user_id = query.from_user.id
    
    user = db.get_user(user_id)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Your current balance: ${user['balance']:.2f}\n\n"
        "Note: Balance can only be added by an administrator.",
        reply_markup=reply_markup
    )

async def show_products(update: Update, context) -> None:
    """Show list of available products to monitor"""
    query = update.callback_query
    products = db.get_all_products()
    
    if not products:
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "No products available for monitoring yet.",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                f"{product['product_name']} - ${product['price']:.2f}",
                callback_data=f"monitor_{product['product_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Select a product to monitor:",
        reply_markup=reply_markup
    )

async def confirm_monitoring(update: Update, context, product_id: int) -> None:
    """Confirm monitoring subscription"""
    query = update.callback_query
    user_id = query.from_user.id
    
    user = db.get_user(user_id)
    product = db.get_product(product_id)
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{product_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user['balance'] < product['price']:
        await query.edit_message_text(
            f"You want to monitor: {product['product_name']}\n"
            f"Price: ${product['price']:.2f}\n\n"
            f"Your balance: ${user['balance']:.2f}\n\n"
            "⚠️ You don't have sufficient balance for this monitoring subscription.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Products", callback_data="products")
            ]])
        )
    else:
        await query.edit_message_text(
            f"You want to monitor: {product['product_name']}\n"
            f"Price: ${product['price']:.2f}\n\n"
            f"Your balance: ${user['balance']:.2f}\n\n"
            "This will monitor the product for 30 days. Proceed?",
            reply_markup=reply_markup
        )

async def add_monitoring(update: Update, context, product_id: int) -> None:
    """Add monitoring subscription"""
    query = update.callback_query
    user_id = query.from_user.id
    
    success, message = db.add_monitoring(user_id, product_id)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if success:
        product = db.get_product(product_id)
        await query.edit_message_text(
            f"✅ Success! You are now monitoring: {product['product_name']}\n\n"
            "You will receive notifications when this product is in stock.",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            f"❌ Error: {message}",
            reply_markup=reply_markup
        )

async def show_my_monitoring(update: Update, context) -> None:
    """Show user's active monitoring subscriptions"""
    query = update.callback_query
    user_id = query.from_user.id
    
    user_monitoring = db.get_user_monitoring(user_id)
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not user_monitoring:
        await query.edit_message_text(
            "You are not monitoring any products yet.",
            reply_markup=reply_markup
        )
        return
    
    message = "Your active monitoring subscriptions:\n\n"
    
    for monitor in user_monitoring:
        message += f"• {monitor['product_name']} (expires: {monitor['expiry_date']})\n"
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context) -> None:
    """Send a message when the command /help is issued"""
    await update.message.reply_text(
        "Use /start to begin interacting with the bot.\n\n"
        "You can monitor Popmart products and receive notifications when they are in stock."
    )

# Notification Bot functionality
async def send_notification(user_id: int, message: str) -> None:
    """Send notification to a user"""
    try:
        if PTB_VERSION >= 20:
            # For v20.x, we need to create a new application each time
            bot = telegram.Bot(token=NOTIFICATION_BOT_TOKEN)
            await bot.send_message(chat_id=user_id, text=message)
        else:
            # For older versions
            import telegram
            bot = telegram.Bot(token=NOTIFICATION_BOT_TOKEN)
            bot.send_message(chat_id=user_id, text=message)
        return True
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

# Function to notify users about stock availability
async def notify_users_about_stock(product_id: int, site: str, url: str) -> None:
    """Notify all users monitoring a product when it's in stock"""
    try:
        product = db.get_product(product_id)
        if not product:
            return
        
        monitors = db.get_product_monitors(product_id)
        
        for monitor in monitors:
            message = (
                f"🔔 {product['product_name']} is now in stock on Popmart {site}!\n\n"
                f"Click here to view: {url}\n\n"
                f"Hurry! Stock may be limited."
            )
            await send_notification(monitor['user_id'], message)
    except Exception as e:
        logger.error(f"Error notifying users: {str(e)}")


# Settings bot setup
def run_settings_bot():
    """Start the settings bot"""
    if PTB_VERSION >= 20:
        # For v20.x and newer
        application = Application.builder().token(SETTINGS_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Start the Bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
        return application
    else:
        # For v13.x and older
        updater = Updater(SETTINGS_BOT_TOKEN)
        dispatcher = updater.dispatcher
        
        # Add handlers
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        
        # Start the Bot
        updater.start_polling()
        updater.idle()
        
        return updater