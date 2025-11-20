import os
import logging
from flask import Flask
from .extensions import db, socketio, csrf, limiter, admin, mail
from .routes import auth, main, rides, api

from .models import User, BikeRide, Booking, Rating, Notification
from .admin_views import AdminModelView, MyAdminIndexView
from . import events  # Register SocketIO events


def create_app(debug=False):
    app = Flask(__name__)

    # --- Config ---
    instance_dir = os.path.join(os.getcwd(), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Secret Key Handling
    app.secret_key = os.environ.get('SECRET_KEY')
    
    if not app.secret_key:
        secret_key_file = os.path.join(instance_dir, 'secret.key')
        if os.path.exists(secret_key_file):
            with open(secret_key_file, 'r') as key_file:
                app.secret_key = key_file.read().strip()
        else:
            import secrets
            app.secret_key = secrets.token_hex(32)
            with open(secret_key_file, 'w') as key_file:
                key_file.write(app.secret_key)
                
        try:
            os.chmod(secret_key_file, 0o600)
        except Exception:
            pass
    
    # Database Config
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(instance_dir, "bikepool.db")}')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/avatars')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Mail Configuration
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@bikepool.com')

    # --- Initialize Extensions ---
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    mail.init_app(app)
    
    # Initialize Admin with custom index view
    admin.init_app(app, index_view=MyAdminIndexView())
    
    # Register Admin Views
    admin.add_view(AdminModelView(User, db.session))
    admin.add_view(AdminModelView(BikeRide, db.session))
    admin.add_view(AdminModelView(Booking, db.session))
    admin.add_view(AdminModelView(Rating, db.session))
    admin.add_view(AdminModelView(Notification, db.session))

    # --- Register Blueprints ---

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(rides.bp)
    app.register_blueprint(api.bp)

    # --- Logging ---
    logging.basicConfig(level=logging.INFO)

    # Create tables
    with app.app_context():
        db.create_all()

    return app

