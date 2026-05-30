import sqlite3
import os
from config import DATABASE


def get_db():
    """Open a connection to the SQLite database."""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """Create tables if they don't exist yet."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            price       REAL    NOT NULL,
            image       TEXT,
            category    TEXT,
            description TEXT,
            stock       INTEGER NOT NULL DEFAULT 0,
            is_active   INTEGER NOT NULL DEFAULT 1
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      TEXT    NOT NULL UNIQUE,
            full_name     TEXT    NOT NULL,
            phone         TEXT    NOT NULL,
            email         TEXT    NOT NULL,
            address       TEXT    NOT NULL,
            city          TEXT    NOT NULL,
            state         TEXT    NOT NULL,
            pincode       TEXT    NOT NULL,
            payment_method TEXT   NOT NULL,
            payment_meta  TEXT,
            total_amount  REAL    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'placed',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   TEXT    NOT NULL,
            product_id INTEGER,
            name       TEXT    NOT NULL,
            price      REAL    NOT NULL,
            quantity   INTEGER NOT NULL,
            image      TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
    """)

    # Auto-migrate older DBs created before image/category/etc fields existed.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(products)").fetchall()}
    if "image" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN image TEXT")
    if "category" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN category TEXT")
    if "description" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN description TEXT")
    if "stock" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 0")
    if "is_active" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    NOT NULL UNIQUE
        )
    """)

    # Seed default categories if table is empty
    count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count == 0:
        default_categories = [
            "Bridal Bouquet",
            "Graduation Bouquet",
            "Chocolate Bouquet",
            "Rose Bouquet",
            "Artificial Bouquet",
        ]
        for name in default_categories:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))

    db.commit()
    db.close()


def get_all_products():
    db = get_db()
    products = db.execute("SELECT * FROM products").fetchall()
    db.close()
    return products


def get_products_by_category(category):
    db = get_db()
    products = db.execute(
        "SELECT * FROM products WHERE category = ? ORDER BY id DESC",
        (category,),
    ).fetchall()
    db.close()
    return products


def get_product_by_id(product_id):
    db = get_db()
    product = db.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    db.close()
    return product


def add_product(name, price, image=None, category=None, description=None, stock=0, is_active=1):
    db = get_db()
    db.execute("INSERT INTO products (name, price, image, category, description, stock, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)", 
               (name, price, image, category, description, stock, is_active))
    db.commit()
    db.close()


def set_product_image(product_id, image_filename):
    db = get_db()
    db.execute("UPDATE products SET image = ? WHERE id = ?", (image_filename, product_id))
    db.commit()
    db.close()


def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    db.close()


def get_order_by_order_id(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    db.close()
    return order


def get_order_items_by_order_id(order_id):
    db = get_db()
    items = db.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    ).fetchall()
    db.close()
    return items


def create_order(order, items):
    """
    order: dict with order fields (order_id, customer fields, payment fields, total_amount, status)
    items: list of dicts with (product_id, name, price, quantity, image)
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO orders
        (order_id, full_name, phone, email, address, city, state, pincode, payment_method, payment_meta, total_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order["order_id"],
            order["full_name"],
            order["phone"],
            order["email"],
            order["address"],
            order["city"],
            order["state"],
            order["pincode"],
            order["payment_method"],
            order.get("payment_meta"),
            order["total_amount"],
            order.get("status", "placed"),
        ),
    )
    for it in items:
        db.execute(
            """
            INSERT INTO order_items (order_id, product_id, name, price, quantity, image)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order["order_id"],
                it.get("product_id"),
                it["name"],
                it["price"],
                it["quantity"],
                it.get("image"),
            ),
        )
    db.commit()
    db.close()


def get_dashboard_stats():
    db = get_db()
    # Total revenue from orders that are NOT cancelled
    total_sales = db.execute("SELECT SUM(total_amount) FROM orders WHERE status != 'cancelled'").fetchone()[0] or 0.0
    total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] or 0
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0] or 0
    total_categories = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] or 0
    
    # Orders status count
    status_counts = db.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status").fetchall()
    status_dict = {row["status"]: row["count"] for row in status_counts}
    
    db.close()
    return {
        "total_sales": total_sales,
        "total_orders": total_orders,
        "total_products": total_products,
        "total_categories": total_categories,
        "status_counts": status_dict
    }


def get_filtered_orders(status=None, search=None):
    db = get_db()
    query = "SELECT * FROM orders"
    params = []
    conditions = []
    
    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)
        
    if search:
        search_like = f"%{search}%"
        conditions.append("(order_id LIKE ? OR full_name LIKE ? OR phone LIKE ? OR email LIKE ?)")
        params.extend([search_like, search_like, search_like, search_like])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY created_at DESC"
    
    orders = db.execute(query, params).fetchall()
    db.close()
    return orders


def update_order_status(order_id, status):
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    db.commit()
    db.close()


def get_filtered_products(category=None, search=None, sort_by=None, active_only=False):
    db = get_db()
    query = "SELECT * FROM products"
    params = []
    conditions = []
    
    if active_only:
        conditions.append("is_active = 1")
    
    if category and category != "all":
        conditions.append("category = ?")
        params.append(category)
        
    if search:
        search_like = f"%{search}%"
        conditions.append("name LIKE ?")
        params.append(search_like)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    if sort_by == "price_asc":
        query += " ORDER BY price ASC"
    elif sort_by == "price_desc":
        query += " ORDER BY price DESC"
    elif sort_by == "name_asc":
        query += " ORDER BY name ASC"
    elif sort_by == "stock_asc":
        query += " ORDER BY stock ASC"
    else:
        query += " ORDER BY id DESC"
        
    products = db.execute(query, params).fetchall()
    db.close()
    return products


def update_product(product_id, name, price, image=None, category=None, description=None, stock=0, is_active=1):
    db = get_db()
    db.execute(
        "UPDATE products SET name = ?, price = ?, image = ?, category = ?, description = ?, stock = ?, is_active = ? WHERE id = ?",
        (name, price, image, category, description, stock, is_active, product_id)
    )
    db.commit()
    db.close()

def toggle_product_active(product_id):
    db = get_db()
    product = db.execute("SELECT is_active FROM products WHERE id = ?", (product_id,)).fetchone()
    if product:
        new_status = 0 if product["is_active"] else 1
        db.execute("UPDATE products SET is_active = ? WHERE id = ?", (new_status, product_id))
        db.commit()
    db.close()

def duplicate_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product:
        new_name = product["name"] + " (Copy)"
        db.execute(
            "INSERT INTO products (name, price, image, category, description, stock, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_name, product["price"], product["image"], product["category"], product["description"], product["stock"], 0)
        )
        db.commit()
    db.close()


def get_all_categories():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()
    db.close()
    return categories


def add_category(name):
    db = get_db()
    success = False
    try:
        db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        db.commit()
        success = True
    except sqlite3.IntegrityError:
        pass
    db.close()
    return success


def delete_category_by_id(category_id):
    db = get_db()
    cat = db.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
    if cat:
        name = cat["name"]
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        # Set products with this category to NULL
        db.execute("UPDATE products SET category = NULL WHERE category = ?", (name,))
        db.commit()
    db.close()


def update_category(category_id, new_name):
    db = get_db()
    cat = db.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
    success = False
    if cat:
        old_name = cat["name"]
        try:
            db.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id))
            # Also update products
            db.execute("UPDATE products SET category = ? WHERE category = ?", (new_name, old_name))
            db.commit()
            success = True
        except sqlite3.IntegrityError:
            pass
    db.close()
    return success
