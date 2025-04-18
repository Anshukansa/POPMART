import time
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from database import Database
from notification_bot import NotificationBot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("popmart_monitor.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class PopMartFastMonitor:
    def __init__(self, notification_bot_token):
        logger.info("Initializing PopMartFastMonitor")
        self.db = Database()  # Connect to your database
        self.notification_bot = NotificationBot(notification_bot_token)  # Connect to notification bot
        self.product_status = {}
        self.executor = None  # Will initialize when we know how many products
        self.drivers = {}
        logger.info("PopMartFastMonitor initialized successfully")
        
    def create_driver(self):
        """Create a highly optimized, undetectable driver"""
        logger.debug("Creating Chrome driver")
        options = Options()
        options.headless = True
        
        # Stealth settings to avoid detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Performance optimizations
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-infobars')
        options.add_argument('--mute-audio')
        options.add_argument('--window-size=1280,720')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.add_argument('--disable-notifications')
        
        # Most important for speed
        options.page_load_strategy = 'eager'
        
        # Network optimizations
        prefs = {
            'profile.default_content_setting_values': {
                'images': 2,                # Disable images
                'plugins': 2,               # Disable plugins
                'popups': 2,                # Disable popups
                'geolocation': 2,           # Disable geolocation
                'notifications': 2,         # Disable notifications
                'auto_select_certificate': 2, # Disable SSL cert selection
                'fullscreen': 2,            # Disable fullscreen permission
                'mouselock': 2,             # Disable mouse lock permission
                'mixed_script': 2,          # Disable mixed script
                'media_stream': 2,          # Disable media stream
                'media_stream_mic': 2,      # Disable mic permission
                'media_stream_camera': 2,   # Disable camera permission
                'automatic_downloads': 2    # Disable multiple downloads
            },
            'disk-cache-size': 4096,        # Limit cache size
            'disable-application-cache': True,
        }
        options.add_experimental_option('prefs', prefs)
        
        driver = webdriver.Chrome(options=options)
        
        # Apply undetectable settings after driver creation
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                })
            '''
        })
        
        logger.debug("Chrome driver created successfully")
        return driver
    
    def check_product(self, db_info):
        """Check a single product with early termination once data is found"""
        db_product_id = db_info["db_product_id"]
        product_name = db_info["product_name"]
        url = db_info["global_link"]
        
        logger.info(f"Checking product: {product_name} (ID: {db_product_id}, URL: {url})")
        
        # Extract API product ID for logging purposes
        api_product_id = url.split('/')[-1].split('%')[0]
        
        # Create driver if it doesn't exist for this URL
        if url not in self.drivers:
            try:
                self.drivers[url] = self.create_driver()
            except Exception as e:
                logger.error(f"Error creating driver for {url}: {str(e)}")
                return {
                    "db_product_id": db_product_id,
                    "product_name": product_name,
                    "title": "Error - Driver Creation Failed",
                    "price": "Unknown",
                    "status": "ERROR",
                    "in_stock": False,
                    "url": url,
                    "api_product_id": api_product_id
                }
            
        driver = self.drivers[url]
        
        try:
            # Navigate to the URL
            driver.get(url)
            
            # Inject early termination script - stops page loading once we find what we need
            early_termination_script = """
                let titleFound = false;
                let priceFound = false;
                let stockStatusFound = false;
                
                // Create a MutationObserver to watch for our elements
                const observer = new MutationObserver(function(mutations) {
                    // Check if title exists
                    if (!titleFound && document.querySelector('h1.index_title___0OsZ')) {
                        titleFound = true;
                    }
                    
                    // Check if price exists
                    if (!priceFound && document.querySelector('div.index_price__cAj0h')) {
                        priceFound = true;
                    }
                    
                    // Check if stock status exists (either button)
                    if (!stockStatusFound && 
                        (document.querySelector('div.index_euBtn__7NmZ6, div.index_btn__w5nKF'))) {
                        stockStatusFound = true;
                    }
                    
                    // If we found all elements, stop loading the page
                    if (titleFound && priceFound && stockStatusFound) {
                        window.stop();
                        observer.disconnect();
                    }
                });
                
                // Start observing the document
                observer.observe(document.documentElement, {
                    childList: true,
                    subtree: true
                });
            """
            
            driver.execute_script(early_termination_script)
            
            # Wait for just the title element with a short timeout
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.index_title___0OsZ"))
                )
            except Exception as e:
                logger.warning(f"Timeout waiting for title element: {str(e)}")
                # If we can't even get the title in 5 seconds, it's a problem
                return {
                    "db_product_id": db_product_id,
                    "product_name": product_name,
                    "title": "Error - Page Load Timeout",
                    "price": "Unknown",
                    "status": "ERROR",
                    "in_stock": False,
                    "url": url,
                    "api_product_id": api_product_id
                }
            
            # Extract data - don't wait for other elements, just try to get what's there
            title = driver.find_element(By.CSS_SELECTOR, "h1.index_title___0OsZ").text
            
            try:
                price = driver.find_element(By.CSS_SELECTOR, "div.index_price__cAj0h").text
            except:
                price = "Unknown Price"
            
            # Quick check for specific buttons 
            add_cart_elements = driver.find_elements(By.XPATH, 
                "//div[contains(@class, 'index_euBtn__7NmZ6') and contains(text(), 'ADD TO CART')]")
            
            notify_elements = driver.find_elements(By.XPATH, 
                "//div[contains(@class, 'index_btn__w5nKF') and contains(text(), 'NOTIFY ME WHEN AVAILABLE')]")
                
            # Determine stock status
            if add_cart_elements:
                status = "IN STOCK"
                in_stock = True
            elif notify_elements:
                status = "OUT OF STOCK"
                in_stock = False
            else:
                # Quick extra check with direct JavaScript as a fallback
                buttons_js = driver.execute_script("""
                    const addToCartBtn = document.querySelector('div.index_euBtn__7NmZ6');
                    if (addToCartBtn && addToCartBtn.textContent.includes('ADD TO CART')) return 'IN STOCK';
                    
                    const notifyBtn = document.querySelector('div.index_btn__w5nKF'); 
                    if (notifyBtn && notifyBtn.textContent.includes('NOTIFY ME WHEN AVAILABLE')) return 'OUT OF STOCK';
                    
                    return 'UNKNOWN';
                """)
                
                status = buttons_js
                in_stock = status == "IN STOCK"
            
            logger.info(f"Product '{title}' (ID: {db_product_id}) in_stock: {in_stock}")
                
            return {
                "db_product_id": db_product_id,
                "product_name": product_name,
                "title": title,
                "price": price,
                "status": status,
                "in_stock": in_stock,
                "url": url,
                "api_product_id": api_product_id
            }
            
        except Exception as e:
            logger.error(f"Error checking {url}: {str(e)}")
            return {
                "db_product_id": db_product_id,
                "product_name": product_name,
                "title": "Error",
                "price": "Error",
                "status": "ERROR",
                "in_stock": False,
                "url": url,
                "api_product_id": api_product_id,
                "error": str(e)
            }
    
    def check_all_monitored_products(self):
        """Check stock for all monitored products using web scraping"""
        try:
            monitored_products = self.db.get_all_active_monitoring()
            
            if not monitored_products:
                logger.info("No products being monitored")
                return []
                
            logger.info(f"Checking {len(monitored_products)} monitored products")
            
            # Build the list of products to check with DB info
            products_to_check = []
            
            for product in monitored_products:
                try:
                    # Ensure that we unpack only the expected number of columns
                    if len(product) < 3:
                        logger.warning(f"Skipping product due to unexpected data structure: {product}")
                        continue
                        
                    db_product_id, product_name, global_link = product[:3]  # Only unpack the first three values
                    
                    if not global_link:
                        logger.warning(f"No global link for product {product_name} (DB ID: {db_product_id})")
                        continue
                    
                    # Add to the list of products to check
                    products_to_check.append({
                        "db_product_id": db_product_id,
                        "product_name": product_name,
                        "global_link": global_link
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing product {product}: {str(e)}")
                    continue
            
            # Initialize executor if needed with the count of products
            if self.executor is None or self.executor._max_workers < len(products_to_check):
                if self.executor is not None:
                    self.executor.shutdown(wait=False)
                self.executor = ThreadPoolExecutor(max_workers=len(products_to_check))
                logger.debug(f"Initialized thread pool with {len(products_to_check)} workers")
            
            # Execute checks in parallel
            futures = [self.executor.submit(self.check_product, product_info) for product_info in products_to_check]
            results = [future.result() for future in futures]
            
            # Process results and update database/send notifications
            for result in results:
                try:
                    db_product_id = result["db_product_id"]
                    product_name = result["product_name"]
                    status = result["status"]
                    in_stock = result["in_stock"]
                    url = result["url"]
                    
                    if status != "ERROR":
                        # Update the product status in our tracking
                        api_product_id = result["api_product_id"]
                        self.product_status[api_product_id] = {
                            'db_product_id': db_product_id,
                            'title': result['title'],
                            'price': result['price'],
                            'status': status,
                            'in_stock': in_stock,
                            'url': url,
                            'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Check if we should notify based on stock status change
                        should_notify = self.db.should_notify_stock_change(db_product_id, "AU", in_stock)
                        
                        if in_stock:
                            if should_notify:
                                logger.info(f"[AU] {product_name} is now in stock! Sending notifications.")
                                self.notification_bot.send_stock_notification(db_product_id, product_name, url, is_global=False)
                                logger.info(f"[AU] Notifications sent for {product_name}.")
                            else:
                                logger.info(f"[AU] {product_name} is still in stock. No notifications sent.")
                        else:
                            logger.info(f"[AU] {product_name} is out of stock.")
                except Exception as e:
                    logger.error(f"Error processing result {result}: {str(e)}")
            
            return results
                
        except Exception as e:
            logger.error(f"Error in check_all_monitored_products: {str(e)}")
            logger.exception("Detailed exception info:")
            return []
    
    def check_product_stock(self, product_id_or_url):
        """Check stock for a specific product (for admin testing)"""
        logger.info(f"Admin testing stock check for: {product_id_or_url}")
        
        try:
            # Try to get product info from database
            product = self.db.get_product(product_id_or_url)  # Use original ID for DB lookup
            if not product:
                logger.warning(f"Product not found in database: {product_id_or_url}")
                return {"success": False, "message": "Product not found in database"}
                
            db_product_id = product_id_or_url
            product_name = product[1] if product else f"Product {db_product_id}"
            global_link = product[2] if len(product) > 2 else None
            
            if not global_link:
                logger.error(f"No global link for product {product_name} (ID: {db_product_id})")
                return {"success": False, "message": "No global link found for product"}
            
            logger.info(f"Retrieved product from DB: {product_name} (ID: {db_product_id}, Link: {global_link})")
            
            # Check the product
            product_info = {
                "db_product_id": db_product_id,
                "product_name": product_name,
                "global_link": global_link
            }
            stock_result = self.check_product(product_info)
            
            if stock_result.get('status') == "ERROR":
                logger.error(f"Error checking stock for {product_name}: {stock_result.get('error', 'Unknown error')}")
                return {"success": False, "message": f"Error checking stock: {stock_result.get('error', 'Unknown error')}"}
            
            in_stock = stock_result.get('in_stock', False)
            product_title = stock_result.get('title', product_name)
            price = stock_result.get('price', 'Unknown Price')
            
            logger.info(f"Stock check result for {product_title} (ID: {db_product_id}): {'In Stock' if in_stock else 'Out of Stock'}")
            
            return {
                "success": True, 
                "product_name": product_name,
                "product_title": product_title, 
                "price": price,
                "in_stock": in_stock,
                "url": global_link,
                "message": f"AU store: {'In Stock' if in_stock else 'Out of Stock'}"
            }
            
        except Exception as e:
            logger.error(f"Error in check_product_stock for {product_id_or_url}: {str(e)}")
            logger.exception("Detailed exception info:")
            return {"success": False, "message": f"Error checking product: {str(e)}"}
    
    def save_status_to_file(self):
        """Save current product status to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Save to JSON for machine reading
            with open('popmart_status.json', 'w') as f:
                json.dump(self.product_status, f, indent=2)
                
            # Append to log file for human reading
            with open('popmart_status.txt', 'a') as f:
                f.write(f"\n{timestamp}\n")
                for product_id, product in self.product_status.items():
                    f.write(f"{product['title']}: {product['status']} - {product['price']}\n")
            
            logger.debug("Saved product status to files")
        except Exception as e:
            logger.error(f"Error saving status to file: {str(e)}")
    
    def run_monitoring_loop(self, check_interval=10):
        """Run the monitor in a continuous loop"""
        logger.info(f"Starting PopMart monitoring loop with {check_interval} second interval")
        
        try:
            while True:
                start_time = time.time()
                
                try:
                    self.check_all_monitored_products()
                    
                    # Save status to file
                    self.save_status_to_file()
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {str(e)}")
                
                # Calculate how long to wait until next check
                elapsed = time.time() - start_time
                wait_time = max(1, check_interval - elapsed)
                
                logger.info(f"Monitoring cycle completed in {elapsed:.2f}s, waiting {wait_time:.2f}s until next check")
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            # Clean up resources
            for url, driver in self.drivers.items():
                try:
                    driver.quit()
                    logger.debug(f"Closed driver for {url}")
                except Exception as e:
                    logger.error(f"Error closing driver for {url}: {str(e)}")
            
            if self.executor:
                self.executor.shutdown()
                logger.debug("Shut down thread pool")

# Example usage in worker.py:
# if __name__ == "__main__":
#     notification_bot_token = "YOUR_BOT_TOKEN"
#     monitor = PopMartFastMonitor(notification_bot_token)
#     monitor.run_monitoring_loop(check_interval=10)