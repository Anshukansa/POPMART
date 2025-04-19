import hashlib
import json
import time
import requests
import csv
from concurrent.futures import ThreadPoolExecutor

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
        if method.lower() == "get":
            response = requests.get(url, params=request_params, headers=headers)
        else:
            response = requests.post(url, json=request_params, headers=headers)
        
        return response.json()
    except Exception as e:
        print(f"Error making request to {endpoint}: {str(e)}")
        return {"error": str(e)}

def get_product_list(category_id=None, page=1, page_size=100, country="AU", language="en"):
    """Get a list of products with pagination"""
    endpoint = "/shop/v1/shop/productList"
    params = {
        "page": str(page),
        "size": str(page_size)
    }
    
    if category_id:
        params["categoryId"] = str(category_id)
    
    return make_api_request(endpoint, params, country=country, language=language)

def get_product_details(spu_id, country="AU", language="en"):
    """Get detailed information about a specific product"""
    endpoint = "/shop/v1/shop/productDetails"
    params = {"spuId": str(spu_id)}
    
    return make_api_request(endpoint, params, country=country, language=language)

def get_all_category_ids(country="AU", language="en"):
    """Get all available category IDs"""
    endpoint = "/shop/v1/shop/indexCarousel"
    
    response = make_api_request(endpoint, {}, country=country, language=language)
    
    category_ids = []
    try:
        for item in response.get("data", {}).get("category", []):
            category_ids.append(item.get("id"))
    except:
        print("Error extracting category IDs")
    
    return category_ids

def get_all_products(country="AU", language="en"):
    """
    Get all products by iterating through all pages and categories
    Returns a list of product IDs
    """
    all_product_ids = set()
    
    # Try with no category first (all products)
    page = 1
    while True:
        print(f"Fetching page {page} of all products...")
        response = get_product_list(None, page, 100, country, language)
        
        try:
            products = response.get("data", {}).get("results", [])
            if not products:
                break
                
            for product in products:
                all_product_ids.add(product.get("id"))
                
            page += 1
        except:
            print(f"Error processing page {page}")
            break
    
    # Also try with each category to ensure we get everything
    categories = get_all_category_ids(country, language)
    for category_id in categories:
        page = 1
        while True:
            print(f"Fetching page {page} for category {category_id}...")
            response = get_product_list(category_id, page, 100, country, language)
            
            try:
                products = response.get("data", {}).get("results", [])
                if not products:
                    break
                    
                for product in products:
                    all_product_ids.add(product.get("id"))
                    
                page += 1
            except:
                print(f"Error processing page {page} for category {category_id}")
                break
    
    return list(all_product_ids)

def get_product_stock_info(product_id, country="AU", language="en"):
    """Get stock information for a specific product"""
    try:
        details = get_product_details(product_id, country, language)
        
        if "data" not in details or not details["data"]:
            return {
                "product_id": product_id,
                "title": "Unknown",
                "status": "Error fetching details",
                "sku_count": 0,
                "skus": []
            }
        
        product_data = details["data"]
        skus = product_data.get("skus", [])
        
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
        
        return {
            "product_id": product_id,
            "title": product_data.get("title", "Unknown"),
            "brand": product_data.get("brand", {}).get("name"),
            "publish_status": "Published" if product_data.get("isPublish") else "Not Published",
            "availability": "Available" if product_data.get("isAvailable") else "Not Available",
            "sku_count": len(skus),
            "skus": sku_info
        }
    except Exception as e:
        print(f"Error getting stock for product {product_id}: {str(e)}")
        return {
            "product_id": product_id,
            "title": "Error",
            "status": str(e),
            "sku_count": 0,
            "skus": []
        }

