"""
Monitoring script for Popmart Global API
"""
import hashlib
import json
import time
import requests
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

def generate_signature(params, timestamp, method="get"):
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

def make_api_request(endpoint, params, method="get", country="AU", language="en"):
    """Make an API request to PopMart API"""
    base_url = "https://prod-global-api.popmart.com"
    url = f"{base_url}{endpoint}"
    
    # Generate timestamp
    timestamp = str(int(time.time()))
    
    # Generate signature
    signature = generate_signature(params, timestamp, method)
    
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
        logger.info(f"Making API request to {endpoint} with params: {params}")
        if method.lower() == "get":
            response = requests.get(url, params=request_params, headers=headers)
        else:
            response = requests.post(url, json=request_params, headers=headers)
        
        return response.json()
    except Exception as e:
        logger.error(f"Error making request to {endpoint}: {str(e)}")
        return {"error": str(e)}

def get_product_details(spu_id, country="AU", language="en"):
    """Get detailed information about a specific product"""
    endpoint = "/shop/v1/shop/productDetails"
    params = {"spuId": str(spu_id)}
    
    return make_api_request(endpoint, params, country=country, language=language)

def extract_product_id_from_url(url):
    """Extract product ID from a Popmart Global URL"""
    if not url:
        logger.warning("No URL provided to extract product ID")
        return None
    
    try:
        logger.info(f"Extracting product ID from URL: {url}")
        
        # Original format: https://www.popmart.com/goods/detail?spuId=938
        if "spuId=" in url:
            spu_id = url.split("spuId=")[1].split("&")[0]
            logger.info(f"Extracted product ID: {spu_id}")
            return spu_id
            
        # New format: https://www.popmart.com/au/products/643/THE-MONSTERS...
        elif "/products/" in url:
            # Extract the ID that comes after /products/ and before the next /
            parts = url.split("/products/")[1].split("/")
            if parts and parts[0].isdigit():
                spu_id = parts[0]
                logger.info(f"Extracted product ID: {spu_id}")
                return spu_id
        
        logger.warning(f"Could not extract product ID from URL: {url}")
    except Exception as e:
        logger.error(f"Error extracting product ID from URL: {e}")
    
    return None

def get_product_stock_info(product_id, country="AU", language="en"):
    """Get detailed stock information for a specific product"""
    try:
        logger.info(f"Getting stock info for product ID {product_id}")
        details = get_product_details(product_id, country, language)
        
        if "data" not in details or not details["data"]:
            logger.warning(f"No data found for product ID {product_id}")
            return {
                "product_id": product_id,
                "title": "Unknown",
                "status": "Error fetching details",
                "sku_count": 0,
                "skus": [],
                "in_stock": False
            }
        
        product_data = details["data"]
        skus = product_data.get("skus", [])
        
        sku_info = []
        any_in_stock = False
        
        for sku in skus:
            stock = sku.get("stock", {}).get("onlineStock", 0)
            if stock > 0:
                any_in_stock = True
            
            price = sku.get("price", 0)
            discount_price = sku.get("discountPrice", 0)
            price_str = f"{float(price)/100:.2f}" if price else "N/A"
            discount_str = f"{float(discount_price)/100:.2f}" if discount_price else "N/A"
            
            logger.info(f"SKU: {sku.get('title')} (ID: {sku.get('id')})")
            logger.info(f"  Code: {sku.get('skuCode')}")
            logger.info(f"  Price: {price_str} {sku.get('currency')} (Discount: {discount_str} {sku.get('currency')})")
            logger.info(f"  Stock: {stock} (Locked: {sku.get('stock', {}).get('onlineLockStock', 0)})")
            
            sku_info.append({
                "sku_id": sku.get("id"),
                "sku_title": sku.get("title"),
                "sku_code": sku.get("skuCode"),
                "price": price,
                "discount_price": discount_price,
                "currency": sku.get("currency"),
                "stock": stock,
                "lock_stock": sku.get("stock", {}).get("onlineLockStock", 0)
            })
        
        result = {
            "product_id": product_id,
            "title": product_data.get("title", "Unknown"),
            "brand": product_data.get("brand", {}).get("name"),
            "publish_status": "Published" if product_data.get("isPublish") else "Not Published",
            "availability": "Available" if product_data.get("isAvailable") else "Not Available",
            "sku_count": len(skus),
            "skus": sku_info,
            "in_stock": any_in_stock
        }
        
        logger.info(f"Product: {result['title']} (ID: {result['product_id']})")
        logger.info(f"Brand: {result.get('brand', 'Unknown')}")
        logger.info(f"Status: {result.get('publish_status', 'Unknown')} / {result.get('availability', 'Unknown')}")
        logger.info(f"SKUs: {result['sku_count']}")
        logger.info(f"In Stock: {result['in_stock']}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting stock for product {product_id}: {str(e)}", exc_info=True)
        return {
            "product_id": product_id,
            "title": "Error",
            "status": str(e),
            "sku_count": 0,
            "skus": [],
            "in_stock": False
        }

