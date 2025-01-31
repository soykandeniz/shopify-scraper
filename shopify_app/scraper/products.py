import json
import ssl
import urllib.request
import logging
from urllib.error import URLError, HTTPError
import random
import time
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"

# Add proxy list
PROXIES = [
    "http://154.53.49.167:3128",
    "http://154.53.49.167:3128",
    "http://154.53.49.167:8888",
    "http://154.92.123.46:3128",
    "http://154.92.123.47:3128",
    # Add more proxies
]


# Update user agents
def get_random_user_agent():
    ua = UserAgent()
    return ua.random


def get_proxy_handler():
    proxy = random.choice(PROXIES)
    proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    return proxy_handler


def make_request(url, headers=None, retry_count=5, delay=2):
    """Make request with proxy and retry logic"""
    headers = headers or {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    for attempt in range(retry_count):
        try:
            proxy_handler = get_proxy_handler()
            opener = urllib.request.build_opener(proxy_handler)
            urllib.request.install_opener(opener)

            req = urllib.request.Request(url, headers=headers)

            # Add random delay
            time.sleep(random.uniform(1, 3))

            with urllib.request.urlopen(
                req, context=ssl_context, timeout=20
            ) as response:
                return response.read().decode()

        except Exception as e:
            logging.error(f"Request failed (attempt {attempt + 1}): {str(e)}")
            time.sleep(delay * (attempt + 1))

    raise Exception(f"Failed after {retry_count} attempts")


def check_shopify_indicators(url):
    """Enhanced Shopify store detection"""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
            content = response.read().decode("utf-8", errors="ignore")

            # Simple string matching for common Shopify indicators
            indicators = [
                "Shopify.theme",
                "shopify.com",
                "myshopify.com",
                "/cdn/shop/",
                "shopify-buy",
                "shopify.loadFeatures",
                "/products.json",
                "shopify-payment-button",
            ]

            # Check if any indicator exists in page content
            return any(indicator.lower() in content.lower() for indicator in indicators)

    except Exception as e:
        logging.warning(f"Shopify check failed: {str(e)}")
        # Return True to allow scraping attempt even if check fails
        return True


def is_shopify_store(url):
    """Simplified Shopify store verification"""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Try products.json endpoint directly
        test_url = f"{url.rstrip('/')}/products.json?limit=1"

        headers = {"User-Agent": get_random_user_agent(), "Accept": "application/json"}

        req = urllib.request.Request(test_url, headers=headers)

        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
            content = response.read().decode()
            json_data = json.loads(content)
            return "products" in json_data

    except Exception as e:
        logging.warning(f"Store verification failed: {str(e)}")
        # Return True to allow scraping attempt
        return True


def get_all_products_by_req(url):
    # First verify if it's a Shopify store
    # if not is_shopify_store(url):
    #     logging.error(f"Not a Shopify store or API access restricted: {url}")
    #     return []

    page = 1
    products_json_list = []

    # Validate and clean URL
    if not url.startswith("http"):
        url = "https://" + url
    base_url = url.split("?")[0].rstrip("/")

    # Debug logging for URL
    logging.info(f"Attempting to scrape: {base_url}")

    while True:
        try:
            products_url = f"{base_url}/products.json?limit=250&page={page}"
            logging.info(f"DEBUG: Trying URL: {products_url}")

            req = urllib.request.Request(
                products_url, data=None, headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(req, context=ssl_context) as response:
                response_code = response.getcode()
                logging.info(f"DEBUG: Response code: {response_code}")
                logging.info(f"DEBUG: Response headers: {response.headers}")

                data = response.read()
                content = data.decode()
                logging.info(f"DEBUG: Raw response data: {content[:500]}...")

                try:
                    json_data = json.loads(content)
                    logging.info(f"DEBUG: JSON keys: {json_data.keys()}")

                    if "products" not in json_data:
                        logging.error("DEBUG: No products key in response")
                        break

                    products = json_data["products"]
                    logging.info(
                        f"DEBUG: Products found on page {page}: {len(products)}"
                    )

                    if not products:
                        break

                    products_json_list.extend(products)
                    page += 1

                except json.JSONDecodeError as e:
                    logging.error(f"DEBUG: JSON decode error: {str(e)}")
                    logging.error(f"DEBUG: Invalid JSON: {content[:200]}")
                    break

        except HTTPError as e:
            logging.error(f"DEBUG: HTTP Error: {e.code} - {e.reason}")
            logging.error(f"DEBUG: URL: {products_url}")
            break
        except URLError as e:
            logging.error(f"DEBUG: URL Error: {str(e)}")
            logging.error(f"DEBUG: URL: {products_url}")
            break
        except Exception as e:
            logging.error(f"DEBUG: Unexpected error: {str(e)}")
            logging.error(f"DEBUG: URL: {products_url}")
            break

    logging.info(f"DEBUG: Total products found: {len(products_json_list)}")
    return products_json_list


def get_parse_data(products_list):
    result_json = []
    for product in products_list:
        try:
            # Safe category extraction with validation
            category = "Health Care"
            tags = product.get("tags", []) or []
            for tag in tags:
                if tag and isinstance(tag, str) and tag.startswith("category:"):
                    category = tag.replace("category:", "")
                    break

            # Safe variant extraction with price validation
            variants = product.get("variants", []) or []
            variant = variants[0] if variants else {}
            variant_grams = variant.get("grams", "")
            variant_price = variant.get("price", "")
            compare_price = variant.get("compare_at_price", "")
            try:
                inventory_qty = int(variant.get("inventory_quantity", 0))
            except (ValueError, TypeError):
                inventory_qty = 0
            # Safe image URLs extraction with validation
            images = product.get("images", []) or []
            image_urls = [
                img.get("src", "") for img in images if img and img.get("src")
            ]

            first_image = image_urls[0] if image_urls else ""

            # Fix option handling
            options = product.get("options", []) or []
            option_data = {}

            # Only add options that actually exist
            for i, opt in enumerate(options, 1):
                # if opt.get("name") and opt.get("values"):
                #     option_data[f"Option{i} Name"] = str(opt.get("name"))
                #     option_data[f"Option{i} Value"] = ", ".join(
                #         filter(None, opt.get("values", []))
                #     )
                # else:
                option_data[f"Option{i} Name"] = ""
                option_data[f"Option{i} Value"] = ""

            product_data = {
                "Handle": str(product.get("handle", "") or ""),
                "Title": str(product.get("title", "") or ""),
                "Body (HTML)": str(product.get("body_html", "") or ""),
                "Vendor": str(product.get("vendor", "") or ""),
                "Product Category": category,
                "Type": str(product.get("product_type", "") or ""),
                "Tags": ", ".join(filter(None, tags)),
                "Published": "TRUE" if product.get("published_at") else "FALSE",
                # Options with safe access
                **option_data,
                # Variant details with safe access
                "Variant SKU": str(variant.get("sku", "") or ""),
                "Variant Grams": str(variant_grams),
                "Variant Inventory Tracker": "shopify",
                "Variant Inventory Qty": str(inventory_qty),
                "Variant Inventory Policy": str(
                    variant.get("inventory_policy", "deny") or "deny"
                ),
                "Variant Fulfillment Service": str(
                    variant.get("fulfillment_service", "manual") or "manual"
                ),
                "Variant Price": (variant_price if variant_price != "0.00" else "0.00"),
                "Variant Compare At Price": (
                    compare_price if compare_price != "0.00" else "0.00"
                ),
                "Variant Requires Shipping": str(
                    variant.get("requires_shipping", True)
                ).upper(),
                "Variant Taxable": str(variant.get("taxable", True)).upper(),
                # Images
                "Image Src": first_image,
                "Image Position": "1",
                # Google Shopping fields
                "Google Shopping / Google Product Category": f"Health Care > {category}",
                "Google Shopping / Gender": "Unisex",
                "Google Shopping / Age Group": "Adult",
                "Google Shopping / Condition": "new",
                # Status
                "Status": "active" if product.get("published_at") else "draft",
            }

            result_json.append(product_data)

            # Create additional rows for remaining images
            if len(image_urls) > 1:
                handle = str(product.get("handle", "") or "")
                for image_url in image_urls[1:]:
                    additional_image_row = {
                        "Handle": handle,
                        "Title": "",
                        "Body (HTML)": "",
                        "Vendor": "",
                        "Product Category": "",
                        "Type": "",
                        "Tags": "",
                        "Published": "",
                        "Option1 Name": "",
                        "Option1 Value": "",
                        "Option2 Name": "",
                        "Option2 Value": "",
                        "Option3 Name": "",
                        "Option3 Value": "",
                        "Variant SKU": "",
                        "Variant Grams": "",
                        "Variant Inventory Tracker": "",
                        "Variant Inventory Qty": "",
                        "Variant Inventory Policy": "",
                        "Variant Fulfillment Service": "",
                        "Variant Price": "",
                        "Variant Compare At Price": "",
                        "Variant Requires Shipping": "",
                        "Variant Taxable": "",
                        "Image Src": image_url,
                        "Image Position": "",
                        "Google Shopping / Google Product Category": "",
                        "Google Shopping / Gender": "",
                        "Google Shopping / Age Group": "",
                        "Google Shopping / Condition": "",
                        "Status": "",
                    }
                    result_json.append(additional_image_row)
            logging.info(f"Successfully parsed product {product.get('id')}")

        except Exception as e:
            logging.error(
                f"Error parsing product {product.get('id', 'Unknown ID')}: {str(e)}"
            )
            logging.error(f"Product data: {json.dumps(product, indent=2)}")
            continue

    return result_json
