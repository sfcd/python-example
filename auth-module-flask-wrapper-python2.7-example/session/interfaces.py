# coding: utf-8


class ISessionSource(object):
    """
    A class which loads a session_id from different sources (such as queries, headers and etc.)
    """

    def get_session_id(self):
        """
        Return a session id
        :return:
        """
        raise NotImplementedError()


class ISessionBackend(object):
    """
    How to manage session data
    """

    def get_session_data(self, session_id):
        """
        Get session data from some backend (database, file, etc).
        If there is no session with session_id return None
        :param session_id:
        :return: session data or None
        """
        raise NotImplementedError()

    def save_session_data(self, session_id, data):
        """
        Save session data to some backend (database, file, etc).
        :param session_id:
        :param data:
        """
        raise NotImplementedError()
