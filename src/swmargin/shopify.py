from __future__ import annotations

import datetime as dt
from typing import Dict, Any, List, Optional, Tuple

import requests
import streamlit as st


def _iso(dt_obj: dt.datetime) -> str:
    # Shopify expects ISO8601 with timezone
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.isoformat()


def _shopify_post_graphql(query: str, variables: dict | None = None) -> dict:
    shop = st.secrets["SHOPIFY_SHOP_DOMAIN"]
    token = st.secrets["SHOPIFY_ADMIN_TOKEN"]
    version = st.secrets.get("SHOPIFY_API_VERSION", "2025-01")

    url = f"https://{shop}/admin/api/{version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }

    r = requests.post(url, json={"query": query, "variables": variables or {}}, headers=headers, timeout=60)
    
    if not r.ok:
        raise RuntimeError(f"Shopify API error {r.status_code}: {r.text}")
    
    payload = r.json()

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    if payload.get("data") is None:
        raise RuntimeError(payload)

    return payload["data"]


ORDERS_QUERY = """
query Orders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        createdAt
        displayFinancialStatus
        shippingAddress { countryCodeV2 country }
        totalShippingPriceSet { shopMoney { amount currencyCode } }
        subtotalPriceSet { shopMoney { amount currencyCode } }
        totalDiscountsSet { shopMoney { amount currencyCode } }
        totalTaxSet { shopMoney { amount currencyCode } }
        totalPriceSet { shopMoney { amount currencyCode } }
        lineItems(first: 250) {
          edges {
            node {
              sku
              quantity
              discountedTotalSet { shopMoney { amount currencyCode } }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_orders_with_lineitems(
    start_date: dt.date,
    end_date: dt.date,
    financial_status: str = "paid",
    page_size: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetch orders and line items (SKU, quantity, discounted line total) for a date range.
    Uses Shopify search query on created_at.
    """
    # created_at filter is inclusive; end_date set to end-of-day
    start_dt = dt.datetime.combine(start_date, dt.time(0, 0, 0, tzinfo=dt.timezone.utc))
    end_dt = dt.datetime.combine(end_date, dt.time(23, 59, 59, tzinfo=dt.timezone.utc))

    # Shopify order search query syntax
    # Examples: created_at:>=2026-03-01 created_at:<=2026-03-31 financial_status:paid
    q = f"created_at:>={start_dt.date().isoformat()} created_at:<={end_dt.date().isoformat()} financial_status:{financial_status} -status:cancelled"

    all_nodes: List[Dict[str, Any]] = []
    after: Optional[str] = None

    while True:
        data = _shopify_post_graphql(
            ORDERS_QUERY,
            variables={"first": page_size, "after": after, "query": q},
        )
        conn = data["orders"]
        edges = conn["edges"]
        for e in edges:
            all_nodes.append(e["node"])

        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]

    return all_nodes