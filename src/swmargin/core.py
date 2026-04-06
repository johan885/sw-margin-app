from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List
import pandas as pd


SE_ALIASES = {"sweden", "sverige", "se"}


def _norm(s: str) -> str:
    return (
        str(s)
        .strip()
        .lower()
        .replace("\u00a0", " ")
        .replace("_", " ")
        .replace("-", " ")
    )


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm(c) for c in df.columns]
    return df


def _find_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    cols_norm = [_norm(c) for c in cols]
    for cand in candidates:
        cand_n = _norm(cand)
        for c in cols_norm:
            if c == cand_n:
                return c
    # fallback: contains match
    for cand in candidates:
        cand_n = _norm(cand)
        for c in cols_norm:
            if cand_n in c:
                return c
    return None


def _to_number(series: pd.Series) -> pd.Series:
    # Handles "1 234,56" and "1234.56" etc.
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def classify_region(country_value: object) -> str:
    if country_value is None or (isinstance(country_value, float) and pd.isna(country_value)):
        return "UNKNOWN"
    c = _norm(country_value)
    if c in SE_ALIASES:
        return "SE"
    return "OTHER"


@dataclass
class Costs:
    cogs_by_sku: Dict[str, float]
    shipping_per_order_se: float
    packaging_per_order_se: float
    shipping_per_order_other: float
    packaging_per_order_other: float
    meta: Dict[str, str]


