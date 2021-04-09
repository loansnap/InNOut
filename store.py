import logging
from pydash import _

from . import S

logger = logging.getLogger('in_n_out')

class Store():
    '''
    Store are created everytime there is a list_like element in the data.
    Each element of that list is its own store.
    Check test `test_storage` for explaination
    '''

    def __init__(self, previous_store):
        '''
        values: signal.key -> matched_value (string -> string)
        children: Store list
        depth: int
        '''
        self.values = {}
        self.children = []
        self.parent = None
        self.depth = previous_store.depth + 1 if previous_store else 0

        if previous_store:
            previous_store.children.append(self)
            self.parent = previous_store

    def add(self, key, value):
        self.values[key] = value

    def as_dict(self):
        return {
            'values': self.values,
            'depth': self.depth,
            'children': [s.as_dict() for s in self.children]
        }

    def __search_current(self, signal):
        for key, value in self.values.items():
            if key == signal.key:
                return value

    def __search_deep(self, signal: S):
        value = self.__search_current(signal)
        if value is not None:
            return value

        # gather all value from children if it cannot be found in current store
        values = _.filter(_.map(self.children, lambda store: store.__search_deep(signal)), lambda x: x != None)
        if values:
            return _.flatten(values)

    def __search_parents(self, signal: S):
        value = self.__search_current(signal)
        if value is not None:
            return value

        if self.parent:
            return self.parent.__search_parents(signal)

    def get_signal_value(self, signal: S, search_deep=True):
        if search_deep:
            value = self.__search_deep(signal)
            if value is not None:
                return value
        else:
            value = self.__search_current(signal)
            if value is not None:
                return value

        if self.parent:
            return self.parent.__search_parents(signal)


    def get_deepest_stores_for_signals(self, signals):
        '''
        Give a list of signals and find the deepest stores where one of the signal is present.
        Only consider the deepest stores for a given branch
        Stop once all signals' stores are found
        '''
        signals_left = []
        for signal in signals:
            if self.__search_current(signal) is None:
                signals_left.append(signal)

        # if we're found the last signals missing return the store as it is the deepest one for our search
        if len(signals_left) == 0:
            return [self]

        # if not keep looking deeper
        children_stores = []
        for child in self.children:
            stores = child.get_deepest_stores_for_signals(signals_left)
            children_stores += stores

        # If looking deeper does not yield any result, and the current store has the value of a signal,
        # return that store, as it is the deepest one with a value
        if len(children_stores) == 0 and len(signals_left) < len(signals):
            return [self]
        else:
            return children_stores


    def __str__(self):
        return str(self.as_dict())

    def __repr__(self):
        return f"{self.__class__.__name__}({self.values}, {self.children}, {self.depth})"
