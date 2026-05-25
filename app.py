import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pos_secret_key_123")

# 資料庫連線設定 (Neon PostgreSQL / 本地 SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///pos.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATA MODELS ====================
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    products = db.relationship('Product', backref='category', lazy=True, cascade="all, delete-orphan")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    is_available = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    total_amount = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(20), default="現金")
    status = db.Column(db.String(20), default="製作中")
    created_at = db.Column(db.DateTime, default=datetime.now)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sweetness = db.Column(db.String(20), nullable=False)
    ice = db.Column(db.String(20), nullable=False)

@app.before_all_requests
def init_db():
    db.create_all()
    if not Category.query.first():
        c1 = Category(name="經典純茶")
        c2 = Category(name="鮮奶拿鐵")
        c3 = Category(name="調風味茶")
        db.session.add_all([c1, c2, c3])
        db.session.commit()
        
        db.session.add_all([
            Product(name="茉莉綠茶", price=30, category_id=c1.id),
            Product(name="阿薩姆紅茶", price=30, category_id=c1.id),
            Product(name="四季春青茶", price=30, category_id=c1.id),
            Product(name="紅茶拿鐵", price=55, category_id=c2.id),
            Product(name="綠茶拿鐵", price=55, category_id=c2.id),
            Product(name="珍珠奶茶", price=50, category_id=c3.id),
        ])
        db.session.commit()

# ==================== ROUTING / CONTROLLERS ====================

@app.route('/')
def front_pos():
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('index.html', categories=categories, products=products)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json() or {}
    items = data.get('items', [])
    if not items:
        return jsonify({"success": False, "message": "訂單無有效內容"}), 400
    
    order_num = f"WINE-{int(datetime.now().timestamp())}"
    total_amount = 0
    order_items_to_add = []
    
    for item in items:
        total_amount += int(item['price']) * int(item['qty'])
        order_items_to_add.append(OrderItem(
            product_name=item['name'], price=item['price'], quantity=item['qty'],
            sweetness=item['sweetness'], ice=item['ice']
        ))
        
    new_order = Order(
        order_number=order_num, total_amount=total_amount,
        payment_method=data.get('payment_method', '現金'), items=order_items_to_add
    )
    
    try:
        db.session.add(new_order)
        db.session.commit()
        return jsonify({"success": True, "order_number": order_num})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

def is_admin_logged_in():
    return session.get('logged_in') is True

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        error = "帳號或密碼錯誤！"
    return render_template('login.html', error=error)

@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('front_pos'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    orders = Order.query.all()
    return render_template('admin_dashboard.html', orders=orders)

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    order = Order.query.get_or_400(order_id)
    order.status = request.form.get('status', '製作中')
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/products')
def admin_products():
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('admin_products.html', categories=categories, products=products)

@app.route('/admin/products/add', methods=['POST'])
def add_product():
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    name = request.form.get('name')
    price = request.form.get('price')
    category_id = request.form.get('category_id')
    if name and price and category_id:
        db.session.add(Product(name=name, price=int(price), category_id=int(category_id)))
        db.session.commit()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/toggle/<int:product_id>')
def toggle_product(product_id):
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    prod = Product.query.get_or_400(product_id)
    prod.is_available = not prod.is_available
    db.session.commit()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete/<int:product_id>')
def delete_product(product_id):
    if not is_admin_logged_in(): return redirect(url_for('admin_login'))
    prod = Product.query.get_or_400(product_id)
    db.session.delete(prod)
    db.session.commit()
    return redirect(url_for('admin_products'))

# 確保這部分在 app.py 的最下方
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()

# Vercel 實際上會從這裡抓取 app 實例，確保你的變數名稱是 app
app = Flask(__name__)