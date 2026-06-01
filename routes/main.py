import os
import uuid
import json
import re
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, session
from werkzeug.utils import secure_filename
from models.product import (
    get_all_products,
    get_products_by_category,
    get_product_by_id,
    add_product,
    set_product_image,
    delete_product,
    create_order,
    get_order_by_order_id,
    get_order_items_by_order_id,
    get_dashboard_stats,
    get_filtered_orders,
    update_order_status,
    get_filtered_products,
    update_product,
    get_all_categories,
    add_category,
    delete_category_by_id,
    toggle_product_active,
    duplicate_product,
    add_contact_message,
    get_all_contact_messages,
    delete_contact_message,
)
from routes.auth import login_required

main_bp = Blueprint("main", __name__)
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _get_categories_list():
    return [c["name"] for c in get_all_categories()]


def _allowed_image(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _require_csrf():
    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not form_token or not session_token or form_token != session_token:
        flash("Security check failed. Please try again.", "error")
        return False
    return True


def _validate_checkout_payload(form):
    """
    Returns (clean_dict, errors_dict)
    """
    errors = {}

    full_name = (form.get("full_name") or "").strip()
    phone = (form.get("phone") or "").strip()
    email = (form.get("email") or "").strip()
    address = (form.get("address") or "").strip()
    city = (form.get("city") or "").strip()
    state = (form.get("state") or "").strip()
    pincode = (form.get("pincode") or "").strip()
    payment_method = (form.get("payment_method") or "").strip()

    if not full_name:
        errors["full_name"] = "Full name is required."
    elif not re.fullmatch(r"[A-Za-z ]+", full_name):
        errors["full_name"] = "Only alphabets and spaces are allowed."

    if not re.fullmatch(r"\d{10}", phone or ""):
        errors["phone"] = "Phone number must be exactly 10 digits."

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
        errors["email"] = "Please enter a valid email address."

    if not address:
        errors["address"] = "Address is required."
    elif len(address) < 10:
        errors["address"] = "Address must be at least 10 characters."

    if not city:
        errors["city"] = "City is required."
    if not state:
        errors["state"] = "State is required."

    if not re.fullmatch(r"\d{6}", pincode or ""):
        errors["pincode"] = "Pincode must be exactly 6 digits."

    if payment_method not in {"upi", "card", "cod"}:
        errors["payment_method"] = "Please select a payment method."

    payment_meta = {}
    if payment_method == "upi":
        upi_id = (form.get("upi_id") or "").strip()
        if not upi_id:
            errors["upi_id"] = "Please enter your UPI ID."
        else:
            payment_meta["upi_id"] = upi_id
    elif payment_method == "card":
        card_name = (form.get("card_name") or "").strip()
        card_number = re.sub(r"\s+", "", (form.get("card_number") or "").strip())
        card_expiry = (form.get("card_expiry") or "").strip()
        card_cvv = (form.get("card_cvv") or "").strip()

        if not card_name:
            errors["card_name"] = "Name on card is required."
        if not re.fullmatch(r"\d{12,19}", card_number or ""):
            errors["card_number"] = "Please enter a valid card number."
        if not re.fullmatch(r"(0[1-9]|1[0-2])\/\d{2}", card_expiry or ""):
            errors["card_expiry"] = "Expiry must be in MM/YY format."
        if not re.fullmatch(r"\d{3,4}", card_cvv or ""):
            errors["card_cvv"] = "Please enter a valid CVV."

        if "card_number" not in errors:
            payment_meta["card_last4"] = card_number[-4:]

    clean = {
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "address": address,
        "city": city,
        "state": state,
        "pincode": pincode,
        "payment_method": payment_method,
        "payment_meta": payment_meta,
    }
    return clean, errors


def _build_home_context():
    products = get_filtered_products(active_only=True)
    hero_image = next((p["image"] for p in products if p["image"]), None)
    promo_image = next((p["image"] for p in products if p["image"] and p["image"] != hero_image), None)
    static_dir = os.path.join(current_app.root_path, "static", "images")

    hero_static = None
    promo_static = None
    if os.path.isdir(static_dir):
        # Prefer the most recently updated home-hero.* / home-promo.* files.
        hero_candidates = [
            f for f in os.listdir(static_dir)
            if f.startswith("home-hero.") and os.path.isfile(os.path.join(static_dir, f))
        ]
        promo_candidates = [
            f for f in os.listdir(static_dir)
            if f.startswith("home-promo.") and os.path.isfile(os.path.join(static_dir, f))
        ]
        if hero_candidates:
            hero_latest = max(hero_candidates, key=lambda f: os.path.getmtime(os.path.join(static_dir, f)))
            hero_static = f"images/{hero_latest}"
        if promo_candidates:
            promo_latest = max(promo_candidates, key=lambda f: os.path.getmtime(os.path.join(static_dir, f)))
            promo_static = f"images/{promo_latest}"

    return {
        "products": products,
        "categories": _get_categories_list(),
        "hero_image": hero_image,
        "promo_image": promo_image,
        "hero_static": hero_static,
        "promo_static": promo_static,
    }


@main_bp.route("/")
def index():
    # Public homepage (no login required).
    ctx = _build_home_context()
    return render_template(
        "home.html",
        **ctx,
    )


@main_bp.route("/products")
def products():
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "").strip()
    
    categories_list = _get_categories_list()
    selected_category = category if category in categories_list else None
    
    items = get_filtered_products(category=selected_category, search=search, sort_by=sort_by, active_only=True)
    return render_template(
        "products.html",
        products=items,
        selected_category=selected_category,
        categories=categories_list,
        search_query=search,
        sort_by=sort_by
    )


