"""
Builds/refreshes the `cloud_kitchen` MySQL database and populates it with
realistic sample data (restaurants, menus, customers, drivers, orders,
payments, deliveries, ratings, coupons, offers).

Prerequisite: apply the schema once (creates the DB, tables, triggers, views):
    mysql -u <user> -p < schema.sql

Run:
    python seed_data.py
"""

import random
from datetime import datetime, timedelta

import pymysql
from faker import Faker

from db_config import PYMYSQL_KWARGS

fake = Faker("en_IN")
random.seed(42)
Faker.seed(42)

CITIES = ["Kolkata", "Mumbai", "Bengaluru", "Delhi", "Hyderabad", "Pune", "Chennai"]
CUISINES = ["North Indian", "South Indian", "Chinese", "Italian", "Bakery",
            "Biryani", "Fast Food", "Desserts", "Beverages", "Continental"]
MENU_CATEGORIES = ["Starter", "Main Course", "Dessert", "Beverage", "Combo"]
VEHICLES = ["Bike", "Scooter", "Bicycle"]
PAYMENT_METHODS = ["UPI", "Card", "Cash", "Wallet"]

N_CUSTOMERS = 60
N_RESTAURANTS = 15
N_MENU_PER_RESTAURANT = (6, 12)
N_DRIVERS = 20
N_COUPONS = 8
N_OFFERS_PER_RESTAURANT = (0, 2)
N_ORDERS = 220


class Conn:
    """Thin sqlite3-style wrapper around a pymysql connection so the rest of
    this script (conn.execute / conn.executemany / cur.lastrowid / iterating
    a cursor) reads the same way it would against SQLite."""

    def __init__(self, connection):
        self._conn = connection

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def executemany(self, sql, rows):
        cur = self._conn.cursor()
        if rows:
            cur.executemany(sql, rows)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


TRUNCATE_ORDER = [
    "Ratings", "Deliveries", "Payments", "Order_Items", "Orders",
    "Offers", "Coupons", "Drivers", "Menus", "Restaurants", "Customers",
]


def fresh_db():
    raw = pymysql.connect(**PYMYSQL_KWARGS)
    conn = Conn(raw)
    # Clear existing data (schema/tables/triggers/views are assumed to
    # already exist -- run schema.sql first) rather than dropping tables,
    # so we don't need to re-parse DELIMITER-based trigger SQL here.
    conn.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in TRUNCATE_ORDER:
        conn.execute(f"TRUNCATE TABLE {table}")
    conn.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    return conn


def seed_customers(conn):
    rows = []
    for _ in range(N_CUSTOMERS):
        rows.append((
            fake.name(),
            fake.unique.email(),
            fake.msisdn()[:10],
            random.choice(CITIES),
            fake.date_between(start_date="-2y", end_date="-30d").isoformat(),
        ))
    conn.executemany(
        "INSERT INTO Customers (name, email, phone, city, joined_date) VALUES (%s,%s,%s,%s,%s)",
        rows,
    )
    conn.commit()


RESTAURANT_NAME_POOL = [
    "Spice Route", "Tandoori Nights", "Curry Leaf", "Wok This Way",
    "The Biryani House", "Bakers & Co.", "Chai Point Express", "Dosa Corner",
    "Pizza Junction", "Noodle Bar", "Sweet Tooth Bakery", "Grill Masters",
    "Green Bowl", "Punjabi Tadka", "Sushi Stop", "Momo Magic",
    "Cafe Aroma", "Rolls Royce Kathi Rolls", "Kebab Factory", "Urban Tadka",
]


def seed_restaurants(conn):
    names = random.sample(RESTAURANT_NAME_POOL, N_RESTAURANTS)
    rows = []
    for name in names:
        rows.append((
            name,
            random.choice(CUISINES),
            random.choice(CITIES),
            round(random.uniform(3.2, 4.6), 2),
            1,
        ))
    conn.executemany(
        "INSERT INTO Restaurants (name, cuisine, city, rating, is_active) VALUES (%s,%s,%s,%s,%s)",
        rows,
    )
    conn.commit()


MENU_ITEM_POOL = [
    "Paneer Butter Masala", "Chicken Biryani", "Veg Fried Rice", "Masala Dosa",
    "Margherita Pizza", "Cheese Burst Pizza", "Chowmein", "Momos (Veg)",
    "Momos (Chicken)", "Butter Naan", "Gulab Jamun", "Cold Coffee",
    "Masala Chai", "Chicken Tikka", "Veg Manchurian", "Mutton Rogan Josh",
    "Filter Coffee", "Idli Sambar", "Club Sandwich", "French Fries",
    "Chocolate Brownie", "Ice Cream Sundae", "Cold Drink (500ml)", "Water Bottle",
    "Egg Roll", "Chicken Roll", "Rasgulla", "Pav Bhaji",
]


