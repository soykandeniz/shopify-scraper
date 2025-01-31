import urllib.request
from urllib.error import URLError, HTTPError
import json
import ssl
import logging
import random
import time
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth
import undetected_chromedriver as uc
import chromedriver_autoinstaller
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import subprocess
import re


# Disable SSL warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants


ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
MAX_RETRIES = 5
TIMEOUT = 10
BACKOFF_FACTOR = 0.5
BACKUP_PROXIES = [
    "http://185.162.230.231:80",
    "http://165.154.224.14:80",
    "http://103.149.130.38:80",
    "http://45.61.188.134:8080",
    "http://45.61.187.67:8080",
]
WORKING_PROXIES = set()


class ProxySession:
    def __init__(self):
        self.session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[403, 429, 500, 502, 503, 504],
        )

        self.session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
        self.ua = UserAgent()

        # Add CloudFlare bypass
        self.session.headers.update(
            {
                "User-Agent": self.ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
        )


RESIDENTIAL_PROXIES = [
    "http://residential.proxy-seller.com:10000",
    "http://residential.proxy-seller.com:10001",
    "http://residential.proxy-seller.com:10002",
]


def get_session():
    """Create session with retries and headers"""
    session = requests.Session()

    # Configure retry strategy
    retries = Retry(
        total=5, backoff_factor=0.5, status_forcelist=[403, 429, 500, 502, 503, 504]
    )

    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))

    # Set convincing browser headers
    session.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": '"Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    return session


# Update user agents
def get_random_user_agent():
    ua = UserAgent()
    return ua.random


def get_free_proxies():
    """Get fresh proxies from multiple sources"""
    proxies = set()

    # Free-proxy-list.net
    try:
        response = requests.get(
            "https://www.free-proxy-list.net/",
            headers={"User-Agent": get_random_user_agent()},
            timeout=10,
        )
        soup = BeautifulSoup(response.text, "html.parser")
        proxy_table = soup.find("table")

        if proxy_table and proxy_table.find("tbody"):
            for row in proxy_table.find("tbody").find_all("tr"):
                cols = row.find_all("td")
                if len(cols) > 6:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    https = cols[6].text.strip()
                    country = cols[2].text.strip()
                    if https == "yes" and country in ["US", "CA", "GB"]:
                        proxies.add(f"http://{ip}:{port}")
    except Exception as e:
        logging.error(f"Error fetching from free-proxy-list: {e}")

    # Proxy-list.download
    try:
        response = requests.get(
            "https://www.proxy-list.download/api/v1/get?type=http",
            headers={"User-Agent": get_random_user_agent()},
            timeout=10,
        )
        if response.status_code == 200:
            for line in response.text.split("\n"):
                if line.strip():
                    proxies.add(f"http://{line.strip()}")
    except Exception as e:
        logging.error(f"Error fetching from proxy-list.download: {e}")

    # Add backup proxies if no proxies found
    if not proxies:
        proxies.update(BACKUP_PROXIES)

    return list(proxies)


def validate_proxy(proxy, timeout=5):
    """Test if proxy is working"""
    try:
        test_url = "https://api.ipify.org?format=json"
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
        opener.addheaders = [("User-Agent", get_random_user_agent())]

        with opener.open(test_url, timeout=timeout) as response:
            return response.getcode() == 200
    except:
        return False


def get_chrome_version():
    """Get installed Chrome version"""
    try:
        # Windows command to get Chrome version
        cmd = (
            r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
        )
        output = subprocess.check_output(cmd, shell=True).decode()
        match = re.search(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", output)
        if match:
            version = match.group(0)
        else:
            version = None
        # Return exact version instead of just major version
        return version
    except:
        return None


def get_shopify_content(url):
    """Get content using Selenium with version-matched ChromeDriver"""
    try:
        chrome_version = get_chrome_version()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Add proxy support
        proxy = random.choice(BACKUP_PROXIES)
        options.add_argument(f"--proxy-server={proxy}")

        # Add stealth settings
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Install matching ChromeDriver version
        service = Service(ChromeDriverManager(driver_version=chrome_version).install())
        driver = webdriver.Chrome(service=service, options=options)

        # Add stealth
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride", {"userAgent": get_random_user_agent()}
        )

        driver.get(url)
        time.sleep(random.uniform(3, 7))
        return driver.page_source

    except Exception as e:
        logging.error(f"Selenium error: {str(e)}")
        return None
    finally:
        if "driver" in locals():
            driver.quit()


