from flask import Blueprint, render_template, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import SQLAlchemyError
import logging

from ..extensions import db, limiter
from ..models import User
from ..forms import RegistrationForm, LoginForm
from ..utils import _DUMMY_PASSWORD_HASH, send_email


bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        email = form.email.data.strip().lower()
        password = form.password.data
        gender = form.gender.data
        is_rider = form.is_rider.data
        gender_preference = form.gender_preference.data

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", 'error')
            return render_template('optimized/register.html', form=form)

        hashed_password = generate_password_hash(password)
        user = User(username=username, email=email, password_hash=hashed_password, gender=gender, is_rider=is_rider, gender_preference=gender_preference)
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send Welcome Email
            html = render_template('email/welcome.html', username=username)
            send_email(user.email, "Welcome to BikePool!", html)
            
            flash("Registration successful! Please log in.", 'success')
            return redirect(url_for('auth.login'))
        except SQLAlchemyError as e:
            logger.error("Registration error: %s", e)
            db.session.rollback()
            flash("Unexpected error during registration.", 'error')
            return render_template('optimized/register.html', form=form)

    return render_template('optimized/register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("100 per minute")
def login():
    """Handle user login."""
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        
        if user is None:
            # Do a single password hash comparison to keep timing similar
            check_password_hash(_DUMMY_PASSWORD_HASH, password)
        elif check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_rider'] = user.is_rider
            session['is_admin'] = user.is_admin
            flash(f"Welcome back, {user.username}!", 'success')
            return redirect(url_for('main.dashboard'))
            
        flash("Invalid username or password.", 'error')
        return redirect(url_for('auth.login'))
        
    return render_template('optimized/login.html', form=form)

@bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", 'info')
    return redirect(url_for('main.home'))
