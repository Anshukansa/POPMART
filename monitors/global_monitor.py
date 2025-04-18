import hashlib
import json
import time
import requests
import re
import logging
from database import Database
from notification_bot import NotificationBot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("popmart_global_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GlobalMonitor:
    def __init__(self, notification_bot_token):
        self.db = Database()
        self.notification_bot = NotificationBot(notification_bot_token)
    
    def extract_product_id_from_url(self, url):
        """Extract product ID from a URL like https://www.popmart.com/au/products/643/PRODUCT-NAME"""
        # Pattern to extract product ID from URLs like:
        # https://www.popmart.com/au/products/643/THE-MONSTERS---I-FOUND-YOU-Vinyl-Face-Doll
        pattern = r'/products/(\d+)/'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
        # If no match found, check if the URL might just be the ID
        if url.isdigit():
            return url
            
        # Try another pattern for direct product links
        pattern2 = r'product_id=(\d+)'
        match = re.search(pattern2, url)
        if match:
            return match.group(1)
            
        logger.error(f"Could not extract product ID from URL: {url}")
        return None
        
    def generate_signature(self, params, timestamp, method="get"):
        """Generate the signature ('s' parameter) for PopMart API"""
        # Process parameters based on method
        if method.lower() == "get":
            # For GET requests, filter out empty values
            filtered_params = {}
            for key, value in params.items():
                if value is not None and value != "":
                    filtered_params[key] = str(value)
        else:
            # For POST requests, use all parameters
            filtered_params = params.copy()
        
        # Sort object's keys recursively
        def sort_object(obj):
            if isinstance(obj, dict):
                return {k: sort_object(obj[k]) for k in sorted(obj.keys())}
            elif isinstance(obj, list):
                return [sort_object(item) for item in obj]
            else:
                return obj
        
        sorted_params = sort_object(filtered_params)
        
        # Generate the string to hash - using compact JSON
        salt = "W_ak^moHpMla"
        json_string = json.dumps(sorted_params, separators=(',', ':'))
        string_to_hash = f"{json_string}{salt}{timestamp}"
        
        # Calculate MD5 hash
        signature = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
        return signature

    def make_api_request(self, endpoint, params, method="get", country="GLOBAL", language="en"):
        """Make an API request to PopMart API"""
        base_url = "https://prod-global-api.popmart.com"
        url = f"{base_url}{endpoint}"
        
        # Generate timestamp
        timestamp = str(int(time.time()))
        
        # Generate signature
        signature = self.generate_signature(params, timestamp, method)
        
        # Add signature and timestamp to parameters
        request_params = params.copy()
        request_params["s"] = signature
        request_params["t"] = timestamp
        
        # Generate x-sign header
        client_key = "rmdxjisjk7gwykcix"
        x_sign_base = f"{timestamp},{client_key}"
        x_sign_hash = hashlib.md5(x_sign_base.encode('utf-8')).hexdigest()
        x_sign = f"{x_sign_hash},{timestamp}"
        
        # Set headers
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": f"en-{country},en-US;q=0.9,en;q=0.8",
            "clientkey": client_key,
            "country": country,
            "language": language,
            "origin": "https://www.popmart.com",
            "referer": "https://www.popmart.com/",
            "did": "g1Oeu7q3-59v6-m85u-945t-9vV3kUgBp03I",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "x-client-country": country,
            "x-client-namespace": "eurasian",
            "x-device-os-type": "web",
            "x-project-id": "eude",
            "x-sign": x_sign,
            "tz": f"Australia/Sydney"
        }
        
        try:
            if method.lower() == "get":
                response = requests.get(url, params=request_params, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=request_params, headers=headers, timeout=10)
            
            # Check if the response was successful
            response.raise_for_status()
            
            # Try to parse as JSON
            response_data = response.json()
            
            # Check if the API returned an error
            if isinstance(response_data, dict) and response_data.get("code") != 0 and response_data.get("code") != "OK":
                error_msg = response_data.get("msg", "Unknown API error")
                logger.error(f"API error: {error_msg} (Code: {response_data.get('code')})")
                return {"error": error_msg, "code": response_data.get("code"), "data": None}
            
            return response_data
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error for {endpoint}: {str(e)}")
            return {"error": f"HTTP Error: {str(e)}", "data": None}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error for {endpoint}: {str(e)}")
            return {"error": f"Connection Error: {str(e)}", "data": None}
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout Error for {endpoint}: {str(e)}")
            return {"error": f"Timeout Error: {str(e)}", "data": None}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error for {endpoint}: {str(e)}")
            return {"error": f"Request Error: {str(e)}", "data": None}
        except ValueError as e:
            logger.error(f"JSON Decode Error for {endpoint}: {str(e)}")
            return {"error": f"JSON Decode Error: {str(e)}", "data": None}
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {str(e)}")
            return {"error": f"Unexpected Error: {str(e)}", "data": None}

    def get_product_stock_info(self, product_id_or_url, country="GLOBAL", language="en"):
        """Get stock information for a specific product"""
        try:
            # Check if we have a URL or just an ID
            if isinstance(product_id_or_url, str) and '/' in product_id_or_url:
                product_id = self.extract_product_id_from_url(product_id_or_url)
                if not product_id:
                    return None
            else:
                product_id = str(product_id_or_url)
            
            endpoint = "/shop/v1/shop/productDetails"
            params = {"spuId": product_id}
            
            details = self.make_api_request(endpoint, params, country=country, language=language)
            
            if "error" in details:
                logger.error(f"Error getting product details for {product_id}: {details['error']}")
                return None
            
            if "data" not in details or not details["data"]:
                logger.error(f"No data returned for product {product_id}")
                return None
            
            product_data = details["data"]
            skus = product_data.get("skus", [])
            
            # Check if we need to look for skus in 'goods' instead
            if not skus and "goods" in product_data:
                skus = product_data.get("goods", [])
            
            in_stock = False
            for sku in skus:
                # Check the stock using the nested structure from the API
                stock = sku.get("stock", {}).get("onlineStock", 0)
                if stock > 0:
                    in_stock = True
                    break
            
            return {
                "product_id": product_id,
                "title": product_data.get("title", "Unknown"),
                "in_stock": in_stock
            }
        except Exception as e:
            logger.error(f"Error getting stock for product {product_id_or_url}: {str(e)}")
            return None

    def check_all_monitored_products(self):
        """Check stock for all monitored products"""
        monitored_products = self.db.get_all_active_monitoring()
        
        if not monitored_products:
            logger.info("No products being monitored")
            return
            
        logger.info(f"Checking {len(monitored_products)} monitored products")
        
        for product in monitored_products:
            product_id = product[0]
            product_name = product[1]
            global_link = product[2]
            
            if not product_id:
                continue
            
            # Check stock status - try extracting ID from URL if it's a URL
            stock_info = self.get_product_stock_info(product_id)
            
            if not stock_info:
                logger.warning(f"[GLOBAL] Could not get stock info for {product_name} (ID: {product_id})")
                continue
                
            is_in_stock = stock_info["in_stock"]
            
            # Check if we should send notifications (only if stock status changed to in-stock)
            should_notify = self.db.should_notify_stock_change(product_id, "GLOBAL", is_in_stock)
            
            if is_in_stock:
                if should_notify:
                    # Send notification only if stock status changed
                    self.notification_bot.send_stock_notification(
                        product_id, product_name, global_link, is_global=True
                    )
                    logger.info(f"[GLOBAL] {product_name} is now in stock! Notifications sent.")
                else:
                    logger.info(f"[GLOBAL] {product_name} is still in stock. No notifications sent.")
            else:
                logger.info(f"[GLOBAL] {product_name} is out of stock.")
                
    def check_product(self, product_id_or_url):
        """Check stock for a specific product (for admin testing)"""
        # Check if it's a URL and extract product ID if needed
        if isinstance(product_id_or_url, str) and '/' in product_id_or_url:
            product_id = self.extract_product_id_from_url(product_id_or_url)
            if not product_id:
                return {"success": False, "message": "Invalid URL format, could not extract product ID"}
        else:
            product_id = product_id_or_url

        # First try to get product from database
        product = self.db.get_product(product_id)
        
        # If in database, use the name from there
        if product:
            product_name = product[1]
        else:
            product_name = f"Product {product_id}"
        
        # Check stock status
        stock_info = self.get_product_stock_info(product_id)
        
        if not stock_info:
            return {"success": False, "message": "Could not check stock status"}
        
        is_in_stock = stock_info["in_stock"]
        product_title = stock_info.get("title", "Unknown Product")
        
        return {
            "success": True, 
            "product_name": product_name,
            "product_title": product_title,
            "in_stock": is_in_stock,
            "message": f"Global store: {'In Stock' if is_in_stock else 'Out of Stock'}"
        }