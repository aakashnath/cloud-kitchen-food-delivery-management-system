# 🍔 Cloud Kitchen & Food Delivery Management System (MySQL edition)

A full SQL project modeled on real-world platforms like **Swiggy, Zomato, and EatClub** —
with a normalized relational schema, a business-logic trigger, reporting views, and a
Streamlit dashboard front-end. This version runs on **MySQL** (converted from an
original SQLite implementation).

## Project structure

```
cloud_kitchen_project/
├── database/
│   ├── schema.sql          -> Tables, triggers, views (MySQL DDL — run this first)
│   ├── db_config.py         -> Shared MySQL connection config (env-driven)
│   └── seed_data.py         -> Truncates + fills the DB with sample data
├── app/
│   └── app.py                -> Streamlit dashboard (front-end)
├── requirements.txt
├── .env.example
└── README.md
```

## Prerequisites

- MySQL Server **8.0.16+** (needed for `CHECK` constraint enforcement)
- Python 3.9+

## How to run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure DB credentials
cp .env.example .env
# then edit .env with your MySQL host/user/password

# 3. Create the database, tables, triggers & views
mysql -u <user> -p < database/schema.sql

# 4. Seed it with sample data (60 customers, 15 restaurants, 220 orders, etc.)
python database/seed_data.py

# 5. Launch the dashboard
streamlit run app/app.py
```

`seed_data.py` truncates existing rows and reseeds every time you run it — handy for
resetting the "⚡ Trigger Demo" page once every delivery has been marked `Delivered`.

## Data model (11 tables)

| Table | Purpose |
|---|---|
| `Restaurants` | Partner restaurants / cloud kitchens |
| `Menus` | Menu items per restaurant |
| `Customers` | End users placing orders |
| `Drivers` | Delivery riders |
| `Coupons` | Platform-wide discount codes |
| `Offers` | Restaurant-specific promotions |
| `Orders` | One row per customer order |
| `Order_Items` | Line items linking Orders ↔ Menus (junction table) |
| `Payments` | 1-to-1 with Orders |
| `Deliveries` | 1-to-1 with Orders, linked to a Driver |
| `Ratings` | Customer feedback after delivery |

Full relational diagram is in `database/schema.sql` (foreign keys) and rendered as an
ER diagram in the dashboard's "ER Model" tab.

## Trigger: `Order Delivered → Increase Restaurant Rating`

Two triggers implement this business rule end-to-end:

1. **`trg_order_delivered_bump_rating`** — fires whenever a row in `Deliveries` is
   updated; an `IF` inside the trigger body checks that `delivery_status` just flipped
   to `'Delivered'` (MySQL has no `AFTER UPDATE OF <column>` clause like SQLite/Postgres,
   so the column-changed check happens explicitly). It marks the parent `Orders.status`
   as `'Delivered'` and gives the restaurant's live rating a small automatic bump
   (capped at 5.0, via `LEAST()`) as an immediate "successful delivery" signal.
2. **`trg_rating_recalc_restaurant_avg`** — fires when a customer actually submits a
   star rating into `Ratings`. It recalculates the restaurant's `rating` as the true
   average of every rating it has ever received, overriding the bump with the real number.

Try it live in the Streamlit app under **⚡ Trigger Demo** — pick a pending delivery,
mark it delivered, and watch the restaurant's rating change in real time, driven entirely
by the database trigger (no application code computes the new value).

## Views (reporting layer)

| View | Description |
|---|---|
| `vw_todays_orders` | All orders placed today, with customer & restaurant names |
| `vw_top_restaurants` | Restaurants ranked by rating, with order count & revenue |
| `vw_pending_deliveries` | Deliveries not yet `Delivered` or `Cancelled` |

## Streamlit dashboard pages

- **📊 Dashboard** — KPIs, order status split, revenue by cuisine, 30-day trend, payment mix
- **🕒 Today's Orders** — live `vw_todays_orders`
- **🏆 Top Restaurants** — live `vw_top_restaurants` + chart
- **🚴 Pending Deliveries** — live `vw_pending_deliveries`
- **⚡ Trigger Demo** — fire the delivery trigger and see the rating update
- **🧾 Browse Tables** — raw table viewer for all 11 tables
- **🧠 Run Custom SQL** — ad-hoc SELECT query console
- **🗺️ ER Model** — relationship summary

## Tech stack

- **Database:** MySQL 8+ (schema uses `CHECK` constraints, `AUTO_INCREMENT`, `DELIMITER`-
  based triggers, and standard views)
- **Connectivity:** PyMySQL (raw DB-API for seeding), SQLAlchemy engine (for the app,
  works cleanly with `pandas.read_sql_query`)
- **Front-end:** Streamlit + Plotly
- **Sample data:** Faker (60 customers, 15 restaurants, 134 menu items, 20 drivers,
  220 orders with realistic order/payment/delivery/rating lifecycles)

## What changed from the SQLite version

- `schema.sql`: `AUTOINCREMENT` → `AUTO_INCREMENT`, `REAL` → `DECIMAL`, added
  `CREATE DATABASE`/`USE`, triggers rewritten with `DELIMITER $$ ... END$$` and an
  `IF` for the column-change check, `date('now')` → `CURDATE()`.
  `MIN(5.0, ...)` → `LEAST(5.0, ...)`.
- `seed_data.py`: `sqlite3` → `pymysql`, `?` placeholders → `%s`, file-based DB reset
  → `TRUNCATE TABLE` (schema/triggers are expected to already exist via `schema.sql`).
- `app.py`: `sqlite3` connection → cached SQLAlchemy engine (`db_config.py`), same
  `run_query`/`run_write` helper shape, `?` → `%s`, `date('now','-30 day')` →
  `CURDATE() - INTERVAL 30 DAY`, startup check now pings the DB instead of checking
  for a `.db` file.
