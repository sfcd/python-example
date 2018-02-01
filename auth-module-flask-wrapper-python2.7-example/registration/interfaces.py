# coding: utf-8

from ..interfaces import IStrategy


class IRegistrationStrategy(IStrategy):
    name = None
    unique_check_delegate = None
    data_source = None
    delegate = None
    """:type : IStrategyDelegate"""

    def __init__(self, unique_check_delegate, data_source):
        """
        :param IUniqueCheckDelegate unique_check_delegate: a delegate instance for checking the uniqueness of the user
        :param IStrategyDataSource data_source: a data source instance
        """
        self.data_source = data_source
        self.unique_check_delegate = unique_check_delegate

    def register(self, user, error_callback=None):
        raise NotImplementedError()


class IViewDbDelegate(object):
    def get_empty(self):
        raise NotImplementedError()

    def save(self, user):
        raise NotImplementedError()

    def find_by(self, **params):
        raise NotImplementedError()


class IStrategyDataSource(object):
    def get_registration_data(self):
        raise NotImplementedError()


class IUniqueCheckDelegate(object):
    def check(self, **params):
        raise NotImplementedError()


class IStrategyDelegate(object):
    def will_user_save(self, strategy, user, *args, **kwargs):
        pass

    def did_user_save(self, strategy, user):
        pass
