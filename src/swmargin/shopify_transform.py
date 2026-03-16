from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import pandas as pd

from src.swmargin.core import classify_region, Costs, CogsResult


def _amt(x) -> float:
    try:
        return float(x["shopMoney"]["amount"])
    except Exception:
        return 0.0


def build_revenue_orders_from_shopify(nodes: list[dict[str, Any]]) -> Dict[str, float]:
    """
    Returns:
      net_rev_se, orders_se, net_rev_other, orders_other
    Adjusted net revenue definition:
      subtotal + shipping  (excludes tax; discounts are already reflected in subtotal depending on Shopify)
    If you want stricter definition later, we can align to your Shopify report precisely.
    """
    net_se = ord_se = 0.0
    net_ot = ord_ot = 0.0

    for o in nodes:
        country = None
        if o.get("shippingAddress"):
            country = o["shippingAddress"].get("countryCodeV2") or o["shippingAddress"].get("country")

        region = classify_region(country) if country else "UNKNOWN"
        if region == "UNKNOWN":
            # Put unknown into OTHER (so you don't lose revenue)
            region = "OTHER"

        subtotal = _amt(o.get("subtotalPriceSet") or {})
        shipping = _amt(o.get("totalShippingPriceSet") or {})
        adjusted = subtotal + shipping

        if region == "SE":
            net_se += adjusted
            ord_se += 1
        else:
            net_ot += adjusted
            ord_ot += 1

    return {
        "net_rev_se": float(net_se),
        "orders_se": float(ord_se),
        "net_rev_other": float(net_ot),
        "orders_other": float(ord_ot),
        "net_sales_source": "Shopify subtotalPriceSet",
        "shipping_source": "Shopify totalShippingPriceSet",
    }


def build_cogs_from_shopify(nodes: list[dict[str, Any]], costs: Costs) -> CogsResult:
    """
    COGS = sum(quantity * cogs_per_sku) across all line items.
    This is TOTAL only; we return it in cogs_se and keep cogs_other=0.0 to match your current model.
    """
    rows = []
    for o in nodes:
        for e in (o.get("lineItems", {}).get("edges") or []):
            li = e["node"]
            sku = (li.get("sku") or "").strip()
            qty = float(li.get("quantity") or 0)
            if not sku or qty == 0:
                continue
            rows.append({"sku": sku, "qty": qty})

    df = pd.DataFrame(rows)
    if df.empty:
        unmatched = pd.DataFrame(columns=["sku", "line_rows", "total_qty"])
        return CogsResult(
            cogs_se=0.0,
            cogs_other=0.0,
            coverage_pct=0.0,
            unmatched=unmatched,
            missing_country=pd.DataFrame(),
            returns_adjustments=pd.DataFrame(),
            meta={"source": "shopify"},
        )

    df["cogs_per_unit"] = df["sku"].map(costs.cogs_by_sku)
    matched = df[df["cogs_per_unit"].notna()].copy()
    unmatched_df = df[df["cogs_per_unit"].isna()].copy()

    matched["line_cogs"] = matched["qty"] * matched["cogs_per_unit"].astype(float)
    cogs_total = float(matched["line_cogs"].sum())

    coverage_pct = float((len(matched) / len(df)) * 100.0) if len(df) else 0.0

    if not unmatched_df.empty:
        unmatched_summary = (
            unmatched_df.groupby("sku")
            .agg(line_rows=("sku", "count"), total_qty=("qty", "sum"))
            .reset_index()
            .sort_values(["total_qty", "line_rows"], ascending=False)
        )
    else:
        unmatched_summary = pd.DataFrame(columns=["sku", "line_rows", "total_qty"])

    return CogsResult(
        cogs_se=cogs_total,
        cogs_other=0.0,
        coverage_pct=coverage_pct,
        unmatched=unmatched_summary,
        missing_country=pd.DataFrame(),
        returns_adjustments=pd.DataFrame(),
        meta={"source": "shopify"},
    )


def build_sku_profit_table(nodes: list[dict[str, Any]], costs: Costs) -> pd.DataFrame:
    """
    Approx profit per SKU:
      revenue ≈ sum(discountedTotalSet for line item)  (Shopify provides this per line item)
      cogs = qty * cogs_per_unit
      profit = revenue - cogs
    """
    rows = []
    for o in nodes:
        for e in (o.get("lineItems", {}).get("edges") or []):
            li = e["node"]
            sku = (li.get("sku") or "").strip()
            qty = float(li.get("quantity") or 0)
            rev = 0.0
            try:
                rev = float(li["discountedTotalSet"]["shopMoney"]["amount"])
            except Exception:
                rev = 0.0
            if not sku or qty == 0:
                continue
            rows.append({"sku": sku, "qty": qty, "revenue": rev})

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["sku", "qty", "revenue", "cogs", "profit", "margin_%"])

    df["cogs_per_unit"] = df["sku"].map(costs.cogs_by_sku)
    df["cogs"] = df["qty"] * df["cogs_per_unit"].fillna(0.0)
    df["profit"] = df["revenue"] - df["cogs"]
    df["margin_%"] = (df["profit"] / df["revenue"] * 100.0).where(df["revenue"] != 0, 0.0)

    out = (
        df.groupby("sku", as_index=False)
        .agg(qty=("qty", "sum"), revenue=("revenue", "sum"), cogs=("cogs", "sum"), profit=("profit", "sum"))
    )
    out["margin_%"] = (out["profit"] / out["revenue"] * 100.0).where(out["revenue"] != 0, 0.0)
    return out.sort_values("profit", ascending=False)