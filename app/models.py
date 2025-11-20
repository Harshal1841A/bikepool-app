from datetime import datetime, timedelta
from marshmallow import Schema, fields, validate
from .extensions import db

# --- Models ---
class User(db.Model):
    """User model for riders and passengers."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, default='test@example.com')
    password_hash = db.Column(db.String(120), nullable=False)

    is_rider = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    gender = db.Column(db.String(10), nullable=False)

    gender_preference = db.Column(db.String(10), default="Any")
    avatar_file = db.Column(db.String(20), nullable=False, default='default.png')
    bio = db.Column(db.Text, nullable=True)
    bookings = db.relationship('Booking', backref='passenger', lazy=True)

    sent_messages = db.relationship('Message', backref='sender', lazy=True)
    ratings_given = db.relationship('Rating', backref='passenger', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    posted_rides = db.relationship('BikeRide', backref='rider', foreign_keys='BikeRide.rider_id', lazy=True)

    def get_average_rating(self):
        if not self.is_rider:
            return None
        ride_ids = [ride.id for ride in self.posted_rides]
        if not ride_ids:
            return 0.0
        total_value = db.session.query(db.func.sum(Rating.rating_value)).filter(Rating.ride_id.in_(ride_ids)).scalar() or 0
        count = db.session.query(db.func.count(Rating.id)).filter(Rating.ride_id.in_(ride_ids)).scalar() or 0
        return round(total_value / count, 2) if count > 0 else 0.0

class BikeRide(db.Model):
    """Model representing a posted bike ride."""

    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    seats_available = db.Column(db.Integer, default=1, nullable=False)
    ride_date = db.Column(db.Date, nullable=False)
    ride_time = db.Column(db.Time, nullable=False)
    ride_end_time = db.Column(db.Time, nullable=True)
    rider_gender_preference = db.Column(db.String(10), default="Any")
    bookings = db.relationship('Booking', backref='ride', lazy=True, cascade="all, delete-orphan")
    messages = db.relationship('Message', backref='ride', lazy=True, cascade="all, delete-orphan")
    ratings = db.relationship('Rating', backref='ride', lazy=True, cascade="all, delete-orphan")
    # Version column to help optimistic updates
    version = db.Column(db.Integer, nullable=False, default=1)

class Booking(db.Model):
    """Model representing a seat booking on a ride."""

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('bike_ride.id'), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('ride_id', 'passenger_id', name='_ride_passenger_uc'),)

class Message(db.Model):
    """Model for chat messages within a ride."""

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('bike_ride.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Rating(db.Model):
    """Model for ratings given to riders by passengers."""

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('bike_ride.id'), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating_value = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('ride_id', 'passenger_id', name='_ride_passenger_rating_uc'),)

class Notification(db.Model):
    """Model for user notifications."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

# --- Utility Functions & Schemas ---
def get_ride_datetime(ride_date, ride_time, ride_end_time=None):
    """Combine date and time into datetime objects, handling overnight rides."""

    ride_dt_start = datetime.combine(ride_date, ride_time)
    end_time = ride_end_time if ride_end_time else ride_time
    ride_dt_end = datetime.combine(ride_date, end_time)
    if ride_time and ride_end_time and ride_dt_end <= ride_dt_start:
        ride_dt_end += timedelta(days=1)
    return ride_dt_start, ride_dt_end

class RideSchema(Schema):
    """Marshmallow schema for validating ride data."""

    source = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    destination = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    seats = fields.Int(required=True, validate=validate.Range(min=1))
    ride_date = fields.Date(required=True)
    ride_time = fields.Time(required=True)
    # CORRECTED: Changed 'missing' to 'load_default' for newer marshmallow versions
    ride_end_time = fields.Time(required=False, load_default=None)
    rider_gender_preference = fields.Str(required=False, load_default="Any", validate=validate.OneOf(["Male", "Female", "Any"]))
