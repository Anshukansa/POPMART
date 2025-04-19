"""
Monitoring script for Popmart AU (Shopify-based)
"""
import requests
import time
import logging
import asyncio
from telegram_bot import notify_users_about_stock
import database as db
from config import CHECK_INTERVAL

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_stock_level(item):
    """Determine stock level based on product variant data"""
    if item.get('available') and item.get('inventory_quantity', 0) > 0:
        return item['inventory_quantity']
    elif item.get('available') and (not item.get('inventory_quantity') or item.get('inventory_quantity', 0) < 1):
        return 'In Stock (Quantity unknown)'
    else:
        return 'Out of stock'

def check_stock(url):
    """Check stock for a given Shopify product URL"""
    # Make sure we're using the JSON endpoint
    if not url:
        return None
        
    url = url.split('?')[0] + '.js'
    
    try:
        logger.info(f"Checking stock for: {url}")
        response = requests.get(url)
        
        if response.status_code == 200:
            product_data = response.json()
            product_name = product_data.get('title', 'Unknown Product')
            logger.info(f"Product: {product_name}")
            
            # Check if any variant is in stock
            in_stock = False
            for variant in product_data.get('variants', []):
                stock = get_stock_level(variant)
                variant_name = 'One Size' if variant.get('title') == 'Default Title' else variant.get('title', 'Unknown Variant')
                logger.info(f"Variant: {variant_name}, Stock: {stock}")
                
                if stock != 'Out of stock':
                    in_stock = True
            
            return in_stock
        else:
            logger.error(f"Error finding product: {response.reason}")
            return None
    
    except Exception as e:
        logger.error(f"Error checking stock: {str(e)}")
        return None

# The following functions are for running the monitoring asynchronously

async def check_product_async(monitor):
    """Check a single product asynchronously"""
    try:
        # Only check AU link
        au_link = monitor['au_link']
        if not au_link:
            return
            
        in_stock = check_stock(au_link)
        
        if in_stock:
            logger.info(f"Product {monitor['product_name']} is in stock on AU!")
            await notify_users_about_stock(monitor['product_id'], "AU", au_link)
    except Exception as e:
        logger.error(f"Error checking product {monitor.get('product_name', 'unknown')}: {str(e)}")

async def check_all_products():
    """Check all products for stock and notify users"""
    try:
        monitors = db.get_all_active_monitors()
        
        # Process each product sequentially (can be made parallel if needed)
        for monitor in monitors:
            await check_product_async(monitor)
    except Exception as e:
        logger.error(f"Error checking products: {str(e)}")

async def run_monitoring_loop():
    """Run continuous monitoring loop"""
    logger.info("Starting Popmart AU monitoring")
    
    while True:
        try:
            await check_all_products()
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
        
        # Wait for the next check interval
        try:
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error during sleep: {str(e)}")
            # If we can't sleep, wait a bit to avoid CPU spinning
            time.sleep(60)

def start_monitoring():
    """Start the monitoring process"""
    try:
        # This is the key fix - create a new event loop for this thread
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        
        # Run the monitoring loop
        new_loop.run_until_complete(run_monitoring_loop())
    except Exception as e:
        logger.error(f"Error starting monitoring: {str(e)}")

if __name__ == "__main__":
    start_monitoring()