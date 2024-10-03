import os
from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import timedelta
from flask_cors import CORS
from models import db, User, Product, Order, OrderItem, Category, ShippingAddress, Payment
import logging
from flask_restful import Api
from dotenv import load_dotenv
import random
from sqlalchemy import func

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "fsbdgfnhgvjnvhmvh" + str(random.randint(1, 1000000000000)))
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 1)))
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "JKSRVHJVFBSRDFV" + str(random.randint(1, 1000000000000)))
app.json.compact = False

# Initialize extensions
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)
db.init_app(app)

api = Api(app)

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO)

@app.before_request
def log_request_info():
    logging.info(f"Request: {request.method} {request.url}")

@app.after_request
def log_response_info(response):
    logging.info(f"Response: {response.status} {response.get_data()}")
    return response

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"message": "Internal server error"}), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"message": "Bad request"}), 400

# JWT Blacklist
BLACKLIST = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, decrypted_token):
    return decrypted_token['jti'] in BLACKLIST

# User management
@app.route("/login", methods=["POST"])
def login():
    email = request.json.get("email", None)
    password = request.json.get("password", None)

    user = User.query.filter_by(email=email).first()

    if user and bcrypt.check_password_hash(user.password, password):
        access_token = create_access_token(identity=user.id)
        return jsonify({"access_token": access_token})

    return jsonify({"message": "Invalid email or password"}), 401

@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    BLACKLIST.add(jti)
    return jsonify({"success": "Successfully logged out"}), 200

@app.route("/current_user", methods=["GET"])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if current_user:
        return jsonify({
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at
        })
    return jsonify({"message": "User not found"}), 404

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

    new_user = User(username=username, email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully", "user": new_user.id}), 201

@app.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    user = User.query.get(user_id)
    if user:
        return jsonify({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        })
    return jsonify({"message": "User not found"}), 404

@app.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'username' in data:
        user.username = data['username']
    if 'email' in data:
        user.email = data['email']
    if 'password' in data:
        user.password = bcrypt.generate_password_hash(data['password']).decode("utf-8")
        
    db.session.commit()
    return jsonify({'message': 'User updated successfully'})
@app.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "User deleted successfully"}), 200

# Product management
@app.route("/products", methods=["GET"])
def list_products():
    products = Product.query.all()
    products_data = [{'id': product.id, 'name': product.name, 'price': product.price, 'category': product.category.name} for product in products]
    return jsonify(products_data)
@app.route("/products", methods=["POST"])
@jwt_required()
def create_product():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")
    category_id = data.get("category_id")

    # Check if category exists
    category = Category.query.get(category_id)
    if not category:
        return jsonify({"message": "Invalid category ID"}), 400

    # Create new product
    new_product = Product(name=name, price=price, category_id=category_id)
    db.session.add(new_product)
    db.session.commit()

    return jsonify({"message": "Product created successfully", "product": new_product.id}), 201

# Order management
@app.route("/orders", methods=["POST"])
@jwt_required()
def create_order():
    data = request.get_json()
    user_id = get_jwt_identity()
    cart_items = data.get("cart_items")
    shipping_address_data = data.get("shipping_address")

    if not cart_items:
        return jsonify({"message": "Cart is empty"}), 400

    new_order = Order(user_id=user_id, total_price=0.0)
    db.session.add(new_order)

    total_price = 0
    for item in cart_items:
        product = Product.query.get(item['product_id'])
        if not product:
            return jsonify({"message": f"Product with ID {item['product_id']} not found"}), 400
        
        quantity = item.get('quantity', 1)
        price = product.price * quantity
        total_price += price

        order_item = OrderItem(order=new_order, product=product, quantity=quantity, price=price)
        db.session.add(order_item)

    # Set the total price
    new_order.total_price = total_price

    # Handle shipping address if provided
    if shipping_address_data:
        shipping_address = ShippingAddress(
            order=new_order,
            address_line_1=shipping_address_data.get("address_line_1"),
            address_line_2=shipping_address_data.get("address_line_2"),
            city=shipping_address_data.get("city"),
            postal_code=shipping_address_data.get("postal_code"),
            country=shipping_address_data.get("country")
        )
        db.session.add(shipping_address)

    db.session.commit()

    return jsonify({"message": "Order created successfully", "order": new_order.id}), 201

@app.route("/payments", methods=["POST"])
@jwt_required()
def make_payment():
    if not request.is_json:
        return jsonify({"message": "Request must be JSON"}), 400

    data = request.get_json()
    order_id = data.get("order_id")
    payment_method = data.get("payment_method")
    amount = data.get("amount")

    order = Order.query.get(order_id)
    if not order or order.is_paid:
        return jsonify({"message": "Invalid order ID or order already paid"}), 400

    payment = Payment(order_id=order_id, payment_method=payment_method, amount=amount)
    order.is_paid = True
    order.payment_date = func.now()
    
    db.session.add(payment)
    db.session.commit()

    return jsonify({"message": "Payment processed successfully", "payment": payment.id}), 201




@app.route('/')
def index():
    return '<h1>Flask is running!</h1>'

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5555, debug=True)