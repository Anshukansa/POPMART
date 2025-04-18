import hashlib
import json
import time
import requests
import re
import logging
from database import Database
from notification_bot import NotificationBot
from requests.exceptions import HTTPError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("popmart_global_monitor.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class GlobalMonitor:
    def __init__(self, notification_bot_token):
        logger.info("Initializing GlobalMonitor")
        self.db = Database()  # Connect to your database
        self.notification_bot = NotificationBot(notification_bot_token)  # Connect to notification bot
        logger.info("GlobalMonitor initialized successfully")

    def extract_product_id_from_url(self, url):
        """Extract product ID from URL like https://www.popmart.com/au/products/938 or with trailing slash"""
        logger.debug(f"Extracting product ID from URL: {url}")
        
        # Updated pattern to handle URLs with or without trailing slash
        pattern = r'/products/(\d+)(?:/|$)'
        match = re.search(pattern, url)
        
        if match:
            product_id = match.group(1)
            logger.debug(f"Successfully extracted product ID: {product_id} from URL: {url}")
            return product_id
            
        if url and isinstance(url, str) and url.isdigit():
            logger.debug(f"URL is directly a numeric ID: {url}")
            return url  # If URL is directly an ID (like "938")
            
        logger.error(f"Could not extract product ID from URL: {url}")
        return None

    def generate_signature(self, params, timestamp, method="get"):
        """Generate the signature ('s' parameter) for PopMart API"""
        logger.debug(f"Generating signature for params: {params}, timestamp: {timestamp}")
        
        # Simplified signature generation (based on working code)
        salt = "W_ak^moHpMla"
        json_string = json.dumps(params, separators=(',', ':'))
        string_to_hash = f"{json_string}{salt}{timestamp}"
        signature = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
        
        logger.debug(f"Generated signature: {signature}")
        return signature

    def make_api_request_with_retry(self, endpoint, params, method="get", country="AU", language="en", retries=3):
        """Make an API request with retry logic"""
        logger.debug(f"Making API request to {endpoint} with retries={retries}")
        
        for attempt in range(retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{retries} for endpoint: {endpoint}")
                return self.make_api_request(endpoint, params, method, country, language)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error for {endpoint}: {str(e)}")
                if attempt < retries - 1:
                    retry_delay = 5
                    logger.debug(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Max retries reached for {endpoint}")
                
        logger.error(f"Failed after {retries} retries for endpoint: {endpoint}")
        return {"error": f"Failed after {retries} retries", "data": None}

    def make_api_request(self, endpoint, params, method="get", country="AU", language="en"):
        """Make an API request to PopMart API - Updated with working implementation"""
        base_url = "https://prod-global-api.popmart.com"
        url = f"{base_url}{endpoint}"
        
        logger.debug(f"Making {method.upper()} request to {url} with params: {params}")
        
        timestamp = str(int(time.time()))
        signature = self.generate_signature(params, timestamp, method)
        
        request_params = params.copy()
        request_params["s"] = signature
        request_params["t"] = timestamp
        
        # Updated headers based on working implementation
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": f"en-{country},en-US;q=0.9,en;q=0.8",
            "clientkey": "rmdxjisjk7gwykcix",
            "country": country,
            "language": language,
            "origin": "https://www.popmart.com",
            "referer": "https://www.popmart.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "x-client-country": country,
            "x-client-namespace": "eurasian", 
            "x-device-os-type": "web",
            "x-project-id": "eude"
        }
        
        logger.debug(f"Request headers: {headers}")
        
        try:
            if method.lower() == "get":
                logger.debug(f"Sending GET request to {url} with params: {request_params}")
                response = requests.get(url, params=request_params, headers=headers, timeout=10)
            else:
                logger.debug(f"Sending POST request to {url} with JSON body: {request_params}")
                response = requests.post(url, json=request_params, headers=headers, timeout=10)
            
            # Don't raise_for_status() - just try to parse JSON like the working version
            response_data = response.json()
            logger.debug(f"Received response: Status {response.status_code}")
            
            # Log any error messages from the API response
            if isinstance(response_data, dict) and response_data.get('code') != 200:
                logger.warning(f"API returned non-success code: {response_data.get('code')}, message: {response_data.get('message')}")
                
            return response_data
            
        except Exception as e:
            logger.error(f"Request Error: {str(e)}")
            # Log full details of the error for debugging
            logger.exception("Detailed exception info:")
            return {"error": str(e), "data": None}

    def get_product_stock_info(self, product_id_or_url, country="AU", language="en"):
        """Get stock information for a specific product - Updated with working implementation"""
        try:
            logger.info(f"Getting stock info for product: {product_id_or_url} in {country}")
            
            # Extract product ID from URL if necessary
            product_id = None
            if isinstance(product_id_or_url, str):
                if '/' in product_id_or_url:
                    # This is a URL, extract the product ID
                    product_id = self.extract_product_id_from_url(product_id_or_url)
                    logger.info(f"Extracted product ID {product_id} from URL {product_id_or_url}")
                else:
                    # This might be a direct product ID
                    product_id = product_id_or_url
                    logger.info(f"Using direct product ID: {product_id}")
            
            if not product_id:
                logger.error(f"Failed to determine product ID from: {product_id_or_url}")
                return None
                
            logger.info(f"Querying product details for ID: {product_id}")
            endpoint = "/shop/v1/shop/productDetails"
            params = {"spuId": product_id}
            
            details = self.make_api_request_with_retry(endpoint, params, country=country, language=language)
            
            if "error" in details:
                logger.error(f"Error getting product details: {details['error']}")
                return None
                
            if "data" not in details or not details["data"]:
                logger.error(f"No data returned for product {product_id}")
                return None
                
            product_data = details["data"]
            logger.debug(f"Received product data: {json.dumps(product_data, indent=2)[:500]}...")  # Log first 500 chars
            
            # Try to get stock information from different possible structures
            skus = product_data.get("skus", [])
            if not skus and "goods" in product_data:
                logger.debug("No 'skus' found, using 'goods' field instead")
                skus = product_data.get("goods", [])
                
            logger.debug(f"Found {len(skus)} SKUs for product {product_id}")
            
            # Log individual SKU stock information for debugging
            for i, sku in enumerate(skus):
                stock_info = sku.get("stock", {})
                online_stock = stock_info.get("onlineStock", 0)
                logger.debug(f"SKU #{i+1}: onlineStock={online_stock}, sku_id={sku.get('id', 'unknown')}")
                
            in_stock = any(sku.get("stock", {}).get("onlineStock", 0) > 0 for sku in skus)
            product_title = product_data.get("title", "Unknown")
            
            logger.info(f"Product '{product_title}' (ID: {product_id}) in_stock: {in_stock}")
            
            return {
                "product_id": product_id, 
                "title": product_title,
                "in_stock": in_stock,
                "skus": [
                    {
                        "sku_id": sku.get("id"),
                        "sku_title": sku.get("title"),
                        "sku_code": sku.get("skuCode"),
                        "price": sku.get("price"),
                        "discount_price": sku.get("discountPrice"),
                        "currency": sku.get("currency"),
                        "stock": sku.get("stock", {}).get("onlineStock", 0),
                        "lock_stock": sku.get("stock", {}).get("onlineLockStock", 0)
                    } for sku in skus
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting stock for product {product_id_or_url}: {str(e)}")
            logger.exception("Detailed exception info:")
            return None

    def check_all_monitored_products(self):
        """Check stock for all monitored products"""
        try:
            monitored_products = self.db.get_all_active_monitoring()
            
            if not monitored_products:
                logger.info("No products being monitored")
                return
                
            logger.info(f"Checking {len(monitored_products)} monitored products")
            
            for product in monitored_products:
                try:
                    # Log the full product data from database for debugging
                    logger.debug(f"Processing product from DB: {product}")
                    
                    # Ensure that we unpack only the expected number of columns
                    if len(product) < 3:
                        # Log or handle the incorrect columns appropriately
                        logger.warning(f"Skipping product due to unexpected data structure: {product}")
                        continue
                        
                    product_id_db, product_name, global_link = product[:3]  # Only unpack the first three values
                    
                    if not global_link:
                        logger.warning(f"No global link for product {product_name} (DB ID: {product_id_db})")
                        continue
                        
                    # Extract the proper product ID from the global link
                    product_id = self.extract_product_id_from_url(global_link)
                    
                    if not product_id:
                        logger.warning(f"Could not extract product ID from global link: {global_link}")
                        # Fall back to the database ID if we can't extract from URL
                        product_id = product_id_db
                        logger.info(f"Using database ID {product_id} as fallback")
                        
                    logger.info(f"Checking stock for {product_name} (ID: {product_id}, Link: {global_link})")
                    
                    # Use AU as country instead of GLOBAL (based on working code)
                    stock_info = self.get_product_stock_info(product_id, country="AU")
                    
                    if not stock_info:
                        logger.warning(f"[AU] Could not get stock info for {product_name} (ID: {product_id})")
                        continue
                        
                    is_in_stock = stock_info["in_stock"]
                    product_title = stock_info.get("title", product_name)
                    
                    # Log the details we're about to use for notification decisions
                    logger.debug(f"Product details: DB name={product_name}, API title={product_title}, in_stock={is_in_stock}")
                    
                    # Check if we should notify based on stock status change
                    should_notify = self.db.should_notify_stock_change(product_id, "AU", is_in_stock)
                    
                    if is_in_stock:
                        if should_notify:
                            logger.info(f"[AU] {product_name} is now in stock! Sending notifications.")
                            self.notification_bot.send_stock_notification(product_id, product_name, global_link, is_global=False)
                            logger.info(f"[AU] Notifications sent for {product_name}.")
                        else:
                            logger.info(f"[AU] {product_name} is still in stock. No notifications sent.")
                    else:
                        logger.info(f"[AU] {product_name} is out of stock.")
                        
                except Exception as e:
                    logger.error(f"Error processing product {product}: {str(e)}")
                    logger.exception("Detailed exception info:")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in check_all_monitored_products: {str(e)}")
            logger.exception("Detailed exception info:")

    def check_product(self, product_id_or_url):
        """Check stock for a specific product (for admin testing)"""
        logger.info(f"Admin testing stock check for: {product_id_or_url}")
        
        try:
            # Extract product ID from URL if necessary
            product_id = product_id_or_url
            if isinstance(product_id_or_url, str) and '/' in product_id_or_url:
                product_id = self.extract_product_id_from_url(product_id_or_url)
                logger.info(f"Extracted product ID: {product_id} from URL: {product_id_or_url}")
                
            if not product_id:
                logger.error(f"Invalid URL format, could not extract product ID: {product_id_or_url}")
                return {"success": False, "message": "Invalid URL format, could not extract product ID"}
                
            # Try to get product info from database
            product = self.db.get_product(product_id)
            product_name = product[1] if product else f"Product {product_id}"
            logger.info(f"Retrieved product from DB: {product_name} (ID: {product_id})")
            
            # Check stock status using the AU region
            stock_info = self.get_product_stock_info(product_id, country="AU")
            
            if not stock_info:
                logger.error(f"Could not check stock status for {product_id}")
                return {"success": False, "message": "Could not check stock status"}
                
            is_in_stock = stock_info["in_stock"]
            product_title = stock_info.get("title", "Unknown Product")
            
            # Format detailed SKU information for the dashboard
            sku_details = []
            for sku in stock_info.get("skus", []):
                price = f"{float(sku['price'])/100:.2f}" if sku.get('price') else "N/A"
                discount = f"{float(sku['discount_price'])/100:.2f}" if sku.get('discount_price') else "N/A"
                
                sku_details.append({
                    "title": sku.get('sku_title', 'Unknown'),
                    "id": sku.get('sku_id', 'Unknown'),
                    "code": sku.get('sku_code', 'Unknown'),
                    "price": f"{price} {sku.get('currency', 'AUD')}",
                    "discount": f"{discount} {sku.get('currency', 'AUD')}",
                    "stock": sku.get('stock', 0),
                    "locked_stock": sku.get('lock_stock', 0)
                })
            
            logger.info(f"Stock check result for {product_title} (ID: {product_id}): {'In Stock' if is_in_stock else 'Out of Stock'}")
            
            return {
                "success": True, 
                "product_name": product_name,
                "product_title": product_title, 
                "in_stock": is_in_stock,
                "sku_details": sku_details,
                "message": f"AU store: {'In Stock' if is_in_stock else 'Out of Stock'}"
            }
            
        except Exception as e:
            logger.error(f"Error in check_product for {product_id_or_url}: {str(e)}")
            logger.exception("Detailed exception info:")
            return {"success": False, "message": f"Error checking product: {str(e)}"}

# Example usage:
# notification_bot_token = "YOUR_BOT_TOKEN"
# global_monitor = GlobalMonitor(notification_bot_token)
# global_monitor.check_all_monitored_products()  # Checks all monitored products for stock statuss