# coding: utf-8

from flask import current_app

from datetime import (
    datetime,
    timedelta,
)

from .interfaces import ISessionBackend
from .signals import (
    on_after_create,
    on_after_update,
    on_after_save,
    on_before_save,
    on_get,
)


class SQLAlchemySessionBackend(ISessionBackend):
    """
    A session backend based on sqlalchemy ORM.
    """

    def __init__(self, db_session, session_table, expiration=30):
        """
        Constructor. A session table should have three fields:
        * session_id,
        * session_data,
        * expiration_date
        :param db_session: an sqlalchemy session
        :param session_table: an sqlalchemy model sfkit.models.sa.SessionModelMixin
        :param expiration: when the session will be expired in days
        """
        self.db_session = db_session
        self.session_table = session_table
        self.expiration = expiration

    def get_session_data(self, session_id):
        table = self.session_table
        time_diff = datetime.utcnow() - timedelta(days=self.expiration)

        # load nonexpired session
        row = self.db_session.query(table.session_data).filter(
            table.session_id == session_id, table.expiration_date >= time_diff).first()

        on_get.send(current_app._get_current_object(),
                    backend=self,
                    session=row)

        return row.session_data if row is not None else row

    def save_session_data(self, session_id, data):
        print(session_id)
        db_session = self.db_session
        table = self.session_table
        now = datetime.utcnow()

        session_row = db_session.query(table).get(session_id)
        session_data = dict(data)
        is_new = False

        if not session_row:
            # create a new session
            is_new = True

            session_row = table(session_id=session_id, session_data=session_data, expiration_date=now)
            on_after_create.send(current_app._get_current_object(),
                                 backend=self,
                                 session=session_row,
                                 is_new=is_new)

            db_session.add(session_row)
        else:
            # or update the current one
            session_row.session_data = session_data

            # check expiration date and update if it's not expired
            if session_row.expiration_date >= (now - timedelta(days=self.expiration)):
                session_row.expiration_date = now

            on_after_update.send(current_app._get_current_object(),
                                 backend=self,
                                 session=session_row,
                                 is_new=is_new)

        db_session.flush()

        on_before_save.send(current_app._get_current_object(),
                            backend=self,
                            session=session_row,
                            is_new=is_new)

        db_session.commit()

        on_after_save.send(current_app._get_current_object(),
                           backend=self,
                           session=session_row,
                           is_new=is_new)