def check_product_stock(product_id, country="AU"):
    """Check if a product is in stock"""
    if not product_id:
        logger.warning("No product ID provided for stock check")
        return False
    
    try:
        result = get_product_stock_info(product_id, country)
        return result["in_stock"]
    
    except Exception as e:
        logger.error(f"Error checking stock for product {product_id}: {str(e)}", exc_info=True)
        return False

# The following functions are for running the monitoring asynchronously

async def check_product_async(monitor):
    """Check a single product asynchronously"""
    try:
        # Only check Global link - using dictionary-style access for sqlite3.Row
        global_link = monitor['global_link'] if 'global_link' in monitor else None
        if not global_link:
            return
            
        product_id = extract_product_id_from_url(global_link)
        
        if not product_id:
            logger.warning(f"Could not extract product ID from URL: {global_link}")
            return
            
        # Use the same approach as in test.py
        logger.info(f"Getting detailed stock info for product ID: {product_id}")
        
        # Get product details directly
        details = get_product_details(product_id)
        
        if "data" not in details or not details["data"]:
            logger.info(f"Product {monitor['product_name']} (ID: {product_id}) - No data found from API")
            logger.info(f"Product {monitor['product_name']} is OUT OF STOCK on Global (no data)")
            return
            
        product_data = details["data"]
        skus = product_data.get("skus", [])
        
        any_in_stock = False
        
        # Log each SKU exactly as in test.py
        for sku in skus:
            stock = sku.get("stock", {}).get("onlineStock", 0)
            if stock > 0:
                any_in_stock = True
            
            price = sku.get("price", 0)
            discount_price = sku.get("discountPrice", 0)
            price_str = f"{float(price)/100:.2f}" if price else "N/A"
            discount_str = f"{float(discount_price)/100:.2f}" if discount_price else "N/A"
            
            logger.info(f"SKU: {sku.get('title')} (ID: {sku.get('id')})")
            logger.info(f"  Code: {sku.get('skuCode')}")
            logger.info(f"  Price: {price_str} {sku.get('currency')} (Discount: {discount_str} {sku.get('currency')})")
            logger.info(f"  Stock: {stock} (Locked: {sku.get('stock', {}).get('onlineLockStock', 0)})")
        
        logger.info(f"Product: {product_data.get('title', 'Unknown')} (ID: {product_id})")
        logger.info(f"Brand: {product_data.get('brand', {}).get('name', 'Unknown')}")
        logger.info(f"Status: {'Published' if product_data.get('isPublish') else 'Not Published'} / {'Available' if product_data.get('isAvailable') else 'Not Available'}")
        logger.info(f"SKUs: {len(skus)}")
        
        # Add our own clear stock status message
        if any_in_stock:
            logger.info(f"ALERT: Product {monitor['product_name']} is IN STOCK on Global!")
            await notify_users_about_stock(monitor['product_id'], "Global", global_link)
        else:
            logger.info(f"Product {monitor['product_name']} is OUT OF STOCK on Global")
            
    except Exception as e:
        product_name = monitor['product_name'] if 'product_name' in monitor else 'unknown'
        logger.error(f"Error checking product {product_name}: {str(e)}", exc_info=True)
        logger.info(f"Product {product_name} stock check FAILED due to error")

