import hashlib
import json
import time
import requests
import csv
from concurrent.futures import ThreadPoolExecutor
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("popmart_debug.log"),
        logging.StreamHandler()
    ]
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
    salt = "W_ak^moHpMla"  # This salt might need to be updated if the API changed
    json_string = json.dumps(sorted_params, separators=(',', ':'))
    string_to_hash = f"{json_string}{salt}{timestamp}"
    
    # Calculate MD5 hash
    signature = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
    return signature

def make_api_request(endpoint, params, method="get", country="AU", language="en", debug=False):
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
    client_key = "rmdxjisjk7gwykcix"  # This key might need to be updated
    x_sign_base = f"{timestamp},{client_key}"
    x_sign_hash = hashlib.md5(x_sign_base.encode('utf-8')).hexdigest()
    x_sign = f"{x_sign_hash},{timestamp}"
    
    # Set headers - Update potentially expired values
    # You might need to update the 'did' value from browser inspection
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": f"en-{country},en-US;q=0.9,en;q=0.8",
        "clientkey": client_key,
        "country": country,
        "language": language,
        "origin": "https://www.popmart.com",
        "referer": "https://www.popmart.com/",
        "did": "g1Oeu7q3-59v6-m85u-945t-9vV3kUgBp03I",  # This might need updating
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "x-client-country": country,
        "x-client-namespace": "eurasian",
        "x-device-os-type": "web",
        "x-project-id": "eude",
        "x-sign": x_sign,
        "tz": "Australia/Sydney"
    }
    
    if debug:
        logger.info(f"Making {method.upper()} request to: {url}")
        logger.info(f"Headers: {json.dumps(headers, indent=2)}")
        logger.info(f"Params: {json.dumps(request_params, indent=2)}")
    
    try:
        if method.lower() == "get":
            response = requests.get(url, params=request_params, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=request_params, headers=headers, timeout=10)
        
        if debug:
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response content: {response.text[:1000]}...")  # Log first 1000 chars
        
        # Check if the response was successful
        response.raise_for_status()
        
        # Try to parse as JSON
        response_data = response.json()
        
        # Check if the API returned an error
        # PopMart API returns "OK" for success, not 0
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
        # Try to log the actual response text
        try:
            logger.error(f"Response content: {response.text[:500]}...")
        except:
            pass
        return {"error": f"JSON Decode Error: {str(e)}", "data": None}
    except Exception as e:
        logger.error(f"Unexpected error for {endpoint}: {str(e)}")
        return {"error": f"Unexpected Error: {str(e)}", "data": None}

def get_product_list(category_id=None, page=1, page_size=100, country="AU", language="en", debug=False):
    """Get a list of products with pagination"""
    endpoint = "/shop/v1/shop/productList"
    params = {
        "page": str(page),
        "size": str(page_size)
    }
    
    if category_id:
        params["categoryId"] = str(category_id)
    
    return make_api_request(endpoint, params, country=country, language=language, debug=debug)

def get_product_details(spu_id, country="AU", language="en", debug=False):
    """Get detailed information about a specific product"""
    endpoint = "/shop/v1/shop/productDetails"
    params = {"spuId": str(spu_id)}
    
    return make_api_request(endpoint, params, country=country, language=language, debug=debug)

def get_all_category_ids(country="AU", language="en", debug=False):
    """Get all available category IDs"""
    endpoint = "/shop/v1/shop/indexCarousel"
    
    response = make_api_request(endpoint, {}, country=country, language=language, debug=debug)
    
    category_ids = []
    try:
        for item in response.get("data", {}).get("category", []):
            category_ids.append(item.get("id"))
    except Exception as e:
        logger.error(f"Error extracting category IDs: {str(e)}")
    
    return category_ids

def test_api_connection(country="AU", language="en"):
    """Test the API connection with a simple request"""
    logger.info("Testing API connection...")
    
    # First test the category endpoint
    response = get_all_category_ids(country, language, debug=True)
    
    if isinstance(response, list) and response:
        logger.info(f"Successfully retrieved {len(response)} categories")
    else:
        logger.error("Failed to retrieve categories")
    
    # Then test the product list endpoint
    response = get_product_list(None, 1, 1, country, language, debug=True)
    
    if "error" in response:
        logger.error(f"Product list test failed: {response['error']}")
        return False
    
    if response.get("data") and response.get("data").get("results"):
        products = response.get("data").get("results")
        logger.info(f"Successfully retrieved {len(products)} products")
        
        # If we have a product, get its ID for the detail test
        if products:
            product_id = products[0].get("id")
            logger.info(f"Testing product details with ID: {product_id}")
            
            detail_response = get_product_details(product_id, country, language, debug=True)
            
            if "error" in detail_response:
                logger.error(f"Product details test failed: {detail_response['error']}")
                return False
            
            if detail_response.get("data"):
                logger.info(f"Successfully retrieved details for product {product_id}")
                return True
    
    logger.error("API tests failed")
    return False

