# coding: utf-8

from ..interfaces import IStrategy


class IAuthorizationStrategy(IStrategy):
    name = None
    user_loader = None  # sfkit.auth.authorization.interfaces.IViewDbDelegate
    data_source = None  # sfkit.auth.authorization.interfaces.IStrategyDataSource

    def __init__(self, user_loader, data_source):
        self.user_loader = user_loader
        self.data_source = data_source

    def authorize(self, error_callback=None):
        raise NotImplementedError()


class IStrategyDataSource(object):
    def get_authorization_data(self):
        raise NotImplementedError()


class IUserLoader(object):
    def load(self, **params):
        raise NotImplementedError()


class IViewDbDelegate(object):
    def find_by(self, **params):
        raise NotImplementedError()