async def check_all_products():
    """Check all products for stock and notify users"""
    try:
        monitors = db.get_all_active_monitors()
        logger.info(f"Checking {len(monitors)} products for Global stock")
        
        found_global_links = False
        
        # Process each product sequentially (can be made parallel if needed)
        for monitor in monitors:
            # Make sure we're accessing the link correctly
            global_link = monitor.get('global_link', '') if isinstance(monitor, dict) else monitor['global_link']
            
            # Debug the link value
            logger.info(f"Product: {monitor['product_name']}, Global link value: '{global_link}'")
            
            # Less strict check - if there's any value, try to extract the ID
            if global_link and global_link.strip():
                found_global_links = True
                logger.info(f"Checking global stock for: {monitor['product_name']} ({global_link})")
                
                # REPLACED CALL TO check_product_async WITH THE FUNCTION'S IMPLEMENTATION
                try:
                    # Only check Global link - using dictionary-style access for sqlite3.Row
                    if not global_link:
                        continue
                        
                    product_id = extract_product_id_from_url(global_link)
                    
                    if not product_id:
                        logger.warning(f"Could not extract product ID from URL: {global_link}")
                        continue
                        
                    # Use the same approach as in test.py
                    logger.info(f"Getting detailed stock info for product ID: {product_id}")
                    
                    # Get product details directly
                    details = get_product_details(product_id)
                    
                    if "data" not in details or not details["data"]:
                        logger.info(f"Product {monitor['product_name']} (ID: {product_id}) - No data found from API")
                        logger.info(f"Product {monitor['product_name']} is OUT OF STOCK on Global (no data)")
                        continue
                        
                    product_data = details["data"]
                    skus = product_data.get("skus", [])
                    
                    any_in_stock = False
                    
                    # Log each SKU exactly as in test.py
                    for sku in skus:
                        stock = sku.get("stock", {}).get("onlineStock", 0)
                        if stock > 0:
                            any_in_stock = True
                        
                        price = sku.get("price", 0)
                        discount_price = sku.get("discountPrice", 0)
                        price_str = f"{float(price)/100:.2f}" if price else "N/A"
                        discount_str = f"{float(discount_price)/100:.2f}" if discount_price else "N/A"
                        
                        logger.info(f"SKU: {sku.get('title')} (ID: {sku.get('id')})")
                        logger.info(f"  Code: {sku.get('skuCode')}")
                        logger.info(f"  Price: {price_str} {sku.get('currency')} (Discount: {discount_str} {sku.get('currency')})")
                        logger.info(f"  Stock: {stock} (Locked: {sku.get('stock', {}).get('onlineLockStock', 0)})")
                    
                    logger.info(f"Product: {product_data.get('title', 'Unknown')} (ID: {product_id})")
                    logger.info(f"Brand: {product_data.get('brand', {}).get('name', 'Unknown')}")
                    logger.info(f"Status: {'Published' if product_data.get('isPublish') else 'Not Published'} / {'Available' if product_data.get('isAvailable') else 'Not Available'}")
                    logger.info(f"SKUs: {len(skus)}")
                    
                    # Add our own clear stock status message
                    if any_in_stock:
                        logger.info(f"ALERT: Product {monitor['product_name']} is IN STOCK on Global!")
                        await notify_users_about_stock(monitor['product_id'], "Global", global_link)
                    else:
                        logger.info(f"Product {monitor['product_name']} is OUT OF STOCK on Global")
                        
                except Exception as e:
                    product_name = monitor['product_name'] if 'product_name' in monitor else 'unknown'
                    logger.error(f"Error checking product {product_name}: {str(e)}", exc_info=True)
                    logger.info(f"Product {product_name} stock check FAILED due to error")
            
        if not found_global_links:
            logger.warning("No products with Global links found in database")
    except Exception as e:
        logger.error(f"Error checking Global products: {str(e)}", exc_info=True)
        
async def run_monitoring_loop():
    """Run continuous monitoring loop"""
    logger.info("Starting Popmart Global monitoring")
    
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
        # Create new event loop for this thread
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        
        # Run the monitoring loop
        new_loop.run_until_complete(run_monitoring_loop())
    except Exception as e:
        logger.error(f"Error starting monitoring: {str(e)}")

if __name__ == "__main__":
    start_monitoring()