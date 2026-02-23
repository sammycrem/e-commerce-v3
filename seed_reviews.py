from app.app import create_app
from app.models import Product, Review, User
from app.extensions import db

app = create_app()
with app.app_context():
    # Create user if not exists
    u = User.query.filter_by(username='reviewer').first()
    if not u:
        u = User(username='reviewer', email='r@example.com', user_id='u1', password='pw', encrypted_password='pw')
        db.session.add(u)
        db.session.commit()

    p = Product.query.filter_by(product_sku='p-1').first()
    if p:
        # Check if review exists
        if not Review.query.filter_by(user_id=u.id, product_id=p.id).first():
            r = Review(user_id=u.id, product_id=p.id, rating=5, comment="Awesome!")
            db.session.add(r)
            db.session.commit()
            print("Review added to p-1")
        else:
            print("Review already exists")
