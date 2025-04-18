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
        self.db = Database()  # Connect to your database
        self.notification_bot = NotificationBot(notification_bot_token)  # Connect to notification bot

    def extract_product_id_from_url(self, url):
        """Extract product ID from URL like https://www.popmart.com/au/products/643/PRODUCT-NAME"""
        pattern = r'/products/(\d+)/'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        if url.isdigit():
            return url  # If URL is directly an ID (like "643")
        logger.error(f"Could not extract product ID from URL: {url}")
        return None

    def generate_signature(self, params, timestamp, method="get"):
        """Generate the signature ('s' parameter) for PopMart API"""
        if method.lower() == "get":
            filtered_params = {key: str(value) for key, value in params.items() if value}
        else:
            filtered_params = params.copy()

        def sort_object(obj):
            if isinstance(obj, dict):
                return {k: sort_object(obj[k]) for k in sorted(obj.keys())}
            elif isinstance(obj, list):
                return [sort_object(item) for item in obj]
            else:
                return obj
        
        sorted_params = sort_object(filtered_params)
        salt = "W_ak^moHpMla"
        json_string = json.dumps(sorted_params, separators=(',', ':'))
        string_to_hash = f"{json_string}{salt}{timestamp}"
        return hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()

    def make_api_request_with_retry(self, endpoint, params, method="get", country="GLOBAL", language="en", retries=3):
        """Make an API request with retry logic"""
        for attempt in range(retries):
            try:
                return self.make_api_request(endpoint, params, method, country, language)
            except HTTPError as e:
                logger.error(f"Attempt {attempt + 1}: HTTP Error for {endpoint}: {str(e)}")
                if attempt < retries - 1:
                    time.sleep(5)  # wait for 5 seconds before retrying
                else:
                    logger.error(f"Max retries reached for {endpoint}")
            except Exception as e:
                logger.error(f"Request Error for {endpoint}: {str(e)}")
                break
        return {"error": "Failed after retries", "data": None}

    def make_api_request(self, endpoint, params, method="get", country="GLOBAL", language="en"):
        """Make an API request to PopMart API"""
        base_url = "https://prod-global-api.popmart.com"
        url = f"{base_url}{endpoint}"
        timestamp = str(int(time.time()))
        signature = self.generate_signature(params, timestamp, method)
        
        request_params = params.copy()
        request_params["s"] = signature
        request_params["t"] = timestamp
        
        client_key = "rmdxjisjk7gwykcix"
        x_sign_base = f"{timestamp},{client_key}"
        x_sign_hash = hashlib.md5(x_sign_base.encode('utf-8')).hexdigest()
        x_sign = f"{x_sign_hash},{timestamp}"

        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": f"en-{country},en-US;q=0.9,en;q=0.8",
            "clientkey": client_key,
            "country": country,
            "language": language,
            "origin": "https://www.popmart.com",
            "referer": "https://www.popmart.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "x-sign": x_sign,
            "tz": "Australia/Sydney"
        }
        
        try:
            if method.lower() == "get":
                response = requests.get(url, params=request_params, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=request_params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error: {str(e)}")
            return {"error": str(e), "data": None}

    def get_product_stock_info(self, product_id_or_url, country="GLOBAL", language="en"):
        """Get stock information for a specific product"""
        try:
            product_id = product_id_or_url if isinstance(product_id_or_url, str) and not '/' in product_id_or_url else self.extract_product_id_from_url(product_id_or_url)
            if not product_id:
                return None
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
            skus = product_data.get("skus", [])
            if not skus and "goods" in product_data:
                skus = product_data.get("goods", [])
            in_stock = any(sku.get("stock", {}).get("onlineStock", 0) > 0 for sku in skus)
            return {"product_id": product_id, "title": product_data.get("title", "Unknown"), "in_stock": in_stock}
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
            if len(product) != 3:
                logger.warning(f"Skipping product due to unexpected data structure: {product}")
                continue
            product_id, product_name, global_link = product[:3]
            if not product_id:
                continue
            stock_info = self.get_product_stock_info(product_id)
            if not stock_info:
                logger.warning(f"[GLOBAL] Could not get stock info for {product_name} (ID: {product_id})")
                continue
            is_in_stock = stock_info["in_stock"]
            should_notify = self.db.should_notify_stock_change(product_id, "GLOBAL", is_in_stock)
            if is_in_stock:
                if should_notify:
                    self.notification_bot.send_stock_notification(product_id, product_name, global_link, is_global=True)
                    logger.info(f"[GLOBAL] {product_name} is now in stock! Notifications sent.")
                else:
                    logger.info(f"[GLOBAL] {product_name} is still in stock. No notifications sent.")
            else:
                logger.info(f"[GLOBAL] {product_name} is out of stock.")

    def check_product(self, product_id_or_url):
        """Check stock for a specific product (for admin testing)"""
        product_id = product_id_or_url if isinstance(product_id_or_url, str) and not '/' in product_id_or_url else self.extract_product_id_from_url(product_id_or_url)
        if not product_id:
            return {"success": False, "message": "Invalid URL format, could not extract product ID"}
        product = self.db.get_product(product_id)
        product_name = product[1] if product else f"Product {product_id}"
        stock_info = self.get_product_stock_info(product_id)
        if not stock_info:
            return {"success": False, "message": "Could not check stock status"}
        is_in_stock = stock_info["in_stock"]
        product_title = stock_info.get("title", "Unknown Product")
        return {"success": True, "product_name": product_name, "product_title": product_title, "in_stock": is_in_stock, "message": f"Global store: {'In Stock' if is_in_stock else 'Out of Stock'}"}

# Example usage:
# notification_bot_token = "YOUR_BOT_TOKEN"
# global_monitor = GlobalMonitor(notification_bot_token)
# global_monitor.check_all_monitored_products()  # Checks all monitored products for stock status
