from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify
from sqlalchemy.orm import joinedload
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import User, BikeRide, Booking, Notification, Rating
from ..forms import DeleteRideForm, UpdateProfileForm
from ..utils import requires_auth, get_ride_datetime, save_picture


bp = Blueprint('main', __name__)

@bp.route('/')
def home():
    """Render the home page."""
    return render_template('optimized/home.html')

@bp.route('/dashboard')
@requires_auth
def dashboard():
    """Render the user dashboard (rider or passenger view)."""
    user_id = session['user_id']
    user = User.query.get(user_id)

    if user is None:
        flash("Your session is invalid. Please log in again.", 'error')
        session.clear()
        return redirect(url_for('auth.login'))

    unread_notifications_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    if session['is_rider']:
        rides = BikeRide.query.options(
            joinedload(BikeRide.bookings).joinedload(Booking.passenger)
        ).filter_by(rider_id=user_id).order_by(BikeRide.ride_date, BikeRide.ride_time).all()

        rider_rides_data = []
        now = datetime.now()
        for ride in rides:
            _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
            is_future_ride = ride_dt_end >= now
            is_completed = ride_dt_end < now
            passengers = [booking.passenger.username for booking in ride.bookings if booking.passenger]

            rider_rides_data.append({
                'ride': ride, 'passengers': passengers,
                'is_future_ride': is_future_ride, 'is_completed': is_completed
            })

        avg_rating = user.get_average_rating()
        return render_template('optimized/rider_dashboard.html',
                               rides_data=rider_rides_data,
                               avg_rating=avg_rating,
                               unread_notifications_count=unread_notifications_count,
                               delete_form=DeleteRideForm())
    
    # Passenger View
    all_rides = BikeRide.query.options(joinedload(BikeRide.rider)).filter(
            BikeRide.rider_id != user_id
        ).order_by(BikeRide.ride_date, BikeRide.ride_time).limit(50).all()

    booked_ride_ids = {b.ride_id for b in Booking.query.filter_by(passenger_id=user_id).all()}
    available_rides = []
    booked_rides_data = []

    now = datetime.now()

    for ride in all_rides:
        _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
        is_future_ride = ride_dt_end >= now
        is_completed = ride_dt_end < now
        is_booked_by_user = ride.id in booked_ride_ids
        is_rated = Rating.query.filter_by(ride_id=ride.id, passenger_id=user_id).first() is not None

        ride_data = {
            'ride': ride, 'rider_username': ride.rider.username,
            'is_future_ride': is_future_ride, 'is_completed': is_completed,
            'is_rated': is_rated
        }

        if is_booked_by_user:
            booked_rides_data.append(ride_data)
        elif is_future_ride and ride.seats_available > 0:
            available_rides.append(ride_data)

    booked_rides_data.sort(key=lambda x: datetime.combine(x['ride'].ride_date, x['ride'].ride_time))
    return render_template('optimized/passenger_dashboard.html',
                           available_rides=available_rides,
                           booked_rides=booked_rides_data,
                           unread_notifications_count=unread_notifications_count)

@bp.route('/notifications')
@requires_auth
def notifications():
    """View and clear notifications."""
    user_id = session['user_id']
    user_notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.timestamp.desc()).all()
    
    # Count unread notifications BEFORE marking them as read
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    
    # Mark all as read
    Notification.query.filter_by(user_id=user_id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    
    return render_template('optimized/notifications.html', 
                         notifications=user_notifications,
                         unread_notifications_count=unread_count)

@bp.route('/notifications/delete/<int:notification_id>', methods=['POST'])
@requires_auth
def delete_notification(notification_id):
    """Delete a specific notification."""
    user_id = session['user_id']
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notification:
        try:
            db.session.delete(notification)
            db.session.commit()
            return jsonify({'success': True})
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Database error'}), 500
    return jsonify({'success': False, 'message': 'Notification not found'}), 404

@bp.route('/notifications/mark_all_read', methods=['POST'])
@requires_auth
def mark_all_notifications_read():
    """Mark all notifications as read for the current user."""
    user_id = session['user_id']
    try:
        Notification.query.filter_by(user_id=user_id, is_read=False).update({Notification.is_read: True})
        db.session.commit()
        return jsonify({'success': True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Database error'}), 500

@bp.route('/profile/<string:username>')
@requires_auth
def profile(username):
    """View a user's profile."""
    user = User.query.filter_by(username=username).first_or_404()
    avg_rating = user.get_average_rating()
    return render_template('optimized/profile.html', user=user, avg_rating=avg_rating)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@requires_auth
def edit_profile():
    """Edit the current user's profile."""
    user_id = session['user_id']
    user = User.query.get(user_id)
    form = UpdateProfileForm()

    if form.validate_on_submit():
        if form.avatar.data:
            picture_file = save_picture(form.avatar.data)
            user.avatar_file = picture_file
        
        user.username = form.username.data
        user.gender = form.gender.data
        user.gender_preference = form.gender_preference.data
        user.bio = form.bio.data
        
        try:
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            return redirect(url_for('main.profile', username=user.username))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Error updating profile.', 'error')

    elif request.method == 'GET':
        form.username.data = user.username
        form.gender.data = user.gender
        form.gender_preference.data = user.gender_preference
        form.bio.data = user.bio

    image_file = url_for('static', filename='avatars/' + user.avatar_file)
    return render_template('optimized/edit_profile.html', title='Edit Profile',
                           image_file=image_file, form=form)
@bp.route('/setup-admin/<string:username>')
def setup_admin(username):
    """Temporary route to make a user an admin."""
    user = User.query.filter_by(username=username).first()
    if not user:
        return f"User '{username}' not found. Please register first.", 404
    
    user.is_admin = True
    try:
        db.session.commit()
        return f"SUCCESS! User '{username}' is now an admin. You can go to /admin", 200
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}", 500