def seed_menus(conn):
    restaurant_ids = [r[0] for r in conn.execute("SELECT restaurant_id FROM Restaurants")]
    rows = []
    for rid in restaurant_ids:
        n_items = random.randint(*N_MENU_PER_RESTAURANT)
        items = random.sample(MENU_ITEM_POOL, min(n_items, len(MENU_ITEM_POOL)))
        for item in items:
            rows.append((
                rid,
                item,
                random.choice(MENU_CATEGORIES),
                round(random.uniform(49, 499), 2),
                1,
            ))
    conn.executemany(
        "INSERT INTO Menus (restaurant_id, item_name, category, price, is_available) VALUES (%s,%s,%s,%s,%s)",
        rows,
    )
    conn.commit()


def seed_drivers(conn):
    rows = []
    for _ in range(N_DRIVERS):
        rows.append((
            fake.name(),
            fake.msisdn()[:10],
            random.choice(VEHICLES),
            round(random.uniform(3.5, 5.0), 2),
            1,
        ))
    conn.executemany(
        "INSERT INTO Drivers (name, phone, vehicle_type, rating, is_active) VALUES (%s,%s,%s,%s,%s)",
        rows,
    )
    conn.commit()


def seed_coupons(conn):
    rows = []
    for i in range(N_COUPONS):
        code = f"SAVE{random.randint(10,50)}" if i % 2 == 0 else f"WELCOME{random.randint(100,999)}"
        start = fake.date_between(start_date="-90d", end_date="-10d")
        end = start + timedelta(days=random.randint(30, 120))
        rows.append((
            code,
            random.choice([10, 15, 20, 25, 30]),
            random.choice([0, 99, 149, 199, 299]),
            start.isoformat(),
            end.isoformat(),
        ))
    # de-dupe codes
    seen = set()
    uniq_rows = []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0])
            uniq_rows.append(r)
    conn.executemany(
        "INSERT INTO Coupons (code, discount_percent, min_order_value, valid_from, valid_to) VALUES (%s,%s,%s,%s,%s)",
        uniq_rows,
    )
    conn.commit()


OFFER_TITLES = ["Flat Off Special", "Weekend Bonanza", "New User Treat", "Combo Saver"]


def seed_offers(conn):
    restaurant_ids = [r[0] for r in conn.execute("SELECT restaurant_id FROM Restaurants")]
    rows = []
    for rid in restaurant_ids:
        n = random.randint(*N_OFFERS_PER_RESTAURANT)
        for _ in range(n):
            start = fake.date_between(start_date="-60d", end_date="-5d")
            end = start + timedelta(days=random.randint(15, 60))
            rows.append((
                rid,
                random.choice(OFFER_TITLES),
                random.choice([10, 20, 25, 30, 40]),
                start.isoformat(),
                end.isoformat(),
            ))
    conn.executemany(
        "INSERT INTO Offers (restaurant_id, title, discount_percent, valid_from, valid_to) VALUES (%s,%s,%s,%s,%s)",
        rows,
    )
    conn.commit()


