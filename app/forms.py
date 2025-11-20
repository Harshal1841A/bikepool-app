from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField, IntegerField, DateField, TimeField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


# --- Forms ---
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Length(min=5, max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])

    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female')], validators=[DataRequired()])
    gender_preference = SelectField('Preferred Rider Gender',
                                   choices=[('Any', 'Any'), ('Male', 'Male'), ('Female', 'Female')],
                                   default='Any')
    is_rider = BooleanField('Register as Bike Rider? (Allows posting rides)')
    terms = BooleanField('I agree to the Terms and Conditions', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class PostRideForm(FlaskForm):
    source = StringField('Source', validators=[DataRequired(), Length(min=1, max=100)])
    destination = StringField('Destination', validators=[DataRequired(), Length(min=1, max=100)])
    seats = IntegerField('Seats Available', validators=[DataRequired(), NumberRange(min=1)], default=1)
    ride_date = DateField('Ride Date', validators=[DataRequired()])
    ride_time = TimeField('Start Time', validators=[DataRequired()])
    ride_end_time = TimeField('End Time', validators=[Optional()])
    rider_gender_preference = SelectField('Your Gender Preference for Passengers',
                                          choices=[('Any', 'Any'), ('Male', 'Male'), ('Female', 'Female')],
                                          default='Any')
    submit = SubmitField('Post Ride')

class UpdateProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female')], validators=[DataRequired()])
    gender_preference = SelectField('Preferred Rider Gender',
                                   choices=[('Any', 'Any'), ('Male', 'Male'), ('Female', 'Female')],
                                   default='Any')
    bio = TextAreaField('Bio')
    avatar = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Update Profile')

class DeleteRideForm(FlaskForm):

    submit = SubmitField('Delete Ride')
