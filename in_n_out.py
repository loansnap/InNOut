import copy
import logging
from pydash import _

try:
    from django.db.models import QuerySet
    django_installed = True
except ModuleNotFoundError:
    # default QuerySet matching to list
    QuerySet = list
    django_installed = False

from . import Store, S, Trans, MatchTrans, FormatTrans

logger = logging.getLogger('in_n_out')

class IncorrecTypeException(Exception):
    pass


class State():
    def __init__(self, path, search_deep, want_return, store):
        self.path = path
        self.search_deep = search_deep
        self.want_return = want_return
        self.store = store


class InNOut():
    list_like = (list, tuple, QuerySet)
    non_static = (S, dict, Trans, MatchTrans, FormatTrans) + list_like

    def __init__(self, template, data, debug=False):
        self.template = copy.deepcopy(template)
        self.data = data
        self.debug_log = debug
        self.root_store = self.__new_store(None)
        self.match(self.template, self.data, 'root', self.root_store)

    def __next_path(self, path, key):
        if path == '' or path == None:
            return key
        else:
            return f"{path}.{key}"

    def __is_non_static(self, value):
        return isinstance(value, self.non_static) or callable(value)

    def __new_store(self, current_store):
        return Store(current_store)

    def __debug(self, s):
        if self.debug_log:
            print(f"{self.__class__.__name__}: {s}")
        logger.debug(s)

    def __clean(self, result, deepclean=False):
        if isinstance(result, InNOut.list_like):
            l = []
            for x in result:
                x = self.__clean(x, deepclean)
                if x is not None:
                    l.append(x)
            if deepclean and l == []:
                return None
            return l
        elif isinstance(result, dict):
            d = {}
            for k, v in result.items():
                v = self.__clean(v, deepclean)
                if v is not None:
                    d[k] = v
            if deepclean and d == {}:
                return None
            return d
        else:
            return result


    ###########
    # MATCHING
    ###########

    def __match_list(self, template_list, data_list, path, current_store):
        # To handle xmltodict, if the template request a list, but the data isn't one,
        # make the data the only element in the list
        if not isinstance(data_list, self.list_like):
            data_list = [data_list]

        for idx, template in enumerate(template_list):
            for data in data_list:
                self.match(
                    template,
                    data,
                    self.__next_path(path, str(idx)),
                    self.__new_store(current_store)
                )
        # When no processing happen (e.g: static matching), the store will be empty
        # clean empty store created.
        current_store.children = _.filter(current_store.children, lambda x: bool(x.values))

    def __match_dict(self, template, data, path, store):
        def get_data_element(data, key):
            def is_relationship_manager(el):
                return django_installed and el.__class__.__name__ == 'RelatedManager' and hasattr(el, 'all')

            if isinstance(data, dict):
                return data.get(key)
            elif isinstance(data, self.list_like):
                logger.warning(f"Matching template is a dictionary but data is a list. Taking first element of the list. It is advised to fix these. path={path} key={key}")
                return get_data_element(data[0], key) if len(data) > 0 else None
            else:
                if hasattr(data, key):
                    el = getattr(data, key)
                    if is_relationship_manager(el):
                        return el.all()
                    elif callable(el):
                        return el()
                    else:
                        return el

        def can_extract(template, data, path):
            '''
            The function will look at the current depth, and check if there is any static values that
            needs to be present before allowing the extraction of signals.
            That allows for { 'users': [ { 'username': 'brian', email: S('email')} ] }. Only extract for `username == 'brian'`
            '''
            for key, value in template.items():
                if not self.__is_non_static(value) and value != get_data_element(data, key):
                    self.__debug(f"Cannot extract data {value} of type {type(value)} is static and not equal to {get_data_element(data, key)}, path={path}")
                    return False
            return True

        if not can_extract(template, data, path):
            return

        for key, value in template.items():
            self.match(
                value,
                get_data_element(data, key),
                self.__next_path(path, key),
                store
            )


    def match(self, template, data, path, store):
        if isinstance(template, MatchTrans) or isinstance(template, Trans):
            self.__debug(f"Matching MatchTrans value={data}, path={path}")
            template.transform(
                data,
                store,
                dir='match',
                debug=self.debug_log,
            )
            return

        if data is None:
            self.__debug(f"No data available for matching, path={path}")
            return

        # If Trans is defined without match, take the template from the Trans.
        # For FormatTrans, just take the template
        if isinstance(template, Trans) and not template.match or isinstance(template, FormatTrans):
            self.__debug(f"Found FormatTrans. Using inner template. value={data}, path={path}")
            template = template.template

        if isinstance(template, S):
            self.__debug(f"Matching value signal={template.key} value={data}, path={path}")
            store.add(template.key, data)

        elif isinstance(template, MatchTrans) or isinstance(template, Trans):
            self.__debug(f"Matching MatchTrans value={data}, path={path}")
            template.transform(
                data,
                store,
                dir='match',
                debug=self.debug_log,
            )
        elif isinstance(template, dict):
            self.__debug(f"Matching dict path={path}")
            self.__match_dict(
                template,
                data,
                path,
                store,
            )
        elif isinstance(template, self.list_like):
            self.__debug(f"Matching list path={path}")
            self.__match_list(
                template,
                data,
                path,
                store
            )
        else:
            self.__debug(f"Matching Nothing value={template} type = {type(template)}, path={path}")


    #############
    # FORMATTING
    #############

    def __proceed_format_dict(self, format_template, state, deepest_stores):
        def proceed_single_elements(store, result_dict, template):
            for key, template in template.items():
                if isinstance(template, Trans) and not template.format or isinstance(template, MatchTrans):
                    template = template.template

                if isinstance(template, dict):
                    result_dict[key] = proceed_single_elements(store, {}, template)
                else:
                    next_state = State(
                        path=self.__next_path(state.path, key),
                        search_deep=False,
                        want_return='single',
                        store=store,
                    )
                    result_dict[key] = self.__format(
                        template,
                        next_state,
                    )
            return result_dict


        result_list = []
        for store in deepest_stores:
            result_dict = proceed_single_elements(store, {}, format_template)

            if result_dict:
                result_list.append(result_dict)

        return result_list


    def __format_dict(self, format_template, state):
        def get_dict_signals(d, acc=[]):
            '''
            Get a list of signals at this level, ignore list_like and FormatTrans are they are another sub-template
            The goal here is to complete all these signals in __proceed_format_dict
            '''
            for k, template in d.items():
                if isinstance(template, Trans) or isinstance(template, MatchTrans) or isinstance(template, FormatTrans):
                    template = template.template

                if isinstance(template, S):
                    acc.append(template)
                elif isinstance(template, dict):
                    acc = get_dict_signals(template, acc)

            return acc

        signals = get_dict_signals(format_template)
        stores = state.store.get_deepest_stores_for_signals(signals)

        # If several stores are returns or not the current store (so deeper store), it means we're doing some accumulation.
        # If we are doing accumulation the user must request a want_return as list.
        # When state.want_return == 'single', we always want to use the current store, get_deepest_stores_for_signals
        # is called for handling error only
        if state.want_return == 'single':
            if len(stores) > 1 or (len(stores) == 1 and stores[0] != state.store):
                raise IncorrecTypeException(f"Requested a dictionary but got a list. One of this signals {signals} is a list, but used as single variable. path={state.path}")

            stores = [state.store]

        res = self.__proceed_format_dict(format_template, state, stores)
        if state.want_return == 'single':
            return res[0] if len(res) > 0 else {}
        else:
            return res


    def __format_list(self, template_list, state):
        def proceed_single_store(result, store):
            next_state = State(
                path=self.__next_path(state.path, str(idx)),
                search_deep=True,
                want_return='list',
                store=store,
            )
            v = self.__format(
                  template,
                  next_state
                  )
            if v is not None:
                if isinstance(v, list):
                    result += v
                else:
                    result.append(v)

        result = []
        for idx, template in enumerate(template_list):
            for child_store in state.store.children:
                proceed_single_store(result, child_store)

        # # if we are not able to find anthing, we maybe trying to transpose when there is nothing to transpose.
        # # Give a chance to get the data from the current store. Check test: `test_list_no_transposition` for why this is needed.
        if result == []:
            for idx, template in enumerate(template_list):
                proceed_single_store(result, state.store)

        return result

    def __format(self, template, state):
        # If Trans is defined without format, take the template from the Trans.
        # For MatchTrans, just take the template
        if isinstance(template, Trans) and not template.format or isinstance(template, MatchTrans):
            self.__debug(f"Found MatchTrans. Using inner template. path={state.path}")
            template = template.template

        if isinstance(template, S):
            value = state.store.get_signal_value(template, state.search_deep)
            self.__debug(f"Format value signal={template.key} value={value}, path={state.path}")
            if isinstance(value, list) and state.want_return == 'single':
                raise IncorrecTypeException(f"Incorrect type requested. Requested non list value, but list returned. signal={template} path={state.path}")
            return value

        elif isinstance(template, FormatTrans) or isinstance(template, Trans):
            self.__debug(f"Format FormatTrans. path={state.path}")
            next_state = State(path=state.path, store=state.store, want_return='single', search_deep=True)
            return template.transform(
                lambda sub_template: self.__format(sub_template, next_state),
                debug=self.debug_log,
                dir='format'
            )

        elif isinstance(template, dict):
            self.__debug(f"Format dict, path={state.path}")
            return self.__format_dict(template, state)

        elif isinstance(template, self.list_like):
            self.__debug(f"Format list, path={state.path}")
            return self.__format_list(template, state)
        else:
            self.__debug(f"Nothing to format type={type(template)}, path={state.path}")
            return template

    def format(self, template, debug=None, deepclean=False):
        state = State(
            path='root',
            search_deep=True,
            want_return='single',
            store=self.root_store,
        )
        if debug is not None:
            self.debug_log = debug
        template = copy.deepcopy(template)
        return self.__clean(self.__format(template, state), deepclean)

    @property
    def storage(self):
        return self.root_store.as_dict()

    def __str__(self):
        return str(self.matched)