def seed_orders_and_children(conn):
    customer_ids = [c[0] for c in conn.execute("SELECT customer_id FROM Customers")]
    restaurant_ids = [r[0] for r in conn.execute("SELECT restaurant_id FROM Restaurants")]
    coupon_ids = [c[0] for c in conn.execute("SELECT coupon_id FROM Coupons")]
    driver_ids = [d[0] for d in conn.execute("SELECT driver_id FROM Drivers")]

    menus_by_restaurant = {}
    for rid in restaurant_ids:
        menus_by_restaurant[rid] = list(
            conn.execute("SELECT menu_id, price FROM Menus WHERE restaurant_id=%s", (rid,))
        )

    now = datetime.now()

    for i in range(N_ORDERS):
        customer_id = random.choice(customer_ids)
        restaurant_id = random.choice(restaurant_ids)
        menu_items = menus_by_restaurant[restaurant_id]
        if not menu_items:
            continue

        # spread orders: most in the past, ~12% "today", ~8% still in-flight
        r = random.random()
        if r < 0.12:
            order_dt = now - timedelta(minutes=random.randint(5, 400))
        elif r < 0.20:
            order_dt = now - timedelta(hours=random.randint(1, 20))
        else:
            order_dt = now - timedelta(days=random.randint(1, 90), hours=random.randint(0, 23))

        use_coupon = random.random() < 0.35
        coupon_id = random.choice(coupon_ids) if use_coupon else None

        chosen_items = random.sample(menu_items, k=min(random.randint(1, 4), len(menu_items)))
        order_total = 0.0
        item_rows = []
        for menu_id, price in chosen_items:
            price = float(price)
            qty = random.randint(1, 3)
            order_total += price * qty
            item_rows.append((menu_id, qty, price))

        if coupon_id:
            disc = conn.execute(
                "SELECT discount_percent FROM Coupons WHERE coupon_id=%s", (coupon_id,)
            ).fetchone()[0]
            order_total = order_total * (1 - float(disc) / 100)
        order_total = round(order_total, 2)

        # decide lifecycle stage
        is_today_recent = order_dt > now - timedelta(hours=20)
        if is_today_recent:
            stage = random.choices(
                ["Placed", "Preparing", "Out for Delivery", "Delivered", "Cancelled"],
                weights=[15, 20, 20, 40, 5],
            )[0]
        else:
            stage = random.choices(
                ["Delivered", "Cancelled"],
                weights=[93, 7],
            )[0]

        cur = conn.execute(
            "INSERT INTO Orders (customer_id, restaurant_id, coupon_id, order_date, status, total_amount) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (customer_id, restaurant_id, coupon_id, order_dt.strftime("%Y-%m-%d %H:%M:%S"), "Placed", order_total),
        )
        order_id = cur.lastrowid

        for menu_id, qty, price in item_rows:
            conn.execute(
                "INSERT INTO Order_Items (order_id, menu_id, quantity, item_price) VALUES (%s,%s,%s,%s)",
                (order_id, menu_id, qty, price),
            )

        if stage == "Cancelled":
            conn.execute("UPDATE Orders SET status='Cancelled' WHERE order_id=%s", (order_id,))
            conn.execute(
                "INSERT INTO Payments (order_id, amount, payment_method, payment_status, payment_date) "
                "VALUES (%s,%s,%s,%s,%s)",
                (order_id, order_total, random.choice(PAYMENT_METHODS), "Refunded",
                 order_dt.strftime("%Y-%m-%d %H:%M:%S")),
            )
            continue

        # Payment (mostly successful)
        pay_status = random.choices(["Success", "Pending", "Failed"], weights=[92, 5, 3])[0]
        conn.execute(
            "INSERT INTO Payments (order_id, amount, payment_method, payment_status, payment_date) "
            "VALUES (%s,%s,%s,%s,%s)",
            (order_id, order_total, random.choice(PAYMENT_METHODS), pay_status,
             order_dt.strftime("%Y-%m-%d %H:%M:%S")),
        )

        # Delivery record
        driver_id = random.choice(driver_ids)
        delivery_status_map = {
            "Placed": "Assigned",
            "Preparing": "Assigned",
            "Out for Delivery": "Picked Up",
            "Delivered": "Delivered",
        }
        delivery_status = delivery_status_map.get(stage, "Assigned")

        pickup_time = None
        delivery_time = None
        if delivery_status in ("Picked Up", "Delivered"):
            pickup_time = (order_dt + timedelta(minutes=random.randint(10, 25))).strftime("%Y-%m-%d %H:%M:%S")
        if delivery_status == "Delivered":
            delivery_time = (order_dt + timedelta(minutes=random.randint(30, 60))).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            "INSERT INTO Deliveries (order_id, driver_id, pickup_time, delivery_time, delivery_status) "
            "VALUES (%s,%s,%s,%s,%s)",
            (order_id, driver_id, pickup_time, delivery_time, "Assigned"),
        )

        # Now push the delivery through its real status via UPDATE so the
        # trigger fires exactly like it would in production
        if delivery_status in ("Picked Up", "Delivered"):
            conn.execute(
                "UPDATE Deliveries SET delivery_status='Picked Up' WHERE order_id=%s", (order_id,)
            )
        if delivery_status == "Delivered":
            conn.execute(
                "UPDATE Deliveries SET delivery_status='Delivered' WHERE order_id=%s", (order_id,)
            )
            # ~70% of delivered orders leave a rating -> fires 2nd trigger
            if random.random() < 0.7:
                conn.execute(
                    "INSERT INTO Ratings (order_id, customer_id, restaurant_id, rating_value, review_text, rating_date) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        order_id,
                        customer_id,
                        restaurant_id,
                        round(random.uniform(2.5, 5.0), 1),
                        random.choice([
                            "Great food, fast delivery!", "Good taste, packaging could improve.",
                            "Loved it, ordering again.", "Average experience.", "Food was cold on arrival.",
                            "Excellent quality and quick service.", None, None,
                        ]),
                        delivery_time,
                    ),
                )
        else:
            conn.execute(
                "UPDATE Deliveries SET delivery_status=%s WHERE order_id=%s", (delivery_status, order_id)
            )
            conn.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (stage, order_id))

    conn.commit()


def main():
    conn = fresh_db()
    seed_customers(conn)
    seed_restaurants(conn)
    seed_menus(conn)
    seed_drivers(conn)
    seed_coupons(conn)
    seed_offers(conn)
    seed_orders_and_children(conn)

    counts = {}
    for t in ["Customers", "Restaurants", "Menus", "Drivers", "Coupons", "Offers",
              "Orders", "Order_Items", "Payments", "Deliveries", "Ratings"]:
        counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print("Seeded MySQL database:", PYMYSQL_KWARGS["database"],
          f"@ {PYMYSQL_KWARGS['host']}:{PYMYSQL_KWARGS['port']}")
    for k, v in counts.items():
        print(f"  {k:15s}: {v}")
    conn.close()


if __name__ == "__main__":
    main()