def load_costs_workbook(file_obj) -> Costs:
    # Read all sheets
    sheets = pd.read_excel(file_obj, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise ValueError("No sheets found in the cost workbook.")

    cogs_df = None
    ship_df = None

    # Identify sheets by their headers
    for name, df in sheets.items():
        if df is None or df.empty:
            continue
        df_n = _norm_cols(df)

        cols = list(df_n.columns)

        has_sku = _find_col(cols, ["sku", "variant sku", "lineitem sku", "artikelnummer"]) is not None
        has_cogs = _find_col(cols, ["cogs_sek", "cogs", "cost", "unit_cost_sek", "inkopspris", "inköpspris"]) is not None

        has_region = _find_col(cols, ["region", "market", "land", "område"]) is not None
        has_ship = _find_col(cols, ["shipping_sek_per_order", "shipping per order", "frakt per order", "frakt"]) is not None
        has_pack = _find_col(cols, ["packaging_sek_per_order", "packaging per order", "emballage per order", "packaging", "emballage"]) is not None

        if cogs_df is None and has_sku and has_cogs:
            cogs_df = df_n.copy()
            cogs_sheet = name

        if ship_df is None and has_region and has_ship and has_pack:
            ship_df = df_n.copy()
            ship_sheet = name

    if cogs_df is None:
        raise ValueError("Could not find a COGS sheet in the workbook (need columns like SKU + COGS).")
    if ship_df is None:
        raise ValueError("Could not find a Shipping/Packaging sheet in the workbook (need region + shipping + packaging).")

    sku_col = _find_col(list(cogs_df.columns), ["sku", "variant sku", "lineitem sku", "artikelnummer"])
    cogs_col = _find_col(list(cogs_df.columns), ["cogs_sek", "cogs", "cost", "unit_cost_sek", "inkopspris", "inköpspris"])

    cogs_df = cogs_df[[sku_col, cogs_col]].copy()
    cogs_df[sku_col] = cogs_df[sku_col].astype(str).str.strip()
    cogs_df[cogs_col] = _to_number(cogs_df[cogs_col]).fillna(0.0)

    cogs_by_sku = dict(zip(cogs_df[sku_col], cogs_df[cogs_col]))

    region_col = _find_col(list(ship_df.columns), ["region", "market", "land", "område"])
    ship_col = _find_col(list(ship_df.columns), ["shipping_sek_per_order", "shipping per order", "frakt per order", "frakt"])
    pack_col = _find_col(list(ship_df.columns), ["packaging_sek_per_order", "packaging per order", "emballage per order", "packaging", "emballage"])

    ship_df = ship_df[[region_col, ship_col, pack_col]].copy()
    ship_df[region_col] = ship_df[region_col].astype(str).str.strip().str.upper()
    ship_df[ship_col] = _to_number(ship_df[ship_col]).fillna(0.0)
    ship_df[pack_col] = _to_number(ship_df[pack_col]).fillna(0.0)

    def _get_region_row(region: str) -> Tuple[float, float]:
        r = ship_df[ship_df[region_col] == region]
        if r.empty:
            return 0.0, 0.0
        row = r.iloc[-1]
        return float(row[ship_col]), float(row[pack_col])

    ship_se, pack_se = _get_region_row("SE")
    ship_ot, pack_ot = _get_region_row("OTHER")

    return Costs(
        cogs_by_sku=cogs_by_sku,
        shipping_per_order_se=ship_se,
        packaging_per_order_se=pack_se,
        shipping_per_order_other=ship_ot,
        packaging_per_order_other=pack_ot,
        meta={"cogs_sheet": cogs_sheet, "ship_sheet": ship_sheet, "sku_col": sku_col, "cogs_col": cogs_col},
    )


@dataclass
class RevenueOrders:
    net_rev_se: float
    orders_se: float
    net_rev_other: float
    orders_other: float
    meta: dict = field(default_factory=dict)
    net_sales_source: str = "unknown"
    shipping_source: str = "unknown"


def compute_revenue_orders(sales_by_location_csv_bytes: bytes) -> RevenueOrders:
    import io
    df = pd.read_csv(io.BytesIO(sales_by_location_csv_bytes))
    df = _norm_cols(df)
    # Create adjusted net revenue as Column F + Column G (1-indexed Excel columns)
    # 0-based pandas: F=5, G=6
    # Adjusted net revenue = Net sales + Shipping (by column names; safer than F/G)
    cols = list(df.columns)

    # Adjusted net revenue = Net sales + Shipping (by column names; fallback to F+G)
    cols = list(df.columns)

    net_sales_col = _find_col(cols, ["net sales", "net sales amount", "net sales (ex vat)", "net sales excl vat"])
    shipping_col = _find_col(cols, ["shipping", "shipping charges", "shipping amount", "shipping revenue"])

    if net_sales_col and shipping_col:
        net_sales = pd.to_numeric(df[net_sales_col], errors="coerce").fillna(0.0)
        shipping = pd.to_numeric(df[shipping_col], errors="coerce").fillna(0.0)
        df["adjusted_net_revenue"] = net_sales + shipping
        df["_rev_net_sales_source"] = net_sales_col
        df["_rev_shipping_source"] = shipping_col
    else:
        col_f = pd.to_numeric(df.iloc[:, 5], errors="coerce").fillna(0.0)
        col_g = pd.to_numeric(df.iloc[:, 6], errors="coerce").fillna(0.0)
        df["adjusted_net_revenue"] = col_f + col_g
        df["_rev_net_sales_source"] = "F (fallback)"
        df["_rev_shipping_source"] = "G (fallback)"

    country_col = _find_col(list(df.columns), ["shipping country", "shipping location", "country", "land"])
    net_col = _find_col(list(df.columns), ["net sales", "net_sales", "net"])
    orders_col = _find_col(list(df.columns), ["orders", "order count", "antal order", "beställningar"])

    if not country_col or not net_col or not orders_col:
        raise ValueError(
            "Could not detect required columns in sales-by-location file. Need country + Net sales + Orders."
        )

    df[country_col] = df[country_col].astype(str)
    df[net_col] = _to_number(df[net_col]).fillna(0.0)
    df[orders_col] = _to_number(df[orders_col]).fillna(0.0)

    df["region"] = df[country_col].apply(classify_region)

    net_se = float(df.loc[df["region"] == "SE", "adjusted_net_revenue"].sum())    
    ord_se = float(df.loc[df["region"] == "SE", orders_col].sum())
    ord_ot = float(df.loc[df["region"] == "OTHER", orders_col].sum())

    net_ot = float(df.loc[df["region"] == "OTHER", net_col].sum())
    net_ot = float(df.loc[df["region"] == "OTHER", "adjusted_net_revenue"].sum())

    return RevenueOrders(
        net_rev_se=net_se,
        orders_se=ord_se,
        net_rev_other=net_ot,
        orders_other=ord_ot,
        net_sales_source=str(df["_rev_net_sales_source"].iloc[0]) if "_rev_net_sales_source" in df.columns and len(df) else "unknown",
        shipping_source=str(df["_rev_shipping_source"].iloc[0]) if "_rev_shipping_source" in df.columns and len(df) else "unknown",
    )


@dataclass
class CogsResult:
    cogs_se: float
    cogs_other: float
    coverage_pct: float
    unmatched: pd.DataFrame
    missing_country: pd.DataFrame
    returns_adjustments: pd.DataFrame
    meta: Dict[str, str]


def compute_cogs_from_orders_export(orders_export_csv_bytes: bytes, costs: Costs) -> CogsResult:
    import io
    df = pd.read_csv(io.BytesIO(orders_export_csv_bytes), low_memory=False)
    df = _norm_cols(df)
    # Adjusted net revenue = Column F + Column G
    # (0-based indexing: F = index 5, G = index 6)

    col_f = df.iloc[:, 5]
    col_g = df.iloc[:, 6]

    # Ensure numeric
    col_f = pd.to_numeric(col_f, errors="coerce").fillna(0.0)
    col_g = pd.to_numeric(col_g, errors="coerce").fillna(0.0)

    df["adjusted_net_revenue"] = col_f + col_g

    qty_col = _find_col(list(df.columns), ["lineitem quantity", "line item quantity", "quantity", "antal"])
    sku_col = _find_col(list(df.columns), ["lineitem sku", "line item sku", "sku", "artikelnummer"])
    country_col = _find_col(
    list(df.columns),
    ["shipping country", "shipping country code", "shipping address country", "shipping address country code", "shipping country name", "shipping country (shipping)", "shipping country/region", "shipping country region", "shipping address country (shipping)"]
    )

    if not qty_col or not sku_col:
        raise ValueError("Could not detect required columns in orders export. Need Lineitem quantity + Lineitem sku.")

    # Only line rows (Shopify exports often include header/summary rows)
    df_line = df[df[qty_col].notna() & df[sku_col].notna()].copy()
    df_line = df_line[df_line[sku_col].astype(str).str.strip() != ""].copy()

    df_line[qty_col] = _to_number(df_line[qty_col]).fillna(0.0)
    df_line[sku_col] = df_line[sku_col].astype(str).str.strip()

    # Identify returns/adjustments
    returns = df_line[df_line[qty_col] <= 0].copy()
    df_line_pos = df_line[df_line[qty_col] > 0].copy()

    # Do NOT classify by region for COGS
    missing_country = pd.DataFrame()
    

    # Join COGS via dict
    df_line_pos["cogs_per_unit"] = df_line_pos[sku_col].map(costs.cogs_by_sku)
    matched_mask = df_line_pos["cogs_per_unit"].notna()
    matched = df_line_pos[matched_mask].copy()
    unmatched = df_line_pos[~matched_mask].copy()

    matched["line_cogs"] = matched[qty_col] * matched["cogs_per_unit"].astype(float)

    cogs_se = float(matched["line_cogs"].sum())
    cogs_ot = 0.0

    coverage_pct = 0.0
    if len(df_line_pos) > 0:
        coverage_pct = float(matched_mask.mean() * 100.0)

    # Unmatched summary
    if not unmatched.empty:
        unmatched_summary = (
            unmatched.groupby(sku_col, dropna=False)
            .agg(line_rows=(sku_col, "count"), total_qty=(qty_col, "sum"))
            .reset_index()
            .rename(columns={sku_col: "sku"})
            .sort_values(["total_qty", "line_rows"], ascending=False)
        )
    else:
        unmatched_summary = pd.DataFrame(columns=["sku", "line_rows", "total_qty"])

    # Returns summary
    if not returns.empty:
        returns_summary = (
            returns.groupby(sku_col, dropna=False)
            .agg(line_rows=(sku_col, "count"), total_qty=(qty_col, "sum"))
            .reset_index()
            .rename(columns={sku_col: "sku"})
            .sort_values(["total_qty", "line_rows"])
        )
    else:
        returns_summary = pd.DataFrame(columns=["sku", "line_rows", "total_qty"])

    return CogsResult(
        cogs_se=cogs_se,
        cogs_other=cogs_ot,
        coverage_pct=coverage_pct,
        unmatched=unmatched_summary,
        missing_country=missing_country,
        returns_adjustments=returns_summary,
        meta={"qty_col": qty_col, "sku_col": sku_col, "country_col": country_col or ""},
    )