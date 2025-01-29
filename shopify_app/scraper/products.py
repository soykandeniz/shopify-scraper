import json
import ssl
import urllib.request
import logging
from urllib.error import URLError

from bs4 import BeautifulSoup

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"


def get_all_products_by_req(url):
    page = 1
    products_json_list = []

    # Validate and clean URL
    if not url.startswith("http"):
        url = "https://" + url
    base_url = url.split("?")[0].rstrip("/")

    while True:
        try:
            products_url = f"{base_url}/products.json?limit=250&page={page}"
            req = urllib.request.Request(
                products_url, data=None, headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(req, context=ssl_context) as response:
                data = response.read()

                # Validate JSON response
                if not data:
                    logging.error(f"Empty response from {products_url}")
                    break

                try:
                    json_data = json.loads(data.decode())
                    if not isinstance(json_data, dict) or "products" not in json_data:
                        logging.error(f"Invalid JSON structure from {products_url}")
                        break

                    products = json_data["products"]
                    if not products:
                        break

                    products_json_list.extend(products)
                    page += 1

                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                    break

        except URLError as e:
            logging.error(f"URL error: {e}")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            break

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

            # Safe options extraction with validation
            options = product.get("options", []) or []
            option1 = options[0] if len(options) > 0 else {}
            option2 = options[1] if len(options) > 1 else {}
            option3 = options[2] if len(options) > 2 else {}

            # Safe variant fields with type conversion
            try:
                variant_grams = int(variant.get("grams", 0))
            except (ValueError, TypeError):
                variant_grams = 0

            try:
                inventory_qty = int(variant.get("inventory_quantity", 0))
            except (ValueError, TypeError):
                inventory_qty = 0

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
                "Option1 Name": str(option1.get("name", "") or ""),
                "Option1 Value": ", ".join(
                    filter(None, option1.get("values", []) or [])
                ),
                "Option2 Name": str(option2.get("name", "") or ""),
                "Option2 Value": ", ".join(
                    filter(None, option2.get("values", []) or [])
                ),
                "Option3 Name": str(option3.get("name", "") or ""),
                "Option3 Value": ", ".join(
                    filter(None, option3.get("values", []) or [])
                ),
                # Variant details with safe access
                "Variant SKU": str(variant.get("sku", "") or ""),
                "Variant Grams": variant_grams,
                "Variant Inventory Tracker": "shopify",
                "Variant Inventory Qty": inventory_qty,
                "Variant Inventory Policy": str(
                    variant.get("inventory_policy", "deny") or "deny"
                ),
                "Variant Fulfillment Service": str(
                    variant.get("fulfillment_service", "manual") or "manual"
                ),
                "Variant Price": price,
                "Variant Compare At Price": str(
                    variant.get("compare_at_price", "") or ""
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
