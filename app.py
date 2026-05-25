import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("請確保在環境變數中設定了 SECRET_KEY")

# 資料庫連線設定
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

# ==================== 資料庫初始化 ====================
def init_database():
    with app.app_context():
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
                Product(name="紅茶拿鐵", price=55, category_id=c2.id),
                Product(name="珍珠奶茶", price=50, category_id=c3.id),
            ])
            db.session.commit()

# 在程式啟動時執行一次初始化
init_database()

# ==================== ROUTING / CONTROLLERS ====================

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def front_pos():
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('index.html', categories=categories, products=products)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json() or {}
    items = data.get('items', [])
    if not items: return jsonify({"success": False}), 400
    
    order_num = f"WINE-{int(datetime.now().timestamp())}"
    total = sum(int(item['price']) * int(item['qty']) for item in items)
    
    new_order = Order(
        order_number=order_num, total_amount=total,
        payment_method=data.get('payment_method', '現金'),
        items=[OrderItem(product_name=i['name'], price=i['price'], quantity=i['qty'], sweetness=i['sweetness'], ice=i['ice']) for i in items]
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"success": True, "order_number": order_num})

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html', orders=Order.query.all())

@app.route('/admin/products')
def admin_products():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    return render_template('admin_products.html', categories=Category.query.all(), products=Product.query.all())

@app.route('/admin/products/add', methods=['POST'])
def add_product():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    db.session.add(Product(name=request.form['name'], price=int(request.form['price']), category_id=int(request.form['category_id'])))
    db.session.commit()
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    app.run(debug=True)