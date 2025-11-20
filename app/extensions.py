from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_admin import Admin
from flask_mail import Mail

db = SQLAlchemy()
socketio = SocketIO(manage_session=False)
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
admin = Admin(name='BikePool Admin')
mail = Mail()


