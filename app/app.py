"""
Cloud Kitchen & Food Delivery Management — Streamlit Dashboard
================================================================
Front-end for the SQL project. Reads from a MySQL database (see
database/schema.sql + database/seed_data.py, and .env.example for
connection settings).

Run:  streamlit run app/app.py
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

# ----------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "database"))
import db_config  # noqa: E402  (needs the sys.path tweak above)

st.set_page_config(
    page_title="Cloud Kitchen & Food Delivery Management",
    page_icon="🍔",
    layout="wide",
)


@st.cache_resource
def get_engine():
    return create_engine(db_config.SQLALCHEMY_URL, pool_pre_ping=True)


def run_query(query, params=None):
    engine = get_engine()
    return pd.read_sql_query(query, engine, params=params)


def run_write(query, params=None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(query, params or ())


try:
    with get_engine().connect():
        pass
except Exception as e:
    st.error(
        f"Could not connect to MySQL database `{db_config.DB_NAME}` at "
        f"`{db_config.DB_HOST}:{db_config.DB_PORT}`.\n\n"
        f"Details: {e}\n\n"
        "Make sure MySQL is running, `.env` is configured (copy `.env.example`), "
        "the schema has been applied (`mysql -u <user> -p < database/schema.sql`), "
        "and the database has been seeded (`python database/seed_data.py`)."
    )
    st.stop()

# ----------------------------------------------------------------
# SIDEBAR NAV
# ----------------------------------------------------------------
st.sidebar.title("🍔 Cloud Kitchen")
st.sidebar.caption("Food Delivery Management System")
page = st.sidebar.radio(
    "Navigate",
    [
        "📊 Dashboard",
        "🕒 Today's Orders",
        "🏆 Top Restaurants",
        "🚴 Pending Deliveries",
        "⚡ Trigger Demo",
        "🧾 Browse Tables",
        "🧠 Run Custom SQL",
        "🗺️ ER Model",
    ],
)

st.sidebar.divider()
st.sidebar.caption(f"DB: `{db_config.DB_NAME}` @ {db_config.DB_HOST}:{db_config.DB_PORT}")
st.sidebar.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")

# ==================================================================
# PAGE 1 — DASHBOARD (KPIs + charts)
# ==================================================================
if page == "📊 Dashboard":
    st.title("📊 Business Dashboard")

    kpi = run_query("""
        SELECT
            (SELECT COUNT(*) FROM Orders) AS total_orders,
            (SELECT COUNT(*) FROM Orders WHERE status='Delivered') AS delivered,
            (SELECT COUNT(*) FROM Orders WHERE status='Cancelled') AS cancelled,
            (SELECT ROUND(SUM(total_amount),2) FROM Orders WHERE status!='Cancelled') AS revenue,
            (SELECT COUNT(*) FROM Restaurants WHERE is_active=1) AS active_restaurants,
            (SELECT COUNT(*) FROM Drivers WHERE is_active=1) AS active_drivers,
            (SELECT ROUND(AVG(rating),2) FROM Restaurants) AS avg_rating
    """).iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Orders", int(kpi.total_orders))
    c2.metric("Delivered", int(kpi.delivered))
    c3.metric("Cancelled", int(kpi.cancelled))
    c4.metric("Revenue (₹)", f"{kpi.revenue:,.0f}")
    c5.metric("Avg Restaurant Rating", f"{kpi.avg_rating:.2f} ⭐")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Orders by Status")
        df_status = run_query("SELECT status, COUNT(*) as count FROM Orders GROUP BY status")
        fig = px.pie(df_status, names="status", values="count", hole=0.45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Revenue by Cuisine")
        df_cuisine = run_query("""
            SELECT r.cuisine, ROUND(SUM(o.total_amount),2) as revenue
            FROM Orders o JOIN Restaurants r ON r.restaurant_id = o.restaurant_id
            WHERE o.status != 'Cancelled'
            GROUP BY r.cuisine ORDER BY revenue DESC
        """)
        fig2 = px.bar(df_cuisine, x="cuisine", y="revenue", color="cuisine")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Orders Trend (last 30 days)")
    df_trend = run_query("""
        SELECT DATE(order_date) as day, COUNT(*) as orders
        FROM Orders
        WHERE DATE(order_date) >= CURDATE() - INTERVAL 30 DAY
        GROUP BY day ORDER BY day
    """)
    if not df_trend.empty:
        fig3 = px.line(df_trend, x="day", y="orders", markers=True)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No orders in the last 30 days.")

    st.subheader("Payment Method Split")
    df_pay = run_query("""
        SELECT payment_method, COUNT(*) as count, ROUND(SUM(amount),2) as amount
        FROM Payments WHERE payment_status='Success' GROUP BY payment_method
    """)
    fig4 = px.bar(df_pay, x="payment_method", y="amount", text="count",
                  labels={"amount": "Amount (₹)"})
    st.plotly_chart(fig4, use_container_width=True)

# ==================================================================
# PAGE 2 — TODAY'S ORDERS  (VIEW: vw_todays_orders)
# ==================================================================
elif page == "🕒 Today's Orders":
    st.title("🕒 Today's Orders")
    st.caption("Backed by SQL view `vw_todays_orders`")

    df = run_query("SELECT * FROM vw_todays_orders")
    st.metric("Orders placed today", len(df))

    status_filter = st.multiselect(
        "Filter by status", options=sorted(df["status"].unique()) if not df.empty else [],
        default=list(df["status"].unique()) if not df.empty else [],
    )
    if not df.empty:
        df = df[df["status"].isin(status_filter)]
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("View SQL"):
        st.code(
            "CREATE VIEW vw_todays_orders AS\n"
            "SELECT o.order_id, c.name AS customer_name, r.name AS restaurant_name,\n"
            "       o.status, o.total_amount, o.order_date\n"
            "FROM Orders o\n"
            "JOIN Customers c   ON c.customer_id   = o.customer_id\n"
            "JOIN Restaurants r ON r.restaurant_id = o.restaurant_id\n"
            "WHERE DATE(o.order_date) = CURDATE()\n"
            "ORDER BY o.order_date DESC;",
            language="sql",
        )

# ==================================================================
# PAGE 3 — TOP RESTAURANTS  (VIEW: vw_top_restaurants)
# ==================================================================
elif page == "🏆 Top Restaurants":
    st.title("🏆 Top Restaurants")
    st.caption("Backed by SQL view `vw_top_restaurants`")

    df = run_query("SELECT * FROM vw_top_restaurants")
    top_n = st.slider("Show top N", 3, len(df) if len(df) else 3, min(10, len(df)) if len(df) else 3)
    df_show = df.head(top_n)

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    fig = px.bar(
        df_show.sort_values("rating"), x="rating", y="name", orientation="h",
        color="total_orders", labels={"rating": "Rating", "name": "Restaurant"},
        color_continuous_scale="oranges",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View SQL"):
        st.code(
            "CREATE VIEW vw_top_restaurants AS\n"
            "SELECT r.restaurant_id, r.name, r.cuisine, r.city, r.rating,\n"
            "       COUNT(o.order_id) AS total_orders,\n"
            "       COALESCE(SUM(o.total_amount),0) AS total_revenue\n"
            "FROM Restaurants r\n"
            "LEFT JOIN Orders o ON o.restaurant_id = r.restaurant_id\n"
            "GROUP BY r.restaurant_id, r.name, r.cuisine, r.city, r.rating\n"
            "ORDER BY r.rating DESC, total_orders DESC;",
            language="sql",
        )

# ==================================================================
# PAGE 4 — PENDING DELIVERIES  (VIEW: vw_pending_deliveries)
# ==================================================================
elif page == "🚴 Pending Deliveries":
    st.title("🚴 Pending Deliveries")
    st.caption("Backed by SQL view `vw_pending_deliveries`")

    df = run_query("SELECT * FROM vw_pending_deliveries")
    st.metric("Deliveries in progress", len(df))
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("View SQL"):
        st.code(
            "CREATE VIEW vw_pending_deliveries AS\n"
            "SELECT d.delivery_id, o.order_id, c.name AS customer_name,\n"
            "       r.name AS restaurant_name, dr.name AS driver_name,\n"
            "       d.delivery_status, d.pickup_time, o.order_date\n"
            "FROM Deliveries d\n"
            "JOIN Orders o        ON o.order_id       = d.order_id\n"
            "JOIN Customers c     ON c.customer_id    = o.customer_id\n"
            "JOIN Restaurants r   ON r.restaurant_id  = o.restaurant_id\n"
            "LEFT JOIN Drivers dr ON dr.driver_id     = d.driver_id\n"
            "WHERE d.delivery_status NOT IN ('Delivered','Cancelled')\n"
            "ORDER BY o.order_date ASC;",
            language="sql",
        )

# ==================================================================
# PAGE 5 — TRIGGER DEMO
# ==================================================================
elif page == "⚡ Trigger Demo":
    st.title("⚡ Trigger Demo: Order Delivered → Increase Restaurant Rating")
    st.markdown(
        "This page lets you **fire the trigger live**. Pick a delivery that "
        "isn't yet `Delivered`, mark it delivered, and watch the restaurant's "
        "rating update automatically — no application code computes the new "
        "rating, the database trigger does it."
    )

    with st.expander("View trigger SQL"):
        st.code(
            "CREATE TRIGGER trg_order_delivered_bump_rating\n"
            "AFTER UPDATE ON Deliveries\n"
            "FOR EACH ROW\n"
            "BEGIN\n"
            "    IF NEW.delivery_status = 'Delivered' AND OLD.delivery_status != 'Delivered' THEN\n"
            "        UPDATE Orders SET status = 'Delivered' WHERE order_id = NEW.order_id;\n\n"
            "        UPDATE Restaurants\n"
            "        SET rating = LEAST(5.0, ROUND(rating + 0.01, 2))\n"
            "        WHERE restaurant_id = (SELECT restaurant_id FROM Orders WHERE order_id = NEW.order_id);\n"
            "    END IF;\n"
            "END;",
            language="sql",
        )

    df_pending = run_query("""
        SELECT d.delivery_id, o.order_id, r.name AS restaurant_name, r.rating,
               c.name AS customer_name, d.delivery_status
        FROM Deliveries d
        JOIN Orders o ON o.order_id = d.order_id
        JOIN Restaurants r ON r.restaurant_id = o.restaurant_id
        JOIN Customers c ON c.customer_id = o.customer_id
        WHERE d.delivery_status != 'Delivered'
        ORDER BY o.order_date DESC
        LIMIT 30
    """)

    if df_pending.empty:
        st.info("No pending deliveries left to demo — every order has been delivered. "
                 "Re-run `python database/seed_data.py` to reset sample data.")
    else:
        st.dataframe(df_pending, use_container_width=True, hide_index=True)

        options = [
            f"Delivery #{row.delivery_id} — Order #{row.order_id} — {row.restaurant_name} "
            f"(current rating {row.rating})"
            for row in df_pending.itertuples()
        ]
        choice = st.selectbox("Pick a delivery to mark as Delivered", options)
        delivery_id = int(choice.split("#")[1].split(" ")[0])

        before = run_query("""
            SELECT r.name, r.rating FROM Restaurants r
            JOIN Orders o ON o.restaurant_id = r.restaurant_id
            JOIN Deliveries d ON d.order_id = o.order_id
            WHERE d.delivery_id = %s
        """, params=(delivery_id,)).iloc[0]

        if st.button("🚀 Mark as Delivered (fire trigger)", type="primary"):
            run_write("UPDATE Deliveries SET delivery_status='Delivered' WHERE delivery_id=%s", (delivery_id,))
            after = run_query("""
                SELECT r.name, r.rating FROM Restaurants r
                JOIN Orders o ON o.restaurant_id = r.restaurant_id
                JOIN Deliveries d ON d.order_id = o.order_id
                WHERE d.delivery_id = %s
            """, params=(delivery_id,)).iloc[0]

            st.success(f"Delivery #{delivery_id} marked as Delivered — trigger fired ✅")
            c1, c2 = st.columns(2)
            c1.metric(f"{before['name']} rating (before)", f"{before.rating:.2f} ⭐")
            c2.metric(f"{after['name']} rating (after)", f"{after.rating:.2f} ⭐",
                       delta=f"{after.rating - before.rating:+.2f}")
            st.rerun()

# ==================================================================
# PAGE 6 — BROWSE TABLES
# ==================================================================
elif page == "🧾 Browse Tables":
    st.title("🧾 Browse Raw Tables")
    tables = [
        "Restaurants", "Menus", "Orders", "Order_Items", "Drivers",
        "Payments", "Offers", "Ratings", "Customers", "Coupons", "Deliveries",
    ]
    table = st.selectbox("Choose a table", tables)
    limit = st.slider("Rows to show", 10, 200, 50)
    df = run_query(f"SELECT * FROM {table} LIMIT {limit}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(df)} rows from `{table}`")

# ==================================================================
# PAGE 7 — CUSTOM SQL RUNNER
# ==================================================================
elif page == "🧠 Run Custom SQL":
    st.title("🧠 Run Custom SQL")
    st.caption("SELECT-only query console against the live database.")

    default_query = "SELECT * FROM vw_top_restaurants LIMIT 10;"
    query = st.text_area("SQL query", value=default_query, height=120)

    if st.button("Run Query"):
        q_clean = query.strip().rstrip(";").lower()
        if not q_clean.startswith("select"):
            st.error("Only SELECT queries are allowed in this console.")
        else:
            try:
                df = run_query(query)
                st.success(f"{len(df)} rows returned")
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Query error: {e}")

# ==================================================================
# PAGE 8 — ER MODEL
# ==================================================================
elif page == "🗺️ ER Model":
    st.title("🗺️ Entity–Relationship Model")
    st.markdown("""
**Core entities:** `Customers`, `Restaurants`, `Menus`, `Drivers`, `Coupons`, `Offers`

**Transaction chain:** `Orders → Order_Items → Payments → Deliveries → Ratings`

| Table | Key Relationships |
|---|---|
| Restaurants | 1 → many Menus, Offers, Orders |
| Customers | 1 → many Orders, Ratings |
| Orders | many → 1 Customer, Restaurant, Coupon (nullable) |
| Order_Items | many → 1 Order, many → 1 Menu |
| Payments | 1 → 1 Order |
| Deliveries | 1 → 1 Order, many → 1 Driver |
| Ratings | 1 → 1 Order, many → 1 Customer, many → 1 Restaurant |

**Trigger flow:**
`Deliveries.delivery_status → 'Delivered'`  ⟶  `Orders.status = 'Delivered'` + `Restaurants.rating` nudged up
`Ratings INSERT` ⟶ `Restaurants.rating` recalculated as true average

See the diagram shared in chat, or `database/ER_diagram.png` in the project folder for the full visual.
""")

st.sidebar.divider()
st.sidebar.caption("Built with MySQL + Streamlit + Plotly")
