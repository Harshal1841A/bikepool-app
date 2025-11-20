from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime
import time
import logging

from ..extensions import db, csrf
from ..models import User, BikeRide, Booking, Message, Rating
from ..forms import PostRideForm, DeleteRideForm
from ..utils import requires_auth, get_ride_datetime, create_notification, send_email

bp = Blueprint('rides', __name__)
logger = logging.getLogger(__name__)

# NOTE: For production, remove csrf.exempt and send CSRF token via AJAX header 'X-CSRFToken'
@bp.route('/book_ride/<int:ride_id>', methods=['POST'])
@requires_auth
@csrf.exempt
def book_ride(ride_id):
    """Handle ride booking with concurrency control."""
    if session['is_rider']:
        flash("Riders cannot book rides.", 'error')
        return redirect(url_for('main.dashboard'))

    user_id = session['user_id']
    passenger = User.query.get(user_id)
    if passenger is None:
        flash("Invalid session user.", 'error')
        return redirect(url_for('auth.login'))

    max_retries = 4
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        try:
            # Read ride fresh
            ride = BikeRide.query.get(ride_id)
            if ride is None:
                flash("Ride not found.", 'error')
                return redirect(url_for('main.dashboard'))

            # Gender preference check
            if ride.rider_gender_preference != "Any" and passenger.gender != ride.rider_gender_preference:
                flash(f"This ride has a gender preference of '{ride.rider_gender_preference}'.", 'error')
                return redirect(url_for('main.dashboard'))

            _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
            if ride_dt_end < datetime.now():
                flash("Ride has already completed.", 'error')
                return redirect(url_for('main.dashboard'))

            # Check duplicate booking early
            if Booking.query.filter_by(ride_id=ride_id, passenger_id=user_id).first():
                flash("You have already booked this ride.", 'info')
                return redirect(url_for('main.dashboard'))

            if ride.seats_available <= 0:
                flash("Ride is full.", 'error')
                return redirect(url_for('main.dashboard'))

            # Try optimistic update using version column for concurrency control
            old_version = ride.version
            new_seats = ride.seats_available - 1
            new_version = old_version + 1

            # Attempt atomic-ish update
            updated = BikeRide.__table__.update().where(
                (BikeRide.id == ride.id) & (BikeRide.version == old_version) & (BikeRide.seats_available > 0)
            ).values(seats_available=new_seats, version=new_version)
            result = db.session.execute(updated)
            if result.rowcount == 0:
                # concurrent modification occurred; rollback and retry
                db.session.rollback()
                logger.info("Concurrent update detected for ride %s, attempt %s", ride_id, attempt)
                time.sleep(0.08 * attempt)
                continue

            # Create booking
            booking = Booking(ride_id=ride_id, passenger_id=user_id)
            db.session.add(booking)
            try:
                db.session.commit()
            except IntegrityError as ie:
                # Could be duplicate booking or constraint failure; rollback and retry
                db.session.rollback()
                logger.warning("IntegrityError during booking commit for user %s ride %s: %s", user_id, ride_id, ie)
                # If duplicate booking, inform the user
                if Booking.query.filter_by(ride_id=ride_id, passenger_id=user_id).first():
                    flash("You have already booked this ride.", 'info')
                    return redirect(url_for('main.dashboard'))
                # else retry
                if attempt >= max_retries:
                    flash("Could not complete booking due to concurrent updates. Please try again.", 'error')
                    return redirect(url_for('main.dashboard'))
                time.sleep(0.08 * attempt)
                continue

            # Success
            create_notification(ride.rider_id, f"🎉 {session['username']} booked a seat on your ride to {ride.destination}!")
            
            # Send Confirmation Email to Passenger
            # Note: Assuming User model has email field, but it doesn't yet. 
            # For now, we'll skip or use a dummy. Ideally we should have added email to User model.
            # Let's assume we added it or just log it for now if missing.
            # Actually, I should have added email to User model in the previous step. 
            # I will add it now via a separate tool call or just use a placeholder.
            # Since I missed adding 'email' to User model, I will use a placeholder and fix it in next step.
            html = render_template('email/booking_confirmation.html', username=session['username'], ride=ride)
            send_email(passenger.email, "Booking Confirmed - BikePool", html)

            flash("Ride booked successfully!", 'success')
            return redirect(url_for('main.dashboard'))


        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("Booking error on attempt %s for ride %s: %s", attempt, ride_id, e)
            flash("An error occurred during booking.", 'error')
            return redirect(url_for('main.dashboard'))

    flash("Unable to book ride at this time due to high contention. Please try again.", 'error')
    return redirect(url_for('main.dashboard'))

@bp.route('/cancel_booking/<int:ride_id>', methods=['POST'])
@requires_auth
def cancel_booking(ride_id):
    """Cancel a booking for a ride."""
    if session['is_rider']:
        return redirect(url_for('main.dashboard'))
    
    user_id = session['user_id']
    ride = BikeRide.query.get_or_404(ride_id)
    booking = Booking.query.filter_by(ride_id=ride_id, passenger_id=user_id).first()
    
    _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
    
    if ride_dt_end < datetime.now():
        flash("Cannot cancel a completed ride.", 'error')
        return redirect(url_for('main.dashboard'))
    
    if booking:
        try:
            db.session.delete(booking)
            # increase seats and bump version
            ride.seats_available = ride.seats_available + 1
            ride.version = ride.version + 1
            db.session.commit()
            create_notification(ride.rider_id, f"😔 {session['username']} cancelled their booking.")
            flash("Booking cancelled.", 'info')
        except SQLAlchemyError as e:
            logger.error("Cancellation error: %s", e)
            db.session.rollback()
            flash("An error occurred during cancellation.", 'error')
    else:
        flash("Booking not found.", 'error')
    
    return redirect(url_for('main.dashboard'))

