import hashlib
import json
import time
import requests
from database import Database
from notification_bot import NotificationBot

class GlobalMonitor:
    def __init__(self, notification_bot_token):
        self.db = Database()
        self.notification_bot = NotificationBot(notification_bot_token)
        
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
                response = requests.get(url, params=request_params, headers=headers)
            else:
                response = requests.post(url, json=request_params, headers=headers)
            
            return response.json()
        except Exception as e:
            print(f"Error making request to {endpoint}: {str(e)}")
            return {"error": str(e)}

    def get_product_stock_info(self, product_id):
        """Get stock information for a specific product"""
        try:
            endpoint = "/shop/v1/shop/productDetails"
            params = {"spuId": str(product_id)}
            
            details = self.make_api_request(endpoint, params)
            
            if "data" not in details or not details["data"]:
                return None
            
            product_data = details["data"]
            skus = product_data.get("skus", [])
            
            in_stock = False
            for sku in skus:
                if sku.get("stock", {}).get("onlineStock", 0) > 0:
                    in_stock = True
                    break
            
            return {
                "product_id": product_id,
                "title": product_data.get("title", "Unknown"),
                "in_stock": in_stock
            }
        except Exception as e:
            print(f"Error getting stock for product {product_id}: {str(e)}")
            return None

    def check_all_monitored_products(self):
        """Check stock for all monitored products"""
        monitored_products = self.db.get_all_active_monitoring()
        
        for product in monitored_products:
            product_id = product[0]
            product_name = product[1]
            global_link = product[2]
            
            # Check stock status
            stock_info = self.get_product_stock_info(product_id)
            
            if stock_info and stock_info["in_stock"]:
                # Send notification
                self.notification_bot.send_stock_notification(
                    product_id, product_name, global_link, is_global=True
                )
                
                print(f"[GLOBAL] {product_name} is in stock! Notifications sent.")
            else:
                print(f"[GLOBAL] {product_name} is out of stock.")