import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Retail Sales Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Retail Sales Dashboard")

st.caption(
    "Interactive analysis of fulfilled retail orders "
    "(Completed and Shipped)"
)


# ============================================================
# 2. HELPER FUNCTION FOR NUMERIC CLEANING
# ============================================================

def clean_money(series):
    """
    Convert values such as:

        1,250.50
        ₱1,250.50
        1250.50

    into numeric values.

    Invalid values become NaN.
    """

    return pd.to_numeric(
        series.astype("string")
        .str.replace("₱", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


# ============================================================
# 3. LOAD AND PREPARE THE ORIGINAL RETAIL DATA
# ============================================================

@st.cache_data
def load_and_prepare_data():

    # --------------------------------------------------------
    # A. READ THE ORIGINAL CSV FILES
    # --------------------------------------------------------

    customers = pd.read_csv(
        "data/customers.csv"
    )

    products = pd.read_csv(
        "data/products.csv"
    )

    orders = pd.read_csv(
        "data/orders.csv"
    )

    items = pd.read_csv(
        "data/order_items.csv"
    )


    # --------------------------------------------------------
    # B. REMOVE EXACT DUPLICATES
    # --------------------------------------------------------

    customers = (
        customers
        .drop_duplicates()
        .copy()
    )

    products = (
        products
        .drop_duplicates()
        .copy()
    )

    orders = (
        orders
        .drop_duplicates()
        .copy()
    )

    items = (
        items
        .drop_duplicates()
        .copy()
    )


    # --------------------------------------------------------
    # C. CLEAN PRODUCT CATEGORIES
    # --------------------------------------------------------

    category_map = {

        "electronics": "Electronics",
        "elec": "Electronics",

        "home & kitchen": "Home & Kitchen",
        "home and kitchen": "Home & Kitchen",

        "books": "Books",
        "book": "Books",

        "groceries": "Groceries",
        "grocery": "Groceries",

        "toys": "Toys",
        "toy": "Toys",

        "beauty": "Beauty",
        "beauty & care": "Beauty",

        "fashion": "Fashion",
        "fashon": "Fashion",

        "sports": "Sports",
        "sports & outdoor": "Sports",
    }


    products["category_clean"] = (

        products["category"]

        .astype("string")

        .str.strip()

        .str.lower()

        .replace(category_map)

        .fillna("Unknown")
    )


    # --------------------------------------------------------
    # D. CLEAN ORDER ITEM VALUES
    # --------------------------------------------------------

    items["quantity"] = pd.to_numeric(
        items["quantity"],
        errors="coerce",
    )


    items["unit_price_clean"] = clean_money(
        items["unit_price_at_purchase"]
    )


    # Keep valid quantity and price rows only

    items = items[
        (items["quantity"] > 0)
        &
        items["unit_price_clean"].notna()
    ].copy()


    # --------------------------------------------------------
    # E. CLEAN ORDERS
    # --------------------------------------------------------

    # Your dataset contains several date formats.
    # format="mixed" allows Pandas to interpret them.

    orders["order_date"] = pd.to_datetime(
        orders["order_datetime"],
        format="mixed",
        errors="coerce",
    )


    # Convert discount to numeric

    orders["discount_pct"] = pd.to_numeric(
        orders["discount_pct"],
        errors="coerce",
    )


    # Missing discount means no discount

    orders["discount_pct"] = (
        orders["discount_pct"]
        .fillna(0)
    )


    # Convert shipping fee

    orders["shipping_fee"] = pd.to_numeric(
        orders["shipping_fee"],
        errors="coerce",
    )


    # Keep valid discount percentages only.
    # Example:
    # 0.10 = 10%
    # 0.25 = 25%

    orders.loc[
        ~orders["discount_pct"].between(
            0,
            1
        ),
        "discount_pct"
    ] = 0


    # --------------------------------------------------------
    # F. REFERENTIAL INTEGRITY
    # --------------------------------------------------------

    # Remove orders whose customer_id does not exist
    # in the customer master file.

    orders = orders[
        orders["customer_id"].isin(
            customers["customer_id"]
        )
    ].copy()


    # Remove order items whose product does not exist

    items = items[
        items["product_id"].isin(
            products["product_id"]
        )
    ].copy()


    # Remove order items whose order does not exist

    items = items[
        items["order_id"].isin(
            orders["order_id"]
        )
    ].copy()


    # --------------------------------------------------------
    # G. BUILD ITEM-LEVEL ANALYTICAL DATAFRAME
    # --------------------------------------------------------

    sales = (

        items

        .merge(
            orders,
            on="order_id",
            how="inner",
            validate="many_to_one",
        )

        .merge(
            products[
                [
                    "product_id",
                    "product_name",
                    "brand",
                    "category_clean",
                ]
            ],
            on="product_id",
            how="inner",
            validate="many_to_one",
        )

        .merge(
            customers[
                [
                    "customer_id",
                    "region_name",
                    "city",
                    "loyalty_tier",
                ]
            ],
            on="customer_id",
            how="left",
            validate="many_to_one",
        )
    )


    # --------------------------------------------------------
    # H. CREATE ANALYTICAL FIELDS
    # --------------------------------------------------------

    # Gross Sales
    #
    # Quantity × Unit Price

    sales["gross_sales"] = (

        sales["quantity"]

        *

        sales["unit_price_clean"]
    )


    # Net Sales
    #
    # Gross Sales after discount

    sales["net_sales"] = (

        sales["gross_sales"]

        *

        (
            1
            -
            sales["discount_pct"]
        )
    )


    # Create month column

    sales["month"] = (

        sales["order_date"]

        .dt.to_period("M")

        .astype("string")
    )


    # --------------------------------------------------------
    # I. KEEP ONLY FULFILLED ORDERS
    # --------------------------------------------------------

    fulfilled_sales = sales[

        sales["order_status"].isin(
            [
                "Completed",
                "Shipped",
            ]
        )

    ].copy()


    # Remove rows with unparseable dates

    fulfilled_sales = fulfilled_sales[

        fulfilled_sales[
            "order_date"
        ].notna()

    ].copy()


    return fulfilled_sales


# ============================================================
# 4. LOAD DATA
# ============================================================

try:

    sales = load_and_prepare_data()

except FileNotFoundError as error:

    st.error(
        "A required CSV file was not found. "
        "Check your data folder and filenames."
    )

    st.code(
        """
data/
├── customers.csv
├── products.csv
├── orders.csv
└── order_items.csv
        """
    )

    st.exception(error)

    st.stop()


# ============================================================
# 5. SIDEBAR FILTERS
# ============================================================

st.sidebar.header(
    "Dashboard Filters"
)


# ---------------- Month ----------------

month_options = [

    "All"

] + sorted(

    sales["month"]

    .dropna()

    .astype(str)

    .unique()

    .tolist()
)


# ---------------- Region ----------------

region_options = [

    "All"

] + sorted(

    sales["region_name"]

    .dropna()

    .astype(str)

    .unique()

    .tolist()
)


# ---------------- Sales Channel ----------------

channel_options = [

    "All"

] + sorted(

    sales["sales_channel"]

    .dropna()

    .astype(str)

    .unique()

    .tolist()
)


# ---------------- Product Category ----------------

category_options = [

    "All"

] + sorted(

    sales["category_clean"]

    .dropna()

    .astype(str)

    .unique()

    .tolist()
)


# Display filters

selected_month = st.sidebar.selectbox(
    "Month",
    month_options,
)


selected_region = st.sidebar.selectbox(
    "Region",
    region_options,
)


selected_channel = st.sidebar.selectbox(
    "Sales Channel",
    channel_options,
)


selected_category = st.sidebar.selectbox(
    "Product Category",
    category_options,
)


# ============================================================
# 6. APPLY FILTERS
# ============================================================

filtered = sales.copy()


if selected_month != "All":

    filtered = filtered[
        filtered["month"]
        ==
        selected_month
    ]


if selected_region != "All":

    filtered = filtered[
        filtered["region_name"]
        ==
        selected_region
    ]


if selected_channel != "All":

    filtered = filtered[
        filtered["sales_channel"]
        ==
        selected_channel
    ]


if selected_category != "All":

    filtered = filtered[
        filtered["category_clean"]
        ==
        selected_category
    ]


# ============================================================
# 7. HANDLE EMPTY FILTER RESULTS
# ============================================================

if filtered.empty:

    st.warning(
        "No records match the selected filters. "
        "Please change one or more filters."
    )

    st.stop()


# ============================================================
# 8. KPI CALCULATIONS
# ============================================================


# ------------------------------------------------------------
# Gross Sales
# ------------------------------------------------------------

total_gross_sales = (
    filtered["gross_sales"]
    .sum()
)


# ------------------------------------------------------------
# Net Sales
# ------------------------------------------------------------

total_net_sales = (
    filtered["net_sales"]
    .sum()
)


# ------------------------------------------------------------
# Number of Unique Orders
# ------------------------------------------------------------

order_count = (

    filtered["order_id"]

    .nunique()
)


# ------------------------------------------------------------
# Average Order Value
# ------------------------------------------------------------

# IMPORTANT:
#
# We must calculate AOV at ORDER LEVEL.
#
# We should NOT calculate:
#
# filtered["net_sales"].mean()
#
# because that would calculate average
# LINE-ITEM value instead of average ORDER value.


order_values = (

    filtered

    .groupby(
        "order_id",
        as_index=False,
    )["net_sales"]

    .sum()

    .rename(
        columns={
            "net_sales":
            "order_value"
        }
    )
)


aov = (
    order_values[
        "order_value"
    ]
    .mean()
)


# ------------------------------------------------------------
# Top Category
# ------------------------------------------------------------

top_category = (

    filtered

    .groupby(
        "category_clean"
    )["gross_sales"]

    .sum()

    .idxmax()
)


# ============================================================
# 9. KPI CARDS
# ============================================================

st.subheader(
    "Key Performance Indicators"
)


kpi1, kpi2, kpi3, kpi4 = (
    st.columns(4)
)


kpi1.metric(
    "Gross Sales",
    f"₱{total_gross_sales:,.2f}",
)


kpi2.metric(
    "Fulfilled Orders",
    f"{order_count:,}",
)


kpi3.metric(
    "Average Order Value",
    f"₱{aov:,.2f}",
)


kpi4.metric(
    "Top Category",
    top_category,
)


st.caption(
    f"Net sales after order discounts: "
    f"₱{total_net_sales:,.2f}"
)


# ============================================================
# 10. MONTHLY SALES TREND
# ============================================================

st.subheader(
    "Sales Trend"
)


monthly_sales = (

    filtered

    .groupby(
        "month",
        as_index=False,
    )["gross_sales"]

    .sum()

    .sort_values(
        "month"
    )
)


fig_month = px.line(

    monthly_sales,

    x="month",

    y="gross_sales",

    markers=True,

    title="Monthly Gross Sales",

    labels={
        "month":
        "Month",

        "gross_sales":
        "Gross Sales (PHP)",
    },
)


fig_month.update_layout(

    yaxis_tickprefix="₱",

    yaxis_tickformat=",.0f",
)


st.plotly_chart(
    fig_month,
    width="stretch",
)


# ============================================================
# 11. CATEGORY AND REGION COMPARISON
# ============================================================

left, right = st.columns(2)


# ------------------------------------------------------------
# Product Category Sales
# ------------------------------------------------------------

category_sales = (

    filtered

    .groupby(
        "category_clean",
        as_index=False,
    )["gross_sales"]

    .sum()

    .sort_values(
        "gross_sales"
    )
)


fig_category = px.bar(

    category_sales,

    x="gross_sales",

    y="category_clean",

    orientation="h",

    title=(
        "Gross Sales "
        "by Product Category"
    ),

    labels={
        "gross_sales":
        "Gross Sales (PHP)",

        "category_clean":
        "Product Category",
    },
)


fig_category.update_layout(

    xaxis_tickprefix="₱",

    xaxis_tickformat=",.0f",
)


with left:

    st.plotly_chart(
        fig_category,
        width="stretch",
    )


# ------------------------------------------------------------
# Region Sales
# ------------------------------------------------------------

region_sales = (

    filtered

    .groupby(
        "region_name",
        as_index=False,
    )["gross_sales"]

    .sum()

    .sort_values(
        "gross_sales"
    )
)


fig_region = px.bar(

    region_sales,

    x="gross_sales",

    y="region_name",

    orientation="h",

    title="Gross Sales by Region",

    labels={
        "gross_sales":
        "Gross Sales (PHP)",

        "region_name":
        "Region",
    },
)


fig_region.update_layout(

    xaxis_tickprefix="₱",

    xaxis_tickformat=",.0f",
)


with right:

    st.plotly_chart(
        fig_region,
        width="stretch",
    )


# ============================================================
# 12. ORDER VALUE DISTRIBUTION
# ============================================================

left2, right2 = st.columns(2)


fig_distribution = px.histogram(

    order_values,

    x="order_value",

    nbins=30,

    title="Order Value Distribution",

    labels={
        "order_value":
        "Net Order Value (PHP)",
    },
)


fig_distribution.update_layout(

    xaxis_tickprefix="₱",

    xaxis_tickformat=",.0f",

    yaxis_title=(
        "Number of Orders"
    ),
)


with left2:

    st.plotly_chart(
        fig_distribution,
        width="stretch",
    )


# ============================================================
# 13. SALES CHANNEL COMPARISON
# ============================================================

channel_sales = (

    filtered

    .groupby(
        "sales_channel",
        as_index=False,
    )["gross_sales"]

    .sum()

    .sort_values(
        "gross_sales",
        ascending=False,
    )
)


fig_channel = px.bar(

    channel_sales,

    x="sales_channel",

    y="gross_sales",

    title=(
        "Gross Sales "
        "by Sales Channel"
    ),

    labels={
        "sales_channel":
        "Sales Channel",

        "gross_sales":
        "Gross Sales (PHP)",
    },
)


fig_channel.update_layout(

    yaxis_tickprefix="₱",

    yaxis_tickformat=",.0f",
)


with right2:

    st.plotly_chart(
        fig_channel,
        width="stretch",
    )


# ============================================================
# 14. TOP PRODUCTS
# ============================================================

st.subheader(
    "Top Products"
)


top_products = (

    filtered

    .groupby(
        "product_name",
        as_index=False,
    )["gross_sales"]

    .sum()

    .sort_values(
        "gross_sales",
        ascending=False,
    )

    .head(10)

    .sort_values(
        "gross_sales"
    )
)


fig_products = px.bar(

    top_products,

    x="gross_sales",

    y="product_name",

    orientation="h",

    title=(
        "Top 10 Products "
        "by Gross Sales"
    ),

    labels={
        "gross_sales":
        "Gross Sales (PHP)",

        "product_name":
        "Product",
    },
)


fig_products.update_layout(

    xaxis_tickprefix="₱",

    xaxis_tickformat=",.0f",
)


st.plotly_chart(
    fig_products,
    width="stretch",
)


# ============================================================
# 15. FILTERED TRANSACTION TABLE
# ============================================================

with st.expander(
    "View Filtered Transaction Details"
):

    detail_columns = [

        "order_id",

        "order_date",

        "product_name",

        "category_clean",

        "quantity",

        "unit_price_clean",

        "region_name",

        "city",

        "sales_channel",

        "discount_pct",

        "gross_sales",

        "net_sales",
    ]


    detail = (

        filtered[
            detail_columns
        ]

        .sort_values(
            "order_date",
            ascending=False,
        )

        .copy()
    )


    st.dataframe(
        detail,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# 16. ABOUT THE DASHBOARD
# ============================================================

with st.expander(
    "About this Dashboard"
):

    st.write(
        """
        This dashboard uses the original retail CSV files.

        The application performs basic cleaning before analysis:

        - removes exact duplicate records
        - standardizes product categories
        - converts unit prices to numeric values
        - removes zero or negative quantities
        - parses mixed order-date formats
        - fills missing discounts with zero
        - validates customer, order, and product references
        - keeps Completed and Shipped orders for sales analysis

        Gross Sales:

        Quantity × Unit Price

        Net Sales:

        Gross Sales × (1 − Discount Percentage)

        Average Order Value is calculated at the order level,
        not at the order-item level.
        """
    )


    st.write(
        "Filtered item rows:",
        f"{len(filtered):,}",
    )


    st.write(
        "Filtered unique orders:",
        f"{order_count:,}",
    )