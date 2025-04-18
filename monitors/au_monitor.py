import requests
from database import Database
from notification_bot import NotificationBot

class AUMonitor:
    def __init__(self, notification_bot_token):
        self.db = Database()
        self.notification_bot = NotificationBot(notification_bot_token)
    
    def get_stock_level(self, item):
        """Determine stock level based on product variant data"""
        if item.get('available') and item.get('inventory_quantity', 0) > 0:
            return item['inventory_quantity']
        elif item.get('available') and (not item.get('inventory_quantity') or item.get('inventory_quantity', 0) < 1):
            return 'In Stock (Quantity unknown)'
        else:
            return 'Out of stock'
    
    def check_stock(self, url):
        """Check stock for a given Shopify product URL"""
        # Make sure we're using the JSON endpoint
        url = url.split('?')[0] + '.js'
        
        try:
            print(f"Checking stock for: {url}")
            response = requests.get(url)
            
            if response.status_code == 200:
                product_data = response.json()
                product_title = product_data.get('title', 'Unknown Product')
                
                in_stock = False
                for variant in product_data.get('variants', []):
                    stock = self.get_stock_level(variant)
                    if stock != 'Out of stock':
                        in_stock = True
                        break
                
                return {
                    "title": product_title,
                    "in_stock": in_stock
                }
            else:
                print(f"Error finding product: {response.reason}")
                return None
        
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
    
    def check_all_monitored_products(self):
        """Check stock for all monitored products"""
        monitored_products = self.db.get_all_active_monitoring()
        
        for product in monitored_products:
            product_id = product[0]
            product_name = product[1]
            au_link = product[3]
            
            if not au_link:
                continue
            
            # Check stock status
            stock_info = self.check_stock(au_link)
            
            if stock_info and stock_info["in_stock"]:
                # Send notification
                self.notification_bot.send_stock_notification(
                    product_id, product_name, au_link, is_global=False
                )
                
                print(f"[AU] {product_name} is in stock! Notifications sent.")
            else:
                print(f"[AU] {product_name} is out of stock.")