# coding: utf-8


class StrategyRegistry(object):
    """
    A container for different strategies
    """
    data_source = None

    def __init__(self, data_source):
        """
        Constructor.
        :param sfkit.auth.interfaces.IStrategyRegistryDataSource data_source: a data source instance
        """
        self.available_strategies = {}
        self.data_source = data_source

    def add(self, strategy):
        """
        Add a strategy to the container
        :param sfkit.auth.interfaces.IStrategy strategy: a strategy instance
        """
        self.available_strategies[strategy.name] = strategy

    def delete(self, strategy):
        """
        Delete a strategy from the container
        :param sfkit.auth.interfaces.IStrategy strategy: a strategy instance
        """
        if strategy.name in self.available_strategies:
            del self.available_strategies[strategy.name]

    def find(self):
        """
        Find a strategy by its name. The name is taken from a data source.
        :return: a found strategy
        :rtype sfkit.auth.interfaces.IStrategy
        """
        selected_type = self.data_source.get_type_name()

        if selected_type in self.available_strategies:
            return self.available_strategies[selected_type]