def get_proxy_handler():
    """Get handler for working proxy"""
    try:
        proxies = get_free_proxies()
        if not proxies:
            proxies = BACKUP_PROXIES
        proxy = random.choice(proxies)
        return urllib.request.ProxyHandler({"http": proxy, "https": proxy}), proxy
    except:
        proxy = random.choice(BACKUP_PROXIES)
        return urllib.request.ProxyHandler({"http": proxy, "https": proxy}), proxy


def make_request(url, headers=None, retry_count=5, delay=2):
    """Make request with enhanced headers and proxy rotation"""
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "TE": "Trailers",
    }

    for attempt in range(retry_count):
        try:
            proxy_handler, current_proxy = get_proxy_handler()
            opener = urllib.request.build_opener(proxy_handler)
            urllib.request.install_opener(opener)

            req = urllib.request.Request(url, headers=headers)
            time.sleep(random.uniform(2, 5))  # Increased delay

            with urllib.request.urlopen(
                req, context=ssl_context, timeout=30
            ) as response:
                return response.read().decode()

        except Exception as e:
            logging.error(f"Request failed (attempt {attempt + 1}): {str(e)}")
            if current_proxy in WORKING_PROXIES:
                WORKING_PROXIES.remove(current_proxy)
            time.sleep(delay * (attempt + 1))

    raise Exception(f"Failed after {retry_count} attempts")


def check_shopify_indicators(url):
    """Check if a website is built with Shopify using requests library"""
    try:
        if not url.startswith("http"):
            url = "https://" + url

        # Get working proxy
        proxies = get_free_proxies()
        working_proxy = None

        for proxy in proxies:
            try:
                proxy_dict = {"http": proxy, "https": proxy}
                response = requests.get(
                    url,
                    proxies=proxy_dict,
                    headers={
                        "User-Agent": get_random_user_agent(),
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Referer": "https://www.google.com/",
                    },
                    timeout=10,
                    verify=False,
                )

                if response.status_code == 200:
                    working_proxy = proxy
                    break
            except:
                continue

        if not working_proxy:
            logging.error("No working proxies found")
            return False

        # Use working proxy for main request
        proxy_dict = {"http": working_proxy, "https": working_proxy}
        response = requests.get(
            url,
            proxies=proxy_dict,
            headers={"User-Agent": get_random_user_agent()},
            verify=False,
        )

        soup = BeautifulSoup(response.text, "html.parser")

        # Check for Shopify indicators
        indicators = [
            soup.find("meta", {"name": "shopify-checkout-api-token"}),
            soup.find("meta", {"name": "shopify-digital-wallet"}),
            soup.find("script", {"src": lambda x: x and "shopify" in str(x).lower()}),
            soup.find("link", {"href": lambda x: x and "cdn.shopify.com" in str(x)}),
            soup.find("img", {"src": lambda x: x and "cdn.shopify.com" in str(x)}),
            soup.find("a", {"href": lambda x: x and "myshopify.com" in str(x)}),
        ]

        return any(indicators)

    except Exception as e:
        logging.error(f"Error checking Shopify indicators: {str(e)}")
        return False


def check_shopify_indicators2(url):
    """Check if website is Shopify using selenium"""
    try:
        content = get_shopify_content(url)
        soup = BeautifulSoup(content or "", "html.parser")

        indicators = [
            soup.find("meta", {"name": "shopify-checkout-api-token"}),
            soup.find("meta", {"name": "shopify-digital-wallet"}),
            soup.find("script", {"src": lambda x: x and "shopify" in str(x).lower()}),
            soup.find("link", {"href": lambda x: x and "cdn.shopify.com" in str(x)}),
        ]

        return any(indicators)

    except Exception as e:
        logging.error(f"Error checking Shopify indicators: {str(e)}")
        return False


