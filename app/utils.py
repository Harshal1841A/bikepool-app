from functools import wraps
from datetime import datetime, timedelta
from flask import session, flash, redirect, url_for, current_app
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError
import logging
import secrets
import os
from PIL import Image
from threading import Thread
from flask_mail import Message

from .extensions import db, socketio, mail
from .models import Notification

logger = logging.getLogger(__name__)

# Precompute a dummy hash to mitigate timing attacks
_DUMMY_PASSWORD_HASH = generate_password_hash("non-existent-user-password")

def get_ride_datetime(ride_date, ride_time, ride_end_time=None):
    """Combine date and time into datetime objects, handling overnight rides."""
    ride_dt_start = datetime.combine(ride_date, ride_time)
    end_time = ride_end_time if ride_end_time else ride_time
    ride_dt_end = datetime.combine(ride_date, end_time)
    if ride_time and ride_end_time and ride_dt_end <= ride_dt_start:
        ride_dt_end += timedelta(days=1)
    return ride_dt_start, ride_dt_end

def requires_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def create_notification(user_id, message):
    """
    Persist notification, commit, and then emit. Returns True/False.
    """
    try:
        notification = Notification(user_id=user_id, message=message, timestamp=datetime.utcnow())
        db.session.add(notification)
        db.session.commit()  # ensure id and timestamp are set
        # emit after commit so clients can use notification.id
        socketio.emit('new_notification', {
            'message': message,
            'timestamp': notification.timestamp.strftime('%H:%M'),
            'notification_id': notification.id,
        }, room=f'user_{user_id}')
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to create notification for user %s: %s", user_id, e)
        return False

def save_picture(form_picture):
    """Save uploaded profile picture with a random name."""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], picture_fn)

    # Resize image
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            logger.info(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            logger.warning(f"Failed to send email to {msg.recipients}: {e}")
            logger.warning("Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD to enable emails.")

def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@bikepool.com')
    )
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
