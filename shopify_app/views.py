import json

from django.http import JsonResponse
from django.shortcuts import render
from django.template.defaultfilters import register
from django.views.decorators.csrf import csrf_exempt

from .utils import url_utils as url_utils
from .scraper import products as scraper
import logging


@register.filter
def split(value, arg):
    return value.split(arg)


# Create your views here.
def index(request):
    return render(request, "index.html")


@csrf_exempt
def scrape(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        # Parse and validate request body
        try:
            request_body = request.body.decode("utf-8")
            req_json_data = json.loads(request_body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON in request body"}, status=400)

        # Get and validate URL
        url = req_json_data.get("url", "").strip()
        if not url:
            return JsonResponse({"error": "URL is required"}, status=400)

        # Extract domain and cleanup URL
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = "https://" + url
            parsed_url = urlparse(url)

        domain = parsed_url.netloc
        if not domain:
            return JsonResponse({"error": "Invalid URL format"}, status=400)

        # Check if store is Shopify
        if not scraper.is_shopify_store(url):
            return JsonResponse(
                {
                    "error": "Not a Shopify store or API is restricted",
                    "details": "Please ensure this is a valid Shopify store URL",
                },
                status=400,
            )

        # Get products
        products_json_list = scraper.get_all_products_by_req(url)
        if not products_json_list:
            return JsonResponse(
                {
                    "error": "No products found",
                    "details": "Could not retrieve products from this store",
                },
                status=404,
            )

        # Parse data and render
        jsonData = scraper.get_parse_data(products_json_list)
        return render(request, "products.html", {"data": jsonData})

    except Exception as e:
        logging.exception("Error during scraping:")
        return JsonResponse({"error": "Scraping failed", "details": str(e)}, status=500)