@main_bp.route("/categories")
def categories():
    db_categories = get_all_categories()
    categories_list = []
    for cat in db_categories:
        c = dict(cat)
        products_in_cat = get_products_by_category(c["name"])
        c["product_count"] = len([p for p in products_in_cat if p["is_active"]])
        if not c.get("image"):
            first_active_prod_img = next((p["image"] for p in products_in_cat if p["image"] and p["is_active"]), None)
            c["fallback_image"] = first_active_prod_img
        categories_list.append(c)
    return render_template("categories.html", categories=categories_list)


@main_bp.route("/categories/<category_name>")
def category_products(category_name):
    categories_list = _get_categories_list()
    if category_name not in categories_list:
        flash("Category not found.", "error")
        return redirect(url_for("main.categories"))
    return redirect(url_for("main.products", category=category_name))


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        
        if not name or not email or not message:
            flash("Name, Email, and Message are required.", "error")
            return render_template("contact.html", form_data=request.form)
            
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Please enter a valid email address.", "error")
            return render_template("contact.html", form_data=request.form)
            
        add_contact_message(name, email, phone or None, subject or None, message)
        flash("Thank you! Your message has been received.", "success")
        return redirect(url_for("main.contact"))
        
    return render_template("contact.html", form_data={})


@main_bp.route("/dashboard")
@login_required
def dashboard():
    status_filter = request.args.get("status", "all").strip()
    search_query = request.args.get("q", "").strip()
    
    stats = get_dashboard_stats()
    raw_orders = get_filtered_orders(status=status_filter, search=search_query)
    
    orders = []
    for order in raw_orders:
        o = dict(order)
        o["items"] = get_order_items_by_order_id(order["order_id"])
        orders.append(o)
    
    messages = get_all_contact_messages()
    
    return render_template(
        "dashboard.html",
        stats=stats,
        orders=orders,
        status_filter=status_filter,
        search_query=search_query,
        messages=messages,
        csrf_token=_get_csrf_token()
    )


@main_bp.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def admin_delete_message(message_id):
    if not _require_csrf():
        return redirect(url_for("main.dashboard"))
    delete_contact_message(message_id)
    flash("Message deleted successfully.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/admin/orders/<order_id>/status", methods=["POST"])