def check_all_stock(country="AU", language="en", max_workers=5):
    """Check stock for all products and save to CSV"""
    product_ids = get_all_products(country, language)
    print(f"Found {len(product_ids)} products. Fetching stock information...")
    
    all_results = []
    
    # Use threading to speed up the process
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a future for each product ID
        future_to_id = {
            executor.submit(get_product_stock_info, product_id, country, language): product_id 
            for product_id in product_ids
        }
        
        # Process results as they complete
        for i, future in enumerate(future_to_id):
            try:
                result = future.result()
                all_results.append(result)
                print(f"Processed {i+1}/{len(product_ids)}: {result['title']}")
            except Exception as e:
                product_id = future_to_id[future]
                print(f"Error processing product {product_id}: {str(e)}")
    
    # Save all results to CSV
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"popmart_stock_{country}_{timestamp}.csv"
    
    # First, create a flat version of the data for CSV
    flat_data = []
    for product in all_results:
        if product["sku_count"] == 0:
            # No SKUs, add a single row
            flat_data.append({
                "product_id": product["product_id"],
                "title": product["title"],
                "brand": product.get("brand", ""),
                "publish_status": product.get("publish_status", ""),
                "availability": product.get("availability", ""),
                "sku_id": "",
                "sku_title": "",
                "sku_code": "",
                "price": "",
                "discount_price": "",
                "currency": "",
                "stock": 0,
                "lock_stock": 0
            })
        else:
            # Add a row for each SKU
            for sku in product["skus"]:
                flat_data.append({
                    "product_id": product["product_id"],
                    "title": product["title"],
                    "brand": product.get("brand", ""),
                    "publish_status": product.get("publish_status", ""),
                    "availability": product.get("availability", ""),
                    "sku_id": sku["sku_id"],
                    "sku_title": sku["sku_title"],
                    "sku_code": sku["sku_code"],
                    "price": sku["price"],
                    "discount_price": sku["discount_price"],
                    "currency": sku["currency"],
                    "stock": sku["stock"],
                    "lock_stock": sku["lock_stock"]
                })
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        if flat_data:
            writer = csv.DictWriter(f, fieldnames=list(flat_data[0].keys()))
            writer.writeheader()
            writer.writerows(flat_data)
    
    print(f"Stock information saved to {filename}")
    
    # Also save the raw JSON data for reference
    with open(f"popmart_stock_{country}_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    return all_results

def get_stock_by_id(product_id, country="AU", language="en"):
    """Check stock for a specific product and print details"""
    result = get_product_stock_info(product_id, country, language)
    
    print(f"\nProduct: {result['title']} (ID: {result['product_id']})")
    print(f"Brand: {result.get('brand', 'Unknown')}")
    print(f"Status: {result.get('publish_status', 'Unknown')} / {result.get('availability', 'Unknown')}")
    print(f"SKUs: {result['sku_count']}")
    
    for sku in result["skus"]:
        price = f"{float(sku['price'])/100:.2f}" if sku['price'] else "N/A"
        discount = f"{float(sku['discount_price'])/100:.2f}" if sku['discount_price'] else "N/A"
        
        print(f"\n  SKU: {sku['sku_title']} (ID: {sku['sku_id']})")
        print(f"  Code: {sku['sku_code']}")
        print(f"  Price: {price} {sku['currency']} (Discount: {discount} {sku['currency']})")
        print(f"  Stock: {sku['stock']} (Locked: {sku['lock_stock']})")
    
    return result

if __name__ == "__main__":
    print("PopMart Stock Checker")
    print("====================")
    print("1. Check stock for a specific product")
    print("2. Check stock for all products")
    print("3. Exit")
    print("4. Check stock for product 938 in AU")
    
    choice = input("\nEnter your choice (1-4): ")
    
    if choice == "1":
        product_id = input("Enter product ID: ")
        country = input("Enter country code (default: AU): ") or "AU"
        get_stock_by_id(product_id, country)
    elif choice == "2":
        country = input("Enter country code (default: AU): ") or "AU"
        check_all_stock(country)
    elif choice == "4":
        # Directly check product ID 938 in AU
        print("Checking stock for product ID 938 in AU...")
        get_stock_by_id("938", "AU")
    else:
        print("Exiting...")