# -*- coding: utf-8 -*-

from functools import wraps

from flask import (
    _request_ctx_stack,
    abort,
    current_app,
    session,
)
from flask.signals import Namespace
from werkzeug.local import LocalProxy

_signals = Namespace()

#: A proxy for the current user. If no user is logged in, this will be an
#: anonymous user
current_user = LocalProxy(lambda: _get_user())


class LoginManager(object):
    """
    This object is used to hold the settings used for logging in. Instances of
    :class:`LoginManager` are *not* bound to specific apps, so you can create
    one in the main body of your code and then bind it to your
    app in a factory function.
    """
    def __init__(self, app=None):
        #: A class or factory function that produces an anonymous user, which
        #: is used when no one is logged in.
        self.anonymous_user = AnonymousUserMixin
        self.user_callback = None
        self.unauthorized_callback = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Configures an application. This attaches this `LoginManager` to
        it as `app.login_manager`.

        :param app: The :class:`flask.Flask` object to configure.
        :type app: :class:`flask.Flask`
        """
        app.login_manager = self

        self._login_disabled = app.config.get('LOGIN_DISABLED',
                                              app.config.get('TESTING', False))

    def unauthorized(self):
        """
        This is called when the user is required to log in. If you register a
        callback with :meth:`LoginManager.unauthorized_handler`, then it will
        be called. Otherwise, it will call 401 error.
        """
        user_unauthorized.send(current_app._get_current_object())

        if self.unauthorized_callback:
            return self.unauthorized_callback()

        abort(401)

    def user_loader(self, callback):
        """
        This sets the callback for reloading a user from the session. The
        function you set should take a user ID (a ``unicode``) and return a
        user object, or ``None`` if the user does not exist.

        :param callback: The callback for retrieving a user object.
        :type callback: function
        """
        self.user_callback = callback
        return callback

    def unauthorized_handler(self, callback):
        """
        This will set the callback for the `unauthorized` method, which among
        other things is used by `login_required`. It takes no arguments, and
        should return a response to be sent to the user instead of their
        normal view.

        :param callback: The callback for unauthorized users.
        :type callback: function
        """
        self.unauthorized_callback = callback
        return callback

    def reload_user(self, user=None):
        ctx = _request_ctx_stack.top

        if user is None:
            user_id = session.get('user_id')
            if user_id is None:
                ctx.user = self.anonymous_user()
            else:
                user = self.user_callback(user_id)
                if user is None:
                    logout_user()
                else:
                    ctx.user = user
        else:
            ctx.user = user

    def _load_user(self):
        """Loads user from session"""
        user_accessed.send(current_app._get_current_object())
        return self.reload_user()


class UserMixin(object):
    """
    This provides default implementations for the methods that Flask-Login
    expects user objects to have.
    """
    def is_active(self):
        return True

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False


class AnonymousUserMixin(object):
    """
    This is the default object for representing an anonymous user.
    """
    def is_authenticated(self):
        return False

    def is_active(self):
        return False

    def is_anonymous(self):
        return True


def login_user(user, force=False):
    """
    Logs a user in. You should pass the actual user object to this. If the
    user's `is_active` method returns ``False``, they will not be logged in
    unless `force` is ``True``.

    This will return ``True`` if the log in attempt succeeds, and ``False`` if
    it fails (i.e. because the user is inactive).

    :param user: The user object to log in.
    :type user: UserMixin
    :param force: If the user is inactive, setting this to ``True`` will log
        them in regardless. Defaults to ``False``.
    :type force: bool
    """
    if not force and not user.is_active():
        return False

    session['user_id'] = user.id

    _request_ctx_stack.top.user = user
    user_logged_in.send(current_app._get_current_object(), user=_get_user())
    return True


def logout_user():
    """
    Logs a user out. (You do not need to pass the actual user.) This will
    also clean up the remember me cookie if it exists.
    """
    if 'user_id' in session:
        session.pop('user_id')

    user = _get_user()
    if user and not user.is_anonymous():
        user_logged_out.send(current_app._get_current_object(), user=user)

    current_app.login_manager.reload_user()
    return True


def login_required(func):
    """
    If you decorate a view with this, it will ensure that the current user is
    logged in and authenticated before calling the actual view. (If they are
    not, it calls the :attr:`LoginManager.unauthorized` callback.) For
    example::

        @app.route('/post')
        @login_required
        def post():
            pass

    If there are only certain times you need to require that your user is
    logged in, you can do so with::

        if not current_user.is_authenticated():
            return current_app.login_manager.unauthorized()

    ...which is essentially the code that this function adds to your views.

    It can be convenient to globally turn off authentication when unit
    testing. To enable this, if either of the application
    configuration variables `LOGIN_DISABLED` or `TESTING` is set to
    `True`, this decorator will be ignored.

    :param func: The view function to decorate.
    :type func: function
    """
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_app.login_manager._login_disabled:
            return func(*args, **kwargs)
        elif not current_user.is_authenticated():
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def _get_user():
    if not hasattr(_request_ctx_stack.top, 'user'):
        current_app.login_manager._load_user()

    return getattr(_request_ctx_stack.top, 'user', None)


# Signals

#: Sent when a user is logged in. In addition to the app (which is the
#: sender), it is passed `user`, which is the user being logged in.
user_logged_in = _signals.signal('logged-in')

#: Sent when a user is logged out. In addition to the app (which is the
#: sender), it is passed `user`, which is the user being logged out.
user_logged_out = _signals.signal('logged-out')

#: Sent when the `unauthorized` method is called on a `LoginManager`. It
#: receives no additional arguments besides the app.
user_unauthorized = _signals.signal('unauthorized')

#: Sent whenever the user is accessed/loaded
#: receives no additional arguments besides the app.
user_accessed = _signals.signal('accessed')