@login_required
def admin_update_order_status(order_id):
    if not _require_csrf():
        return redirect(url_for("main.dashboard"))
        
    new_status = request.form.get("status", "").strip()
    if new_status not in {"placed", "processing", "shipped", "completed", "cancelled"}:
        flash("Invalid order status.", "error")
        return redirect(url_for("main.dashboard"))
        
    update_order_status(order_id, new_status)
    flash(f"Order status for {order_id} updated to {new_status.capitalize()}.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        if not _require_csrf():
            return redirect(url_for("main.add"))
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        raw_price = request.form.get("price", "").strip()
        raw_stock = request.form.get("stock", "0").strip()
        category = request.form.get("category", "").strip()
        is_active = 1 if request.form.get("is_active") else 0

        if not name:
            flash("Product name is required.", "error")
            return redirect(url_for("main.add"))

        try:
            price = float(raw_price)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid non-negative price.", "error")
            return redirect(url_for("main.add"))
            
        try:
            stock = int(raw_stock)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid non-negative stock quantity.", "error")
            return redirect(url_for("main.add"))

        image = request.files.get("image")
        image_filename = None
        if image and image.filename:
            if not _allowed_image(image.filename):
                flash("Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.", "error")
                return redirect(url_for("main.add"))

            original_name = secure_filename(image.filename)
            ext = original_name.rsplit(".", 1)[1].lower()
            image_filename = f"{uuid.uuid4().hex}.{ext}"

            upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
            os.makedirs(upload_dir, exist_ok=True)
            upload_path = os.path.join(upload_dir, image_filename)
            image.save(upload_path)

        categories_list = _get_categories_list()
        if category and category not in categories_list:
            flash("Please select a valid category.", "error")
            return redirect(url_for("main.add"))

        add_product(name, price, image_filename, category, description, stock, is_active)
        flash("Product added successfully.", "success")
        return redirect(url_for("main.admin_products"))
    return render_template("add_product.html", categories=_get_categories_list(), csrf_token=_get_csrf_token())


def _get_cart():
    """
    Cart is stored in session as:
      session['cart'] = { "<product_id>": { "quantity": <int> } }
    """
    cart = session.get("cart")
    if not isinstance(cart, dict):
        return {}
    return cart


def _set_cart(cart):
    session["cart"] = cart


@main_bp.route("/cart", methods=["GET"])
def cart():
    cart = _get_cart()
    product_map = {str(p["id"]): p for p in get_all_products()}

    items = []
    total = 0.0
    for product_id, item in cart.items():
        product = product_map.get(product_id)
        if not product:
            continue
        qty = int(item.get("quantity", 0) or 0)
        if qty <= 0:
            continue
        line_total = float(product["price"]) * qty
        total += line_total
        items.append(
            {
                "product": product,
                "quantity": qty,
                "line_total": line_total,
            }
        )

    return render_template("cart.html", items=items, total=total)


@main_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.products"))

    cart = _get_cart()
    pid = str(product_id)
    current_qty = int(cart.get(pid, {}).get("quantity", 0) or 0)
    cart[pid] = {"quantity": current_qty + 1}
    _set_cart(cart)

    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("main.products"))


@main_bp.route("/buy/<int:product_id>", methods=["POST"])
def buy_now(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.products"))

    # Buy now = replace cart with a single item.
    _set_cart({str(product_id): {"quantity": 1}})
    flash("Ready to buy now.", "success")
    return redirect(url_for("main.checkout"))


@main_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = _get_cart()
    product_map = {str(p["id"]): p for p in get_all_products()}

    items = []
    total = 0.0
    for product_id, item in cart.items():
        product = product_map.get(product_id)
        if not product:
            continue
        qty = int(item.get("quantity", 0) or 0)
        if qty <= 0:
            continue
        line_total = float(product["price"]) * qty
        total += line_total
        items.append({"product": product, "quantity": qty, "line_total": line_total})

    if request.method == "GET":
        return render_template(
            "checkout.html",
            items=items,
            total=total,
            form_data={},
            errors={},
            csrf_token=_get_csrf_token(),
            upi_qr_static="images/upi-qr.png",
            upi_default_id="wrapnbloom@upi",
        )

    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("main.cart"))

    if not _require_csrf():
        return redirect(url_for("main.checkout"))

    clean, errors = _validate_checkout_payload(request.form)
    if errors:
        return render_template(
            "checkout.html",
            items=items,
            total=total,
            form_data=clean,
            errors=errors,
            csrf_token=_get_csrf_token(),
            upi_qr_static="images/upi-qr.png",
            upi_default_id="wrapnbloom@upi",
        )

    order_id = f"WB-{uuid.uuid4().hex[:10].upper()}"
    order_items = []
    for it in items:
        p = it["product"]
        order_items.append(
            {
                "product_id": int(p["id"]),
                "name": p["name"],
                "price": float(p["price"]),
                "quantity": int(it["quantity"]),
                "image": p["image"],
            }
        )

    create_order(
        {
            "order_id": order_id,
            "full_name": clean["full_name"],
            "phone": clean["phone"],
            "email": clean["email"],
            "address": clean["address"],
            "city": clean["city"],
            "state": clean["state"],
            "pincode": clean["pincode"],
            "payment_method": clean["payment_method"],
            "payment_meta": json.dumps(clean["payment_meta"]) if clean["payment_meta"] else None,
            "total_amount": float(total),
            "status": "placed",
        },
        order_items,
    )

    _set_cart({})
    flash("Order placed successfully.", "success")
    return redirect(url_for("main.order_confirmation", order_id=order_id))


