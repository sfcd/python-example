# coding: utf-8

from flask import session

from .interfaces import IUserLoader
from .strategies import (
    FacebookStrategy,
    SimpleStrategy,
)
from .. import StrategyRegistry
from ..errors import (
    StrategyNotDefined,
    UserIsNotActive
)
from ..login import login_user
from ... import validation as val
from ...errors import SFKitException
from ...reqparser import (
    RequestParser,
    six
)
from ...views import View


class AuthorizationControllerView(IUserLoader, View):
    methods = ['POST']

    error_exception = SFKitException
    strategies = [
        FacebookStrategy,
        SimpleStrategy
    ]
    strategy_registry_class = StrategyRegistry

    def __init__(self, db_delegate):
        self.db_delegate = db_delegate

        self.strategy_registry = self._create_strategy_registry()
        self._add_strategies(self.strategy_registry)

    def post(self):
        user = self.apply_strategy(self.strategy_registry.find())

        if self.will_sign_in(user) and user is not None and login_user(user):
            self.did_sign_in(user)
            return self.build_response({'token': self._generate_token()})

        self.error_handler(UserIsNotActive())

    def apply_strategy(self, strategy=None):
        if strategy is not None:
            return strategy.authorize(self.error_handler)

        self.error_handler(StrategyNotDefined())

    def get_type_name(self):
        parser = RequestParser()
        parser.add_argument('type')
        args = parser.parse_args()
        return args['type']

    def get_authorization_data(self):
        parser = RequestParser()
        parser.add_argument('facebook_token')
        parser.add_argument('login')
        parser.add_argument('password')

        schema = val.Schema({
            val.Optional('facebook_token'): val.Any(None, six.text_type),
            val.Optional('login'): val.Any(None, val.All(val.normalize(), val.email())),
            val.Optional('password'): val.Any(None, six.text_type),
        }, extra=True)

        return schema(parser.parse_args())

    def error_handler(self, error):
        raise self.error_exception(error)

    def load(self, **params):
        return self.db_delegate.find_by(**params)

    def will_sign_in(self, user):
        return True

    def did_sign_in(self, user):
        pass

    @classmethod
    def register(cls, app, endpoint='signin', url="/signin/", view_args=None, view_kwargs=None, **kwargs):
        super(AuthorizationControllerView, cls).register(app, url, endpoint, view_args, view_kwargs, **kwargs)

    def _create_strategy_registry(self):
        return self.strategy_registry_class(self)

    def _add_strategies(self, strategy_registry):
        for strategy in self.strategies:
            strategy = strategy(self, self)
            strategy.delegate = self
            strategy_registry.add(strategy)

    def _generate_token(self):
        session.generate_new()
        return session.key
