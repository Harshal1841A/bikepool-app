from flask import Blueprint, request, jsonify
from ..extensions import limiter
from ..models import User

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/check_username')
@limiter.limit("10 per minute")
def check_username():
    """Check if a username is available."""
    username = (request.args.get('username') or '').strip().lower()
    if not username or len(username) < 3:
        return jsonify({'available': False, 'message': 'Username must be at least 3 characters.'})

    user = User.query.filter_by(username=username).first()
    return jsonify({'available': user is None})