def is_shopify_store(url):
    """Verify if the URL is a Shopify store"""
    if not check_shopify_indicators2(url):
        logging.error(f"No Shopify indicators found for: {url}")
        return False
    try:
        if not url.startswith("http"):
            url = "https://" + url
        base_url = url.split("?")[0].rstrip("/")

        # Extract collection if present
        collection_path = "/collections/"
        collection = None
        if collection_path in base_url:
            parts = base_url.split(collection_path)
            base_url = parts[0]
            if len(parts) > 1:
                collection = parts[1].split("/")[0]

        logging.info(f"Base URL: {base_url}, Collection: {collection}")

        # Test endpoints including collection-specific ones
        test_endpoints = [
            "/products.json?limit=1",
            "/collections/all/products.json?limit=1",
            "/cdn/shop/products.json?limit=1",
            f"/collections/{collection}/products.json?limit=1" if collection else None,
        ]

        # Filter out None values
        test_endpoints = [ep for ep in test_endpoints if ep]

        for endpoint in test_endpoints:
            try:
                test_url = f"{base_url}{endpoint}"
                logging.info(f"Testing: {test_url}")

                req = urllib.request.Request(
                    test_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                        "Connection": "close",
                    },
                )

                try:
                    with urllib.request.urlopen(
                        req, context=ssl_context, timeout=10
                    ) as response:
                        response_code = response.getcode()
                        content = response.read().decode()

                        logging.info(f"Response Code: {response_code}")
                        logging.info(f"Response Headers: {dict(response.headers)}")
                        logging.info(f"Response Content: {content[:1000]}")

                        if response_code == 200:
                            try:
                                json_data = json.loads(content)
                                if "products" in json_data:
                                    logging.info(f"✓ Valid endpoint: {test_url}")
                                    return True
                                else:
                                    logging.error(
                                        f"No products key in response: {json_data.keys()}"
                                    )
                            except json.JSONDecodeError as e:
                                logging.error(
                                    f"JSON parse error: {str(e)}\nContent: {content[:200]}"
                                )
                        else:
                            logging.error(f"Bad status code: {response_code}")

                except HTTPError as e:
                    logging.error(f"HTTP Error {e.code}: {e.reason} for {test_url}")
                except URLError as e:
                    logging.error(f"Connection failed: {str(e)} for {test_url}")
                except Exception as e:
                    logging.error(f"Request failed: {str(e)} for {test_url}")

            except Exception as e:
                logging.error(f"Endpoint test failed: {str(e)}")

        logging.error(f"❌ No valid Shopify endpoints found for: {base_url}")
        return False

    except Exception as e:
        logging.error(f"Store verification failed: {str(e)}")
        logging.exception("Full traceback:")
        return False


def get_all_products_by_req(url):
    # First verify if it's a Shopify store
    if not is_shopify_store(url):
        logging.error(f"Not a Shopify store or API access restricted: {url}")
        return []

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
                products_url,
                data=None,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Connection": "close",
                },
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
            category = "Apparel & Accessories"
            tags = product.get("tags", []) or []
            for tag in tags:
                if tag and isinstance(tag, str) and tag.startswith("category:"):
                    category = tag.replace("category:", "")
                    break

            # Safe variant extraction with price validation
            variants = product.get("variants", []) or []
            variant = variants[0] if variants else {}
            try:
                price = format(float(variant.get("price") or 0), ".2f")
            except (ValueError, TypeError):
                price = "0.00"

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

            # Safe numeric fields with validation
            try:
                variant_grams = int(variant.get("grams", 0))
            except (ValueError, TypeError):
                variant_grams = 0

            try:
                inventory_qty = int(variant.get("inventory_quantity", 0))
            except (ValueError, TypeError):
                inventory_qty = 0

            # Safe compare at price validation
            try:
                compare_price = variant.get("compare_at_price")
                compare_at_price = format(
                    float(compare_price if compare_price else 0), ".2f"
                )
            except (ValueError, TypeError):
                compare_at_price = "0.00"

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
                "Variant Price": price,
                "Variant Compare At Price": (
                    compare_at_price if compare_at_price != "0.00" else ""
                ),
                "Variant Requires Shipping": str(
                    variant.get("requires_shipping", True)
                ).upper(),
                "Variant Taxable": str(variant.get("taxable", True)).upper(),
                # Images
                "Image Src": first_image,
                "Image Position": "1",
                # Google Shopping fields
                "Google Shopping / Google Product Category": f"Apparel & Accessories > {category}",
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
