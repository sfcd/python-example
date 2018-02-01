# coding: utf-8

import uuid

from flask.sessions import (
    SecureCookieSession,
    SessionInterface,
)


class SecureKeySession(SecureCookieSession):
    def __init__(self, initial=None, key=None):
        SecureCookieSession.__init__(self, initial)
        self.key = key

    def generate_new(self, new_id=None):
        """
        Create a new session. If the new_id is not set it's automaticaly generated.
        :param new_id: a new session id
        """
        self.key = str(uuid.uuid4()) if new_id is None else new_id
        self.modified = True


class CommonSessionInterface(SessionInterface):
    session_class = SecureKeySession

    def __init__(self, backend, source):
        self.backend = backend
        self.source = source

    def open_session(self, app, request):
        if not app.secret_key:
            return None

        sid = self.source.get_session_id()

        if sid is not None:
            data = self.backend.get_session_data(sid)

            if data is not None:
                return self.session_class(data, key=sid)

        return self.session_class()

    def save_session(self, app, session, response):
        if session.key is not None and session.modified:
            self.backend.save_session_data(session.key, session)


class SessionExtension(object):
    def __init__(self, backend, source, app=None):
        self.session_interface = CommonSessionInterface(backend, source)

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.session_interface = self.session_interface
