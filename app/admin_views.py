from flask import redirect, url_for, session, flash
from flask_admin.contrib.sqla import ModelView
from flask_admin import AdminIndexView


class AdminModelView(ModelView):
    """Custom admin view that restricts access to admin users."""
    
    def is_accessible(self):
        return session.get('is_admin', False)
    
    def inaccessible_callback(self, name, **kwargs):
        flash("You must be an admin to access this page.", 'error')
        return redirect(url_for('auth.login'))


class MyAdminIndexView(AdminIndexView):
    """Custom admin index view with access control."""
    
    def is_accessible(self):
        return session.get('is_admin', False)
    
    def inaccessible_callback(self, name, **kwargs):
        flash("You must be an admin to access this page.", 'error')
        return redirect(url_for('auth.login'))
