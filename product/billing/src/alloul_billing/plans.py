PLANS = {
    "alloulq": {
        "starter":    {"price_usd": 30,  "seats": 3,  "storage_gb": 5},
        "pro":        {"price_usd": 90,  "seats": 10, "storage_gb": 20},
        "business":   {"price_usd": 210, "seats": 30, "storage_gb": 100},
        "enterprise": {"price_usd": None, "seats": None, "storage_gb": None},
    },
    "handex": {
        "enterprise": {"price_usd": None, "seats": None, "storage_gb": None},
    },
}

def get_plan(product: str, plan: str) -> dict:
    return PLANS.get(product, {}).get(plan, {})

def list_plans(product: str) -> list[dict]:
    product_plans = PLANS.get(product, {})
    return [{"name": k, **v} for k, v in product_plans.items()]
