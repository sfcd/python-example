# coding: utf-8


class IStrategy(object):
    name = None


class IStrategyRegistryDataSource(object):
    def get_type_name(self):
        raise NotImplementedError()


class IFacebookLoader(object):
    def load(self, facebook_token):
        raise NotImplementedError()
