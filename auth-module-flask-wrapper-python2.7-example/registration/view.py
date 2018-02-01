# coding: utf-8

from .interfaces import IUniqueCheckDelegate
from .strategies import (
    FacebookStrategy,
    SimpleStrategy,
)
from .. import StrategyRegistry
from ..interfaces import IStrategyRegistryDataSource
from ..errors import StrategyNotDefined
from ... import validation as val
from ...errors import SFKitException
from ...reqparser import (
    RequestParser,
    six
)
from ...views import View


class RegistrationControllerView(IStrategyRegistryDataSource, IUniqueCheckDelegate, View):
    methods = ['POST']

    error_exception = SFKitException
    strategies = [
        FacebookStrategy,
        SimpleStrategy
    ]
    strategy_registry_class = StrategyRegistry

    def __init__(self, db_delegate):
        """
        :param sfkit.auth.registration.interfaces.IViewDbDelegate db_delegate: a database delegate instance
        """
        self.db_delegate = db_delegate

        self.strategy_registry = self._create_strategy_registry()
        self._add_strategies(self.strategy_registry)

    def post(self):
        self.apply_strategy(self.strategy_registry.find())
        return self.build_response(None).status(201)

    def apply_strategy(self, strategy=None):
        new_user = self.db_delegate.get_empty()

        if strategy is None:
            self.error_handler(StrategyNotDefined())
            return

        if self.will_register(new_user):
            strategy.register(new_user, self.error_handler)
            self.save(new_user)
            self.did_register(new_user)

    def get_type_name(self):
        parser = RequestParser()
        parser.add_argument('type')
        args = parser.parse_args()
        return args['type']

    def get_registration_data(self):
        parser = RequestParser()
        parser.add_argument('facebook_token')
        parser.add_argument('login')
        parser.add_argument('password')
        parser.add_argument('email')

        schema = val.Schema({
            val.Optional('facebook_token'): val.Any(None, six.text_type),
            val.Optional('login'): val.Any(None, val.All(val.normalize(), val.email())),
            val.Optional('password'): val.Any(None, val.All(six.text_type, val.Length(3))),
            val.Optional('email'): val.All(val.email(), val.normalize()),
        }, extra=True)

        return schema(parser.parse_args())

    def error_handler(self, error):
        raise self.error_exception(error)

    def save(self, user):
        self.db_delegate.save(user)

    def will_register(self, user):
        return True

    def did_register(self, user):
        pass

    def _create_strategy_registry(self):
        """
        :return: a strategy registry
        :rtype sfkit.auth.StrategyRegistry
        """
        return self.strategy_registry_class(self)

    def _add_strategies(self, strategy_registry):
        for strategy_class in self.strategies:
            strategy = strategy_class(self, self)
            strategy.delegate = self
            strategy_registry.add(strategy)

    def check(self, **params):
        return self.db_delegate.find_by(**params) is not None

    @classmethod
    def register(cls, app, endpoint='signup', url="/signup/", view_args=None, view_kwargs=None, **kwargs):
        super(RegistrationControllerView, cls).register(app, endpoint, url, view_args, view_kwargs, **kwargs)
