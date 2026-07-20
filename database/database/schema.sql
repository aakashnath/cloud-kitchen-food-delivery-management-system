-- ============================================================
-- CLOUD KITCHEN & FOOD DELIVERY MANAGEMENT SYSTEM
-- SQL Schema (MySQL 8.0+ dialect)
-- Inspired by: Swiggy / Zomato / EatClub
--
-- Run this with the mysql CLI, e.g.:
--   mysql -u root -p < database/schema.sql
-- (it creates the `cloud_kitchen` database itself)
-- ============================================================

CREATE DATABASE IF NOT EXISTS cloud_kitchen
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE cloud_kitchen;

-- Drop in child-to-parent order so FK constraints don't block re-runs
DROP TABLE IF EXISTS Ratings;
DROP TABLE IF EXISTS Deliveries;
DROP TABLE IF EXISTS Payments;
DROP TABLE IF EXISTS Order_Items;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS Offers;
DROP TABLE IF EXISTS Coupons;
DROP TABLE IF EXISTS Drivers;
DROP TABLE IF EXISTS Menus;
DROP TABLE IF EXISTS Restaurants;
DROP TABLE IF EXISTS Customers;

-- ------------------------------------------------------------
-- 1. CUSTOMERS
-- ------------------------------------------------------------
CREATE TABLE Customers (
    customer_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    city            VARCHAR(80) NOT NULL,
    joined_date     DATE NOT NULL DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. RESTAURANTS
-- ------------------------------------------------------------
CREATE TABLE Restaurants (
    restaurant_id   INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    cuisine         VARCHAR(80) NOT NULL,
    city            VARCHAR(80) NOT NULL,
    rating          DECIMAL(3,2) NOT NULL DEFAULT 3.5 CHECK (rating >= 0 AND rating <= 5),
    is_active       TINYINT(1) NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. MENUS  (menu items belong to a restaurant)
-- ------------------------------------------------------------
CREATE TABLE Menus (
    menu_id         INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id   INT NOT NULL,
    item_name       VARCHAR(150) NOT NULL,
    category        VARCHAR(50) NOT NULL,          -- Starter / Main / Dessert / Beverage
    price           DECIMAL(8,2) NOT NULL CHECK (price > 0),
    is_available    TINYINT(1) NOT NULL DEFAULT 1 CHECK (is_available IN (0,1)),
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. DRIVERS
-- ------------------------------------------------------------
CREATE TABLE Drivers (
    driver_id       INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    vehicle_type    VARCHAR(30) NOT NULL,          -- Bike / Scooter / Bicycle
    rating          DECIMAL(3,2) NOT NULL DEFAULT 4.0 CHECK (rating >= 0 AND rating <= 5),
    is_active       TINYINT(1) NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. COUPONS
-- ------------------------------------------------------------
CREATE TABLE Coupons (
    coupon_id           INT AUTO_INCREMENT PRIMARY KEY,
    code                VARCHAR(30) UNIQUE NOT NULL,
    discount_percent    DECIMAL(5,2) NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    min_order_value     DECIMAL(8,2) NOT NULL DEFAULT 0,
    valid_from          DATE NOT NULL,
    valid_to            DATE NOT NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 6. OFFERS  (restaurant-specific promotions)
-- ------------------------------------------------------------
CREATE TABLE Offers (
    offer_id            INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id       INT NOT NULL,
    title               VARCHAR(150) NOT NULL,
    discount_percent    DECIMAL(5,2) NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    valid_from          DATE NOT NULL,
    valid_to            DATE NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 7. ORDERS
-- ------------------------------------------------------------
CREATE TABLE Orders (
    order_id        INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    restaurant_id   INT NOT NULL,
    coupon_id       INT,                     -- nullable
    order_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'Placed'
                        CHECK (status IN ('Placed','Preparing','Out for Delivery','Delivered','Cancelled')),
    total_amount    DECIMAL(10,2) NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (customer_id)   REFERENCES Customers(customer_id),
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id),
    FOREIGN KEY (coupon_id)     REFERENCES Coupons(coupon_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 7b. ORDER_ITEMS  (junction: which menu items in which order)
-- ------------------------------------------------------------
CREATE TABLE Order_Items (
    order_item_id   INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL,
    menu_id         INT NOT NULL,
    quantity        INT NOT NULL CHECK (quantity > 0),
    item_price      DECIMAL(8,2) NOT NULL,   -- price at time of order
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (menu_id)  REFERENCES Menus(menu_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 8. PAYMENTS
-- ------------------------------------------------------------
CREATE TABLE Payments (
    payment_id      INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL UNIQUE,
    amount          DECIMAL(10,2) NOT NULL CHECK (amount >= 0),
    payment_method  VARCHAR(20) NOT NULL CHECK (payment_method IN ('UPI','Card','Cash','Wallet')),
    payment_status  VARCHAR(20) NOT NULL DEFAULT 'Pending'
                        CHECK (payment_status IN ('Pending','Success','Failed','Refunded')),
    payment_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 9. DELIVERIES
-- ------------------------------------------------------------
CREATE TABLE Deliveries (
    delivery_id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id            INT NOT NULL UNIQUE,
    driver_id           INT,
    pickup_time         DATETIME,
    delivery_time       DATETIME,
    delivery_status     VARCHAR(20) NOT NULL DEFAULT 'Assigned'
                            CHECK (delivery_status IN ('Assigned','Picked Up','Delivered','Delayed','Cancelled')),
    FOREIGN KEY (order_id)  REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (driver_id) REFERENCES Drivers(driver_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 10. RATINGS  (customer feedback after delivery)
-- ------------------------------------------------------------
CREATE TABLE Ratings (
    rating_id       INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL UNIQUE,
    customer_id     INT NOT NULL,
    restaurant_id   INT NOT NULL,
    rating_value    DECIMAL(3,2) NOT NULL CHECK (rating_value BETWEEN 1 AND 5),
    review_text     TEXT,
    rating_date     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id)      REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id)   REFERENCES Customers(customer_id),
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id)
) ENGINE=InnoDB;

-- ============================================================
-- TRIGGERS
-- Flow:  Order Delivered  --->  Increase Restaurant Rating
--
-- When a delivery's status flips to 'Delivered', we mark the
-- parent order Delivered and nudge the restaurant's live rating
-- up slightly (a quick "on-time delivery" signal). Once the
-- customer actually submits a star Rating, a second trigger
-- recomputes the restaurant's rating as the true average of
-- every rating it has ever received, overriding the bump.
--
-- MySQL has no "AFTER UPDATE OF <column>" clause (unlike SQLite/
-- Postgres), so the column-changed check is done with an IF
-- inside the trigger body instead.
-- ============================================================

DROP TRIGGER IF EXISTS trg_order_delivered_bump_rating;
DROP TRIGGER IF EXISTS trg_rating_recalc_restaurant_avg;

DELIMITER $$

CREATE TRIGGER trg_order_delivered_bump_rating
AFTER UPDATE ON Deliveries
FOR EACH ROW
BEGIN
    IF NEW.delivery_status = 'Delivered' AND OLD.delivery_status != 'Delivered' THEN
        -- 1) Mark the parent order as Delivered too
        UPDATE Orders
        SET status = 'Delivered'
        WHERE order_id = NEW.order_id;

        -- 2) Small positive nudge to the restaurant's live rating,
        --    capped at 5.0, rewarding a completed delivery
        UPDATE Restaurants
        SET rating = LEAST(5.0, ROUND(rating + 0.01, 2))
        WHERE restaurant_id = (
            SELECT restaurant_id FROM Orders WHERE order_id = NEW.order_id
        );
    END IF;
END$$

CREATE TRIGGER trg_rating_recalc_restaurant_avg
AFTER INSERT ON Ratings
FOR EACH ROW
BEGIN
    UPDATE Restaurants
    SET rating = ROUND((
        SELECT AVG(rating_value) FROM Ratings WHERE restaurant_id = NEW.restaurant_id
    ), 2)
    WHERE restaurant_id = NEW.restaurant_id;
END$$

DELIMITER ;

-- ============================================================
-- VIEWS
-- ============================================================

-- 1) TODAY'S ORDERS
DROP VIEW IF EXISTS vw_todays_orders;
CREATE VIEW vw_todays_orders AS
SELECT
    o.order_id,
    c.name          AS customer_name,
    r.name          AS restaurant_name,
    o.status,
    o.total_amount,
    o.order_date
FROM Orders o
JOIN Customers   c ON c.customer_id   = o.customer_id
JOIN Restaurants r ON r.restaurant_id = o.restaurant_id
WHERE DATE(o.order_date) = CURDATE()
ORDER BY o.order_date DESC;

-- 2) TOP RESTAURANTS (by rating, tie-broken by order volume)
DROP VIEW IF EXISTS vw_top_restaurants;
CREATE VIEW vw_top_restaurants AS
SELECT
    r.restaurant_id,
    r.name,
    r.cuisine,
    r.city,
    r.rating,
    COUNT(o.order_id)               AS total_orders,
    COALESCE(SUM(o.total_amount),0) AS total_revenue
FROM Restaurants r
LEFT JOIN Orders o ON o.restaurant_id = r.restaurant_id
GROUP BY r.restaurant_id, r.name, r.cuisine, r.city, r.rating
ORDER BY r.rating DESC, total_orders DESC;

-- 3) PENDING DELIVERIES
DROP VIEW IF EXISTS vw_pending_deliveries;
CREATE VIEW vw_pending_deliveries AS
SELECT
    d.delivery_id,
    o.order_id,
    c.name          AS customer_name,
    r.name          AS restaurant_name,
    dr.name         AS driver_name,
    d.delivery_status,
    d.pickup_time,
    o.order_date
FROM Deliveries d
JOIN Orders o        ON o.order_id       = d.order_id
JOIN Customers c      ON c.customer_id   = o.customer_id
JOIN Restaurants r    ON r.restaurant_id = o.restaurant_id
LEFT JOIN Drivers dr  ON dr.driver_id    = d.driver_id
WHERE d.delivery_status NOT IN ('Delivered','Cancelled')
ORDER BY o.order_date ASC;