def get_stock_by_id(product_id, country="AU", language="en", debug=False):
    """Check stock for a specific product and print details"""
    logger.info(f"Getting stock information for product ID {product_id} in {country}...")
    
    result = get_product_stock_info(product_id, country, language, debug)
    
    print(f"\nProduct: {result.get('title', 'Unknown')} (ID: {result.get('product_id', 'Unknown')})")
    print(f"Brand: {result.get('brand', 'Unknown')}")
    
    if "error" in result:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return result
    
    print(f"Status: {result.get('publish_status', 'Unknown')} / {result.get('availability', 'Unknown')}")
    print(f"SKUs: {result.get('sku_count', 0)}")
    
    for sku in result.get("skus", []):
        price = f"{float(sku.get('price', 0))/100:.2f}" if sku.get('price') else "N/A"
        discount = f"{float(sku.get('discount_price', 0))/100:.2f}" if sku.get('discount_price') else "N/A"
        
        print(f"\n  SKU: {sku.get('sku_title', 'Unknown')} (ID: {sku.get('sku_id', 'Unknown')})")
        print(f"  Code: {sku.get('sku_code', 'Unknown')}")
        print(f"  Price: {price} {sku.get('currency', '')} (Discount: {discount} {sku.get('currency', '')})")
        print(f"  Stock: {sku.get('stock', 'Unknown')} (Locked: {sku.get('lock_stock', 'Unknown')})")
    
    return result

def get_product_stock_info(product_id, country="AU", language="en", debug=False):
    """Get stock information for a specific product"""
    try:
        details = get_product_details(product_id, country, language, debug)
        
        if "error" in details:
            return {
                "product_id": product_id,
                "title": "Unknown",
                "error": details.get("error", "Unknown error"),
                "sku_count": 0,
                "skus": []
            }
        
        if "data" not in details or not details["data"]:
            return {
                "product_id": product_id,
                "title": "Unknown",
                "error": "No data returned from API",
                "sku_count": 0,
                "skus": []
            }
        
        # Log the response structure for debugging
        if debug:
            logger.info(f"Product data keys: {list(details['data'].keys())}")
            
        product_data = details["data"]
        
        # The API might not return 'skus' directly, let's check if it's nested
        skus = product_data.get("skus", [])
        
        # If no skus found but there's a 'goods' key, try to get them from there
        if not skus and "goods" in product_data:
            skus = product_data.get("goods", [])
        
        sku_info = []
        for sku in skus:
            sku_info.append({
                "sku_id": sku.get("id"),
                "sku_title": sku.get("title"),
                "sku_code": sku.get("skuCode"),
                "price": sku.get("price"),
                "discount_price": sku.get("discountPrice"),
                "currency": sku.get("currency"),
                "stock": sku.get("stock", {}).get("onlineStock", 0),
                "lock_stock": sku.get("stock", {}).get("onlineLockStock", 0)
            })
        
        # Build brand information - it could be a string or an object
        brand_info = "Unknown"
        if isinstance(product_data.get("brand"), dict):
            brand_info = product_data.get("brand", {}).get("name", "Unknown")
        elif isinstance(product_data.get("brand"), str):
            brand_info = product_data.get("brand")
        elif isinstance(product_data.get("brandId"), (str, int)):
            brand_info = f"Brand ID: {product_data.get('brandId')}"
            
        # Handle different ways to determine publish status
        publish_status = "Unknown"
        if "isPublish" in product_data:
            publish_status = "Published" if product_data.get("isPublish") else "Not Published"
        elif "show" in product_data:
            publish_status = "Published" if product_data.get("show") else "Not Published"
            
        # Handle different ways to determine availability
        availability = "Unknown"
        if "isAvailable" in product_data:
            availability = "Available" if product_data.get("isAvailable") else "Not Available"
        elif "isHot" in product_data:
            availability = "Available (Hot)" if product_data.get("isHot") else "Available"
            
        return {
            "product_id": product_id,
            "title": product_data.get("title", "Unknown"),
            "brand": brand_info,
            "publish_status": publish_status,
            "availability": availability,
            "sku_count": len(skus),
            "skus": sku_info
        }
    except Exception as e:
        logger.error(f"Error getting stock for product {product_id}: {str(e)}")
        return {
            "product_id": product_id,
            "title": "Error",
            "error": str(e),
            "sku_count": 0,
            "skus": []
        }

if __name__ == "__main__":
    print("PopMart Stock Checker")
    print("====================")
    print("1. Check stock for a specific product")
    print("2. Check stock for all products")
    print("3. Test API connection")
    print("4. Check stock for product 938 in AU")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == "1":
        product_id = input("Enter product ID: ")
        country = input("Enter country code (default: AU): ") or "AU"
        debug = input("Enable debug mode? (y/n, default: n): ").lower() == 'y'
        get_stock_by_id(product_id, country, debug=debug)
    elif choice == "2":
        country = input("Enter country code (default: AU): ") or "AU"
        debug = input("Enable debug mode? (y/n, default: n): ").lower() == 'y'
        # Your existing check_all_stock function would need to be updated to use debug parameter
        print("Feature not updated yet")
    elif choice == "3":
        country = input("Enter country code (default: AU): ") or "AU"
        test_api_connection(country)
    elif choice == "4":
        print("Checking stock for product ID 938 in AU...")
        get_stock_by_id("938", "AU", debug=True)
    else:
        print("Exiting...")