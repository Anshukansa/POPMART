import hashlib
import json
import time
import requests

def generate_signature(params, timestamp, method="get"):
    """Generate the signature ('s' parameter) for PopMart API"""
    salt = "W_ak^moHpMla"
    json_string = json.dumps(params, separators=(',', ':'))
    string_to_hash = f"{json_string}{salt}{timestamp}"
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
    
    # Set headers
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
        "x-project-id": "eude",
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

def get_product_details(spu_id, country="AU", language="en"):
    """Get detailed information about a specific product"""
    endpoint = "/shop/v1/shop/productDetails"
    params = {"spuId": str(spu_id)}
    
    return make_api_request(endpoint, params, country=country, language=language)

def get_product_stock_info(product_url, country="AU", language="en"):
    """Extract product ID from URL and get stock information for a specific product"""
    try:
        # Extract product ID from URL (e.g., 'https://www.popmart.com/au/products/938')
        product_id = product_url.strip().split('/')[-1]
        
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
        print(f"Error getting stock for product {product_url}: {str(e)}")
        return {
            "product_id": product_url.split('/')[-1],
            "title": "Error",
            "status": str(e),
            "sku_count": 0,
            "skus": []
        }

if __name__ == "__main__":
    print("PopMart Stock Checker")
    product_url = input("Enter PopMart product URL (e.g., https://www.popmart.com/au/products/938): ").strip()
    result = get_product_stock_info(product_url)
    
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
