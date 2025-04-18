import time
import json
import logging
import os
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
    handlers=[logging.FileHandler("popmart_selenium_monitor.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class SeleniumMonitor:
    """Monitor PopMart products using Selenium web scraping - Heroku compatible"""
    
    def __init__(self, notification_bot_token):
        logger.info("Initializing SeleniumMonitor")
        self.db = Database()  # Connect to your database
        self.notification_bot = NotificationBot(notification_bot_token)  # Connect to notification bot
        self.drivers = {}  # Will store one driver per URL
        self.product_status = {}  # Keep track of product statuses
        logger.info("SeleniumMonitor initialized successfully")
    
    def create_driver(self):
        """Create a Heroku-compatible Chrome driver with necessary options"""
        logger.debug("Creating new Chrome driver for Heroku")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        options = Options()
        
        # Check if running on Heroku (look for dyno environment)
        is_heroku = os.environ.get('DYNO') is not None
        
        if is_heroku:
            # REQUIRED for Heroku with new buildpack
            options.binary_location = os.environ.get("GOOGLE_CHROME_SHIM", None)
            if not options.binary_location:
                # Fall back to the old environment variable
                options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
                
            options.add_argument("--headless")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
        
        # Stealth settings to avoid detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Performance optimizations
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
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
        
        try:
            # Create the driver - with different approaches for Heroku vs local
            if is_heroku:
                # Get the chromedriver path from Heroku environment
                chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
                
                if chromedriver_path:
                    # Legacy approach
                    service = Service(executable_path=chromedriver_path)
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    # New approach - Chrome for Testing buildpack should handle paths
                    driver = webdriver.Chrome(options=options)
            else:
                # Local development - use webdriver_manager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            
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
        
        except Exception as e:
            logger.error(f"Failed to create driver: {str(e)}")
            raise
    
    def extract_product_id_from_url(self, url):
        """Extract product ID from URL for database operations"""
        try:
            # Extract product ID from URL (e.g., 'https://www.popmart.com/au/products/938')
            return url.strip().split('/')[-1].split('%')[0]
        except Exception as e:
            logger.error(f"Error extracting product ID from URL {url}: {str(e)}")
            return None
    
    def check_product(self, url, db_product_id, product_name):
        """Check a single product with early termination once data is found"""
        logger.info(f"Checking product: {product_name} (ID: {db_product_id}, URL: {url})")
        
        # Create driver if it doesn't exist
        if url not in self.drivers:
            try:
                self.drivers[url] = self.create_driver()
            except Exception as e:
                logger.error(f"Error creating driver for {url}: {str(e)}")
                return {
                    "db_product_id": db_product_id,
                    "title": product_name,
                    "price": "Unknown",
                    "status": "ERROR",
                    "in_stock": False,
                    "url": url,
                    "error": f"Driver creation failed: {str(e)}"
                }
        
        driver = self.drivers[url]
        
        try:
            # Navigate to the URL
            driver.get(url)
            
            # Inject early termination script
            early_termination_script = """
                let titleFound = false;
                let priceFound = false;
                let stockStatusFound = false;
                
                const observer = new MutationObserver(function(mutations) {
                    if (!titleFound && document.querySelector('h1.index_title___0OsZ')) {
                        titleFound = true;
                    }
                    
                    if (!priceFound && document.querySelector('div.index_price__cAj0h')) {
                        priceFound = true;
                    }
                    
                    if (!stockStatusFound && 
                        (document.querySelector('div.index_euBtn__7NmZ6, div.index_btn__w5nKF'))) {
                        stockStatusFound = true;
                    }
                    
                    if (titleFound && priceFound && stockStatusFound) {
                        window.stop();
                        observer.disconnect();
                    }
                });
                
                observer.observe(document.documentElement, {
                    childList: true,
                    subtree: true
                });
            """
            
            driver.execute_script(early_termination_script)
            
            # Wait for the title element with a short timeout
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.index_title___0OsZ"))
                )
            except Exception as e:
                logger.warning(f"Timeout waiting for title element: {str(e)}")
                return {
                    "db_product_id": db_product_id,
                    "title": product_name,
                    "price": "Unknown",
                    "status": "ERROR",
                    "in_stock": False,
                    "url": url,
                    "error": "Page load timeout"
                }
            
            # Extract data
            try:
                title = driver.find_element(By.CSS_SELECTOR, "h1.index_title___0OsZ").text
            except:
                title = product_name
            
            try:
                price = driver.find_element(By.CSS_SELECTOR, "div.index_price__cAj0h").text
            except:
                price = "Unknown Price"
            
            # Multiple ways to check for stock status
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
                # Fallback JavaScript check
                buttons_js = driver.execute_script("""
                    const addToCartBtn = document.querySelector('div.index_euBtn__7NmZ6');
                    if (addToCartBtn && addToCartBtn.textContent.includes('ADD TO CART')) return 'IN STOCK';
                    
                    const notifyBtn = document.querySelector('div.index_btn__w5nKF'); 
                    if (notifyBtn && notifyBtn.textContent.includes('NOTIFY ME WHEN AVAILABLE')) return 'OUT OF STOCK';
                    
                    return 'UNKNOWN';
                """)
                
                status = buttons_js
                in_stock = status == "IN STOCK"
            
            logger.info(f"Stock check for {title}: {status} at {price}")
            
            return {
                "db_product_id": db_product_id,
                "title": title,
                "price": price,
                "status": status,
                "in_stock": in_stock,
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error checking {url}: {str(e)}")
            return {
                "db_product_id": db_product_id,
                "title": product_name,
                "price": "Unknown",
                "status": "ERROR",
                "in_stock": False,
                "url": url,
                "error": str(e)
            }
    
    def check_all_monitored_products(self):
        """Check stock for all monitored products"""
        try:
            monitored_products = self.db.get_all_active_monitoring()
            
            if not monitored_products:
                logger.info("No products being monitored")
                return []
                
            logger.info(f"Checking {len(monitored_products)} monitored products")
            
            # Create a thread pool with one thread per product
            with ThreadPoolExecutor(max_workers=len(monitored_products)) as executor:
                futures = []
                
                for product in monitored_products:
                    # Ensure that we unpack only the expected number of columns
                    if len(product) < 3:
                        logger.warning(f"Skipping product due to unexpected data structure: {product}")
                        continue
                        
                    db_product_id, product_name, global_link = product[:3]  # Only unpack the first three values
                    
                    if not global_link:
                        logger.warning(f"No global link for product {product_name} (DB ID: {db_product_id})")
                        continue
                    
                    # Submit the task to the thread pool
                    future = executor.submit(self.check_product, global_link, db_product_id, product_name)
                    futures.append(future)
                
                # Get results from all threads
                results = [future.result() for future in futures]
            
            # Process results and update database/send notifications
            for result in results:
                if result.get("status") == "ERROR":
                    logger.warning(f"Error checking {result.get('title', 'Unknown')}: {result.get('error', 'Unknown error')}")
                    continue
                
                db_product_id = result.get("db_product_id")
                product_name = result.get("title")
                in_stock = result.get("in_stock", False)
                
                # Check if we should notify based on stock status change
                should_notify = self.db.should_notify_stock_change(db_product_id, "AU", in_stock)
                
                if in_stock:
                    if should_notify:
                        logger.info(f"[AU] {product_name} is now in stock! Sending notifications.")
                        self.notification_bot.send_stock_notification(db_product_id, product_name, result.get("url"), is_global=False)
                        logger.info(f"[AU] Notifications sent for {product_name}.")
                    else:
                        logger.info(f"[AU] {product_name} is still in stock. No notifications sent.")
                else:
                    logger.info(f"[AU] {product_name} is out of stock.")
            
            return results
                
        except Exception as e:
            logger.error(f"Error in check_all_monitored_products: {str(e)}")
            logger.exception("Detailed exception info:")
            return []
    
    def check_product_stock(self, product_id):
        """Check stock for a specific product (for admin testing)"""
        logger.info(f"Admin testing stock check for: {product_id}")
        
        try:
            # Try to get product info from database
            product = self.db.get_product(product_id)
            if not product:
                logger.warning(f"Product not found in database: {product_id}")
                return {"success": False, "message": "Product not found in database"}
                
            product_name = product[1] if len(product) > 1 else f"Product {product_id}"
            global_link = product[2] if len(product) > 2 else None
            
            if not global_link:
                logger.error(f"No global link for product {product_name} (ID: {product_id})")
                return {"success": False, "message": "No global link found for product"}
            
            logger.info(f"Retrieved product from DB: {product_name} (ID: {product_id}, Link: {global_link})")
            
            # Check the product
            result = self.check_product(global_link, product_id, product_name)
            
            if result.get("status") == "ERROR":
                logger.error(f"Error checking stock for {product_name}: {result.get('error', 'Unknown error')}")
                return {"success": False, "message": f"Error checking stock: {result.get('error', 'Unknown error')}"}
            
            in_stock = result.get("in_stock", False)
            product_title = result.get("title", product_name)
            price = result.get("price", "Unknown Price")
            
            logger.info(f"Stock check result for {product_title} (ID: {product_id}): {'In Stock' if in_stock else 'Out of Stock'}")
            
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
            logger.error(f"Error in check_product_stock for {product_id}: {str(e)}")
            logger.exception("Detailed exception info:")
            return {"success": False, "message": f"Error checking product: {str(e)}"}
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up SeleniumMonitor resources")
        
        for url, driver in self.drivers.items():
            try:
                driver.quit()
                logger.debug(f"Closed driver for {url}")
            except Exception as e:
                logger.error(f"Error closing driver for {url}: {str(e)}")