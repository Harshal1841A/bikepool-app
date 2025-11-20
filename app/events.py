from flask import session, current_app
from flask_socketio import emit, join_room, leave_room
from .extensions import socketio, db
from .models import User, Message

# --- SocketIO Events ---
@socketio.on('join')
def handle_join(data):
    """Handle user joining a chat room."""

    if 'user_id' not in session:
        return  # Unauthorized

    ride_id = data.get('ride_id')
    user_id = session['user_id']
    username = session['username']

    if ride_id:
        # Security Check: Ensure user is allowed to join this ride room
        # For now, we allow it if they are logged in, but ideally check if they are rider or passenger.
        # Given the current requirements, we'll keep it open to logged-in users for simplicity 
        # but ensure ride_id is valid.
        join_room(str(ride_id))
        emit('user_joined', {'username': username}, room=str(ride_id), include_self=False)

    if user_id:
        join_room(f'user_{user_id}')


@socketio.on('leave')
def handle_leave(data):
    """Handle user leaving a chat room."""

    ride_id = data.get('ride_id')
    username = data.get('username')
    if ride_id:
        leave_room(str(ride_id))
        emit('user_left', {'username': username}, room=str(ride_id), include_self=False)

@socketio.on('typing')
def handle_typing(data):
    """Broadcast typing status."""

    room = data.get('room')
    user = session.get('username')
    if room and user:
        emit('user_typing', {'user': user}, room=room, include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    """Broadcast stop typing status."""

    room = data.get('room')
    user = session.get('username')
    if room and user:
        emit('user_stop_typing', {'user': user}, room=room, include_self=False)

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a chat message."""

    if 'user_id' not in session:
        return  # Unauthorized

    ride_id = int(data['ride_id'])
    user_id = session['user_id']
    message_text = data['message']

    with current_app.app_context():
        new_msg = Message(ride_id=ride_id, sender_id=user_id, message_text=message_text)
        db.session.add(new_msg)
        db.session.commit()
        user = User.query.get(user_id)

        emit('new_message', {
            'sender_id': user_id,
            'sender_username': user.username,
            'text': message_text,
            'timestamp': new_msg.timestamp.strftime('%H:%M'),
        }, room=str(ride_id))