@main_bp.route("/order/<order_id>", methods=["GET"])
def order_confirmation(order_id):
    order = get_order_by_order_id(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("main.products"))
    items = get_order_items_by_order_id(order_id)
    return render_template("order_confirmation.html", order=order, items=items)


@main_bp.route("/admin/products", methods=["GET"])
@login_required
def admin_products():
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "").strip()
    
    categories_list = _get_categories_list()
    selected_category = category if category in categories_list else None
    
    products = get_filtered_products(category=selected_category, search=search, sort_by=sort_by)
    return render_template(
        "manage_products.html",
        products=products,
        categories=categories_list,
        selected_category=selected_category,
        search_query=search,
        sort_by=sort_by,
        csrf_token=_get_csrf_token()
    )


@main_bp.route("/admin/products/<int:product_id>/delete-image", methods=["POST"])
@login_required
def admin_delete_product_image(product_id):
    if not _require_csrf():
        return redirect(url_for("main.admin_products"))

    product = get_product_by_id(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.admin_products"))

    filename = product["image"]
    if not filename:
        flash("No image to delete for this product.", "error")
        return redirect(url_for("main.admin_products"))

    upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
    target_path = os.path.join(upload_dir, filename)

    # Remove file from disk (best-effort), then clear DB reference.
    try:
        if os.path.isfile(target_path):
            os.remove(target_path)
    except OSError:
        pass

    set_product_image(product_id, None)
    flash("Product image deleted successfully.", "success")
    return redirect(url_for("main.admin_products"))


@main_bp.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def admin_delete_product(product_id):
    if not _require_csrf():
        return redirect(url_for("main.admin_products"))

    product = get_product_by_id(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.admin_products"))

    filename = product["image"]
    if filename:
        upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
        target_path = os.path.join(upload_dir, filename)
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
        except OSError:
            pass

    delete_product(product_id)
    flash("Product deleted successfully.", "success")
    return redirect(url_for("main.admin_products"))


@main_bp.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_product(product_id):
    if not _require_csrf():
        return redirect(url_for("main.admin_products"))
    toggle_product_active(product_id)
    flash("Product visibility toggled.", "success")
    return redirect(url_for("main.admin_products"))


@main_bp.route("/admin/products/<int:product_id>/duplicate", methods=["POST"])
@login_required
def admin_duplicate_product(product_id):
    if not _require_csrf():
        return redirect(url_for("main.admin_products"))
    duplicate_product(product_id)
    flash("Product duplicated successfully (set to inactive).", "success")
    return redirect(url_for("main.admin_products"))


@main_bp.route("/home-images", methods=["GET", "POST"])
@login_required
def home_images():
    """
    Admin page to upload images for the home hero/promo frames.
    Saves files as static/images/home-hero.<ext> and static/images/home-promo.<ext>.
    """
    static_dir = os.path.join(current_app.root_path, "static", "images")
    os.makedirs(static_dir, exist_ok=True)

    if request.method == "POST":
        hero_file = request.files.get("hero_image")
        promo_file = request.files.get("promo_image")

        def _save_one(upload, target_prefix):
            if not upload or not upload.filename:
                return None
            if not _allowed_image(upload.filename):
                raise ValueError("Invalid image type.")
            original_name = secure_filename(upload.filename)
            ext = original_name.rsplit(".", 1)[1].lower()

            # Delete existing variants (home-hero.* / home-promo.*)
            for f in os.listdir(static_dir):
                if f.startswith(target_prefix + "."):
                    try:
                        os.remove(os.path.join(static_dir, f))
                    except OSError:
                        pass

            dest_filename = f"{target_prefix}.{ext}"
            dest_path = os.path.join(static_dir, dest_filename)
            upload.save(dest_path)
            return dest_filename

        try:
            if hero_file:
                _save_one(hero_file, "home-hero")
            if promo_file:
                _save_one(promo_file, "home-promo")
        except ValueError:
            flash("Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.", "error")
            return redirect(url_for("main.home_images"))

        flash("Home images updated successfully.", "success")
        return redirect(url_for("main.dashboard"))

    # For display on the page (optional): show whether images exist.
    hero_exists = any(
        f.startswith("home-hero.") for f in os.listdir(static_dir)
    )
    promo_exists = any(
        f.startswith("home-promo.") for f in os.listdir(static_dir)
    )
    return render_template("home_images.html", hero_exists=hero_exists, promo_exists=promo_exists)


@main_bp.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_product(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.admin_products"))
        
    categories_list = _get_categories_list()
    
    if request.method == "POST":
        if not _require_csrf():
            return redirect(url_for("main.admin_edit_product", product_id=product_id))
            
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        raw_price = request.form.get("price", "").strip()
        raw_stock = request.form.get("stock", "0").strip()
        category = request.form.get("category", "").strip()
        is_active = 1 if request.form.get("is_active") else 0
        
        if not name:
            flash("Product name is required.", "error")
            return redirect(url_for("main.admin_edit_product", product_id=product_id))
            
        try:
            price = float(raw_price)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid non-negative price.", "error")
            return redirect(url_for("main.admin_edit_product", product_id=product_id))
            
        try:
            stock = int(raw_stock)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid non-negative stock quantity.", "error")
            return redirect(url_for("main.admin_edit_product", product_id=product_id))
            
        if category and category not in categories_list:
            flash("Please select a valid category.", "error")
            return redirect(url_for("main.admin_edit_product", product_id=product_id))
            
        image = request.files.get("image")
        image_filename = product["image"]
        
        if image and image.filename:
            if not _allowed_image(image.filename):
                flash("Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.", "error")
                return redirect(url_for("main.admin_edit_product", product_id=product_id))
                
            if product["image"]:
                upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
                old_path = os.path.join(upload_dir, product["image"])
                try:
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except OSError:
                    pass
            
            original_name = secure_filename(image.filename)
            ext = original_name.rsplit(".", 1)[1].lower()
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            
            upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
            os.makedirs(upload_dir, exist_ok=True)
            upload_path = os.path.join(upload_dir, image_filename)
            image.save(upload_path)
            
        update_product(product_id, name, price, image_filename, category, description, stock, is_active)
        flash("Product updated successfully.", "success")
        return redirect(url_for("main.admin_products"))
        
    return render_template("edit_product.html", product=product, categories=categories_list, csrf_token=_get_csrf_token())


@main_bp.route("/admin/categories", methods=["GET", "POST"])
@login_required
def admin_categories():
    if request.method == "POST":
        if not _require_csrf():
            return redirect(url_for("main.admin_categories"))
            
        action = request.form.get("action", "").strip()
        if action == "add":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Category name is required.", "error")
                return redirect(url_for("main.admin_categories"))
                
            image = request.files.get("image")
            image_filename = None
            if image and image.filename:
                if not _allowed_image(image.filename):
                    flash("Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.", "error")
                    return redirect(url_for("main.admin_categories"))
                    
                original_name = secure_filename(image.filename)
                ext = original_name.rsplit(".", 1)[1].lower()
                image_filename = f"{uuid.uuid4().hex}.{ext}"
                
                upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
                os.makedirs(upload_dir, exist_ok=True)
                upload_path = os.path.join(upload_dir, image_filename)
                image.save(upload_path)
                
            if add_category(name, image_filename):
                flash(f"Category '{name}' added successfully.", "success")
            else:
                flash(f"Category '{name}' already exists or is invalid.", "error")
        elif action == "delete":
            cat_id_str = request.form.get("category_id", "").strip()
            try:
                cat_id = int(cat_id_str)
                delete_category_by_id(cat_id)
                flash("Category deleted successfully.", "success")
            except ValueError:
                flash("Invalid category ID.", "error")
                
        return redirect(url_for("main.admin_categories"))
        
    categories = get_all_categories()
    return render_template("admin_categories.html", categories=categories, csrf_token=_get_csrf_token())


@main_bp.route("/admin/orders/<order_id>", methods=["GET"])
@login_required
def admin_order_detail(order_id):
    order = get_order_by_order_id(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("main.dashboard"))
    items = get_order_items_by_order_id(order_id)
    return render_template("admin_order_detail.html", order=order, items=items, csrf_token=_get_csrf_token())