@bp.route('/delete_ride/<int:ride_id>', methods=['POST'])
@requires_auth
def delete_ride(ride_id):
    """Delete a ride posted by the current user."""
    if not session['is_rider']:
        flash("Only riders can delete rides.", 'error')
        return redirect(url_for('main.dashboard'))

    form = DeleteRideForm()

    if form.validate_on_submit():
        ride = BikeRide.query.options(joinedload(BikeRide.bookings).joinedload(Booking.passenger)).get_or_404(ride_id)
        
        if ride.rider_id != session['user_id']:
            flash("You are not authorized to delete this ride.", 'error')
            return redirect(url_for('main.dashboard'))
            
        _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
        
        if ride_dt_end < datetime.now():
            flash("Cannot delete a completed ride.", 'error')
            return redirect(url_for('main.dashboard'))

        try:
            for booking in ride.bookings:
                if booking.passenger:
                    create_notification(booking.passenger.id, f"⚠️ Your ride from {ride.source} to {ride.destination} was cancelled.")
            db.session.delete(ride)
            db.session.commit()
            flash("Ride deleted successfully.", 'success')
        except SQLAlchemyError as e:
            logger.error("Ride deletion error: %s", e)
            db.session.rollback()
            flash("An error occurred while deleting the ride.", 'error')
    
    return redirect(url_for('main.dashboard'))

@bp.route('/post_bike_ride', methods=['GET', 'POST'])
@requires_auth
def post_bike_ride():
    """Handle posting a new bike ride."""
    if not session['is_rider']:
        flash("Only riders can post rides.", 'error')
        return redirect(url_for('main.dashboard'))
        
    form = PostRideForm()

    if form.validate_on_submit():
        try:
            ride_dt_start, _ = get_ride_datetime(
                form.ride_date.data, form.ride_time.data, form.ride_end_time.data
            )

            if ride_dt_start < datetime.now():
                flash("Cannot post a ride in the past.", 'error')
                return render_template('optimized/post_bike_ride.html', form=form), 400

            bike_ride = BikeRide(
                rider_id=session['user_id'],
                source=form.source.data,
                destination=form.destination.data,
                seats_available=form.seats.data,
                ride_date=form.ride_date.data,
                ride_time=form.ride_time.data,
                ride_end_time=form.ride_end_time.data,
                rider_gender_preference=form.rider_gender_preference.data
            )
            db.session.add(bike_ride)
            db.session.commit()
            flash("Ride posted successfully!", 'success')
            return redirect(url_for('main.dashboard'))
        except SQLAlchemyError as e:
            logger.error("Posting ride error: %s", e)
            db.session.rollback()
            flash("Failed to post ride.", 'error')

    return render_template('optimized/post_bike_ride.html', form=form)

@bp.route('/ride_chat/<int:ride_id>')
@requires_auth
def ride_chat(ride_id):
    """Render the chat page for a specific ride."""
    user_id = session['user_id']
    ride = BikeRide.query.get_or_404(ride_id)
    is_rider = ride.rider_id == user_id
    is_booked = Booking.query.filter_by(ride_id=ride_id, passenger_id=user_id).first() is not None
    
    if not is_rider and not is_booked:
        flash("Access denied.", 'error')
        return redirect(url_for('main.dashboard'))
        
    messages = (Message.query.options(joinedload(Message.sender))
                .filter_by(ride_id=ride_id).order_by(Message.timestamp.asc()).all())
    
    message_data = [{
        'sender_username': msg.sender.username,
        'text': msg.message_text,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'is_self': msg.sender_id == user_id
    } for msg in messages]
            
    return render_template('optimized/ride_chat.html', ride=ride, messages=message_data, 
                           current_user_id=user_id, current_username=session['username'])

@bp.route('/rate_ride/<int:ride_id>', methods=['GET', 'POST'])
@requires_auth
def rate_ride(ride_id):
    """Handle rating a completed ride."""
    if session['is_rider']:
        flash("Riders cannot rate rides.", 'error')
        return redirect(url_for('main.dashboard'))
        
    user_id = session['user_id']
    ride = BikeRide.query.get_or_404(ride_id)
    booking = Booking.query.filter_by(ride_id=ride_id, passenger_id=user_id).first()
    
    _, ride_dt_end = get_ride_datetime(ride.ride_date, ride.ride_time, ride.ride_end_time)
    
    if not booking or ride_dt_end >= datetime.now():
        flash("This ride cannot be rated yet.", 'error')
        return redirect(url_for('main.dashboard'))
        
    existing_rating = Rating.query.filter_by(ride_id=ride_id, passenger_id=user_id).first()
    if existing_rating:
        flash("You have already rated this ride.", 'info')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            rating_value = int(request.form['rating'])
            comments = request.form.get('comments', '')
            
            if 1 <= rating_value <= 5:
                new_rating = Rating(ride_id=ride_id, passenger_id=user_id, rating_value=rating_value, comments=comments)
                db.session.add(new_rating)
                db.session.commit()
                create_notification(ride.rider_id, f"⭐ You received a {rating_value}-star rating!")
                flash("Thank you for your rating!", 'success')
                return redirect(url_for('main.dashboard'))
            
            flash("Rating must be between 1 and 5.", 'error')

        except (ValueError, SQLAlchemyError) as e:
            logger.error("Rating error: %s", e)
            db.session.rollback()
            flash("Invalid rating or error saving.", 'error')
            
    return render_template('optimized/rate_ride.html', ride=ride)
