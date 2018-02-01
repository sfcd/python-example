# coding: utf-8

from flask import request

from .interfaces import ISessionSource


class GetQuerySource(ISessionSource):
    """
    Get a token from a query string.
    """
    default_token_name = 'auth_token'

    def __init__(self, token_name=None):
        self.token_name = token_name if token_name is not None else self.default_token_name

    def get_session_id(self, req=None):
        _req = req if req is not None else request
        return _req.args.get(self.token_name)


class HeaderSource(ISessionSource):
    """
    Get a token from a header
    """
    default_header_name = "SFCD-Auth-Token"

    def __init__(self, header_name=None):
        self.header_name = header_name if header_name is not None else self.default_header_name

    def get_session_id(self, req=None):
        _req = req if req is not None else request
        return _req.headers.get(self.header_name)
