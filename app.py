from flask import Flask, session
from routes.main import main_bp
from routes.auth import auth_bp
from models.product import init_db

app = Flask(__name__)
app.config.from_object("config")

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)

# Create tables on first run
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)


@app.context_processor
def cart_context():
    cart = session.get("cart")
    if not isinstance(cart, dict):
        return {"cart_count": 0}
    count = 0
    for item in cart.values():
        qty = 0
        if isinstance(item, dict):
            qty = int(item.get("quantity", 0) or 0)
        count += max(0, qty)
    return {"cart_count": count}
