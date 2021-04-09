import random
import unittest
from django.db.models.query import QuerySet

from pydash import _

from django.test import TestCase, testcases

# from apps.common.models import Application
# from apps.common.models.tests.utils import create_entire_mock_application

from . import match, format, transform, S, FormatTrans, MatchTrans, Trans, utils as RegUtils
from .match_trans import MatchTransException, IncorrectMatchTypeException
from .in_n_out import IncorrecTypeException


test_match_template = {
    'profile_list': [{
        'first_name': S('first_name'),
        'last_name': S('last_name'),
        'addresses': [{
            'street': S('street_address'),
            'postal_code': S('postal_code'),
            'street_crossing': [{
                'name': S('street_crossing_name')
            }]
        }]
    }]
}

test_data = {
    'profile_list': [{
        'first_name': 'Marc',
        'last_name': 'Simon',
        'addresses': [{
            'street': '123 main st',
            'postal_code': '12345',
            'street_crossing': [{
                'name': 'main'
            }, {
                'name': 'hide'
            }]
        }, {
            'street': '556 Sutter St',
            'postal_code': '94107',
            'street_crossing': [{
                'name': 'mission'
            }, {
                'name': '16th'
            }]
        }]
    }, {
        'first_name': 'Bryan',
        'last_name': 'Coloma',
        'addresses': [{
            'street': '123 pasadena st',
            'postal_code': '99401',
            'street_crossing': [{
                'name': 'pasadena'
            }, {
                'name': 'mcallister'
            }]
        }]
    }]
}

class TestStorage(unittest.TestCase):
    '''
    Store are created everytime there is a list_like element in the data.
    Each element of that list is its own store.

    This design allow us:
    - to couple signal together in list.
    - to gather all the sub signal available
    - to get parents signal into list.

    One test for each of these use case
    '''

    def setUp(self):
        self.match_template = test_match_template
        self.data = test_data
        self.matched = match(self.match_template, self.data)

    def test_storage(self):
        expected_store = {
            'values': {},  # First store is empty, as there is no signal on top level
            'depth': 0,
            'children': [{  # 2 children stores. One for each element of the data.profile_list
                'values': {  # 2 children stores. One for each element of the data.profile_list
                    'first_name': 'Marc',
                    'last_name': 'Simon'
                },
                'depth': 1,
                'children': [{  # 2 children stores. One for each element of the data.profile_list.0.addresses
                    'values': {
                        'street_address': '123 main st',
                        'postal_code': '12345'
                    },
                    'depth': 2,
                    'children': [{
                        'values': {
                            'street_crossing_name': 'main'
                        },
                        'depth': 3,
                        'children': []
                    }, {
                        'values': {
                            'street_crossing_name': 'hide'
                        },
                        'depth': 3,
                        'children': []
                    }]
                }, {
                    'values': {
                        'street_address': '556 Sutter St',
                        'postal_code': '94107'
                    },
                    'depth': 2,
                    'children': [{
                        'values': {
                            'street_crossing_name': 'mission'
                        },
                        'depth': 3,
                        'children': []
                    }, {
                        'values': {
                            'street_crossing_name': '16th'
                        },
                        'depth': 3,
                        'children': []
                    }]
                }]
            }, {
                'values': {
                    'first_name': 'Bryan',
                    'last_name': 'Coloma'
                },
                'depth': 1,
                'children': [{  # 1 child stores. One for each element of the data.profile_list.1.addresses
                    'values': {
                        'street_address': '123 pasadena st',
                        'postal_code': '99401'
                    },
                    'depth': 2,
                    'children': [{
                        'values': {
                            'street_crossing_name': 'pasadena'
                        },
                        'depth': 3,
                        'children': []
                    }, {
                        'values': {
                            'street_crossing_name': 'mcallister'
                        },
                        'depth': 3,
                        'children': []
                    }]
                }]
            }]
        }
        self.assertEqual(self.matched.storage, expected_store)

    def test_get_deepest_store_for_signals_deepest(self):
        # should return only the store holding the street_crossing_name
        stores = self.matched.root_store.get_deepest_stores_for_signals([
            S('street_crossing_name'),
            S('first_name'),
            S('street_address'),
        ])

        for store in stores:
            self.assertTrue('street_crossing_name' in store.values)
        self.assertEqual(len(stores), 6)


    def test_get_deepest_store_for_signals_mid_depth(self):
        # Should returns the 3 stores with street_address
        stores = self.matched.root_store.get_deepest_stores_for_signals([
            S('first_name'),
            S('street_address'),
        ])

        for store in stores:
            self.assertTrue('street_address' in store.values)
        self.assertEqual(len(stores), 3)


    def test_get_deepest_store_for_signals_first_depth(self):
        # Should returns the 2 stores with first_name
        stores = self.matched.root_store.get_deepest_stores_for_signals([
            S('first_name'),
        ])

        for store in stores:
            self.assertTrue('first_name' in store.values)
        self.assertEqual(len(stores), 2)


    def test_get_deepest_store_for_signals_mix_depth(self):
        # Testing if looking for signals that are not always present
        data = {
            'profile_list': [{
                'first_name': 'Marc',
                'last_name': 'Simon',
                'addresses': [{
                    'street': '123 main st',
                    'postal_code': '12345',
                    'street_crossing': [{
                        'name': 'main' # 1 stops here
                    }, {
                        'name': 'hide' # 1 stops here
                    }]
                }, {
                    'street': '556 Sutter St', # 1 stops here
                    'postal_code': '94107',
                }]
            }, {
                'first_name': 'Bryan', # 1 stops here
                'last_name': 'Coloma',
            }]
        }

        m = match(self.match_template, data)

        stores = m.root_store.get_deepest_stores_for_signals([
            S('street_crossing_name'),
            S('first_name'),
            S('street_address'),
        ])

        def reducer(acc, store):
            if 'street_crossing_name' in store.values:
                acc['street_crossing_name'] = _.get(acc, 'street_crossing_name', 0) + 1
            elif 'first_name' in store.values:
                acc['first_name'] = _.get(acc, 'first_name', 0) + 1
            elif 'street_address' in store.values:
                acc['street_address'] = _.get(acc, 'street_address', 0) + 1

            return acc

        occurences = _.reduce(stores, reducer, {})
        self.assertEqual(occurences, {
            'street_crossing_name': 2,
            'first_name': 1,
            'street_address': 1,
        })

class TestError(unittest.TestCase):
    def setUp(self):
        self.match_template = test_match_template
        self.data = test_data
        self.matched = match(self.match_template, self.data)

    def test_ask_single_get_list(self):
        template = S('postal_code')

        with self.assertRaises(IncorrecTypeException):
            self.matched.format(template)


    def test_ask_single_dict_get_list(self):
        template = {
            'postal_code': S('postal_code'),
            'street_crossing_name': S('street_crossing_name')
        }

        with self.assertRaises(IncorrecTypeException):
            self.matched.format(template)


class TestTransposition(unittest.TestCase):
    '''
    The goal of transposition is to allow to bring together values that are store in different depths in one dictionary
    '''
    def setUp(self):
        self.match_template = test_match_template
        self.data = test_data
        self.matched = match(self.match_template, self.data)


    def test_transpose_street_crossing_name(self):
        '''
        In this case, we want to get all the crossing name in a dict, with their post_code & profile
        There is several postal code for a profile and several street_crossing for an address
        '''
        template = [{  # Asking for a list, as we are going to transpose
            'first_names': S('first_name'),
            'postal_code': S('postal_code'),
            'street_crossing_name': S('street_crossing_name')
        }]
        res = self.matched.format(template)
        expected = [{
            'first_names': 'Marc',
            'postal_code': '12345',
            'street_crossing_name': 'main'
        }, {
            'first_names': 'Marc',
            'postal_code': '12345',
            'street_crossing_name': 'hide'
        }, {
            'first_names': 'Marc',
            'postal_code': '94107',
            'street_crossing_name': 'mission'
        }, {
            'first_names': 'Marc',
            'postal_code': '94107',
            'street_crossing_name': '16th'
        }, {
            'first_names': 'Bryan',
            'postal_code': '99401',
            'street_crossing_name': 'pasadena'
        }, {
            'first_names': 'Bryan',
            'postal_code': '99401',
            'street_crossing_name': 'mcallister'
        }]

        self.assertEqual(res, expected)


    def test_transpose_street_name_acc_crossing(self):
        '''
        In this case, we want to get all the street_address & postal_code in a dict, with their profile
        But we also want to get as a list the street_crossing_name
        '''
        template = [{  # Asking for a list, as we are going to transpose
            'first_names': S('first_name'),
            'street_address': S('street_address'),
            'postal_code': S('postal_code'),
            'street_crossing_name': [S('street_crossing_name')]  # Asking to return street_crossing_name as list. Hence no transposition here.
        }]
        res = self.matched.format(template)

        expected = [{
            'first_names': 'Marc',
            'street_address': '123 main st',
            'postal_code': '12345',
            'street_crossing_name': ['main', 'hide']
        }, {
            'first_names': 'Marc',
            'street_address': '556 Sutter St',
            'postal_code': '94107',
            'street_crossing_name': ['mission', '16th']
        }, {
            'first_names': 'Bryan',
            'street_address': '123 pasadena st',
            'postal_code': '99401',
            'street_crossing_name': ['pasadena', 'mcallister']
        }]
        self.assertEqual(res, expected)


    def test_inner_transpose(self):
        template = [{  # Asking for a list, as we are going to transpose
            'first_names': S('first_name'),
            'address': [{
                'street_address': S('street_address'),
                'postal_code': S('postal_code'),
                'street_crossing_name': S('street_crossing_name')  # Asking for transposition, but only on street address. Not first-name
            }]
        }]
        res = self.matched.format(template)
        expected = [{
            'first_names': 'Marc',
            'address': [{
                'street_address': '123 main st',
                'postal_code': '12345',
                'street_crossing_name': 'main'
            }, {
                'street_address': '123 main st',
                'postal_code': '12345',
                'street_crossing_name': 'hide'
            }, {
                'street_address': '556 Sutter St',
                'postal_code': '94107',
                'street_crossing_name': 'mission'
            }, {
                'street_address': '556 Sutter St',
                'postal_code': '94107',
                'street_crossing_name': '16th'
            }]
        }, {
            'first_names': 'Bryan',
            'address': [{
                'street_address': '123 pasadena st',
                'postal_code': '99401',
                'street_crossing_name': 'pasadena'
            }, {
                'street_address': '123 pasadena st',
                'postal_code': '99401',
                'street_crossing_name': 'mcallister'
            }]
        }]
        self.assertEqual(res, expected)

    def test_several_transposition_with_list(self):
        '''
        Both profile & street are being transposed but they aren't link.
        The only data we're transposing on is data_id.
        '''
        data = {
            'data_id': 123,
            'profiles': [{
                'first_name': 'Marc',
                'last_name': 'Simon',
            }, {
                'first_name': 'Bryan',
                'last_name': 'Coloma',
            }],
            'addresses': [{
                'street': 'mcAllister',
            }, {
                'street': 'market',
            }]
        }
        match_template = {
            'data_id': S('data_id'),
            'profiles': [{
                'first_name': S('fist_name'),
                'last_name': S('last_name'),
            }],
            'addresses': [{
                'street': S('street')
            }]
        }
        format_template = [{
            'data_id': S('data_id'),
            'profile': {
                'first_name': S('fist_name'),
                'last_name': S('last_name'),
            },
            'street': S('street')
        }]

        res = transform(data, match_template, format_template)

        expected = [{
            'data_id': 123,
            'profile': {
                'first_name': 'Marc',
                'last_name': 'Simon'
            }
        }, {
            'data_id': 123,
            'profile': {
                'first_name': 'Bryan',
                'last_name': 'Coloma'
            }
        }, {
            'data_id': 123,
            'street': 'mcAllister',
            'profile': {
            },
        }, {
            'data_id': 123,
            'street': 'market',
            'profile': {
            },
        }]

        self.assertEqual(res, expected)

    def test_transposition_with_list_acc(self):
        '''
        Street is being transposed, while profile is accumulated into a list. Profile & List arent' related
        Since there isn't any profile for each street, no profile info is returns
        '''
        data = {
            'data_id': 123,
            'profiles': [{
                'first_name': 'Marc',
                'last_name': 'Simon',
            }, {
                'first_name': 'Bryan',
                'last_name': 'Coloma',
            }],
            'addresses': [{
                'street': 'mcAllister',
            }, {
                'street': 'market',
            }]
        }

        match_template = {
            'data_id': S('data_id'),
            'profiles': [{
                'first_name': S('fist_name'),
                'last_name': S('last_name'),
            }],
            'addresses': [{
                'street': S('street'),
            }]
        }

        format_template = [{
            'data_id': S('data_id'),
            'profile': {
                'fist_name': [S('fist_name')],
                'last_name': [S('last_name')],
            },
            'street': S('street')
        }]

        res = transform(data, match_template, format_template)

        expected = [{
            'data_id': 123,
            'profile': {
                'fist_name': [],
                'last_name': []
            },
            'street': 'mcAllister',
        }, {
            'data_id': 123,
            'profile': {
                'fist_name': [],
                'last_name': []
            },
            'street': 'market',
        }]

        self.assertEqual(res, expected)


    def test_list_no_transposition(self):
        '''
        In that test, we're taking single element from our storage (first_name, last_name, address)
        We're not transposing any data from children store.
        '''
        data = {
            'first_name': 'Marc',
            'last_name': 'Simon',
            'address': '2687 mcAllister st',
            'otot': [{
                'abc': 'abc1',
                'tot': 'tot'
            }, {
                'efg': 'efg',
            }],
            'lol': [{
                'qw': 'qw1',
            }, {
                'qw': 'qw2',
            }]
        }

        match_template = {
            'first_name': S('first_name'),
            'last_name': S('last_name'),
            'address': S('address'),
            'otot': [{
                'abc': S('abc'),
                'tot': S('tot')
            }],
            'lol': [{
                'qw': S('qw')
            }]
        }

        format_template = {
            'info': [{
                'info_type': 'user_info',
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }, {
                'info_type': 'address',
                'address': FormatTrans(S('address'), lambda x: x == 'Y')
            }]
        }

        res = transform(data, match_template, format_template)
        expected = {
            'info': [{
                'info_type': 'user_info',
                'first_name': 'Marc',
                'last_name': 'Simon'
            }, {
                'info_type': 'address',
                'address': False
            }]
        }
        self.assertEqual(res, expected)


class TestListAccumulation(unittest.TestCase):
    def setUp(self):
        self.match_template = test_match_template
        self.data = test_data
        self.matched = match(self.match_template, self.data)


    def test_list_accumulation(self):
        '''
        Goal of list accumulation is to gather all the signals into a list of values, independtly of their depth
        '''
        template = {
            'first_names': [S('first_name')],
            'streets': [S('street_address')],
            'postal_code': [S('postal_code')],
            'street_crossing_name': [S('street_crossing_name')],
        }
        expected = {
            'first_names': ['Marc', 'Bryan'],
            'streets': ['123 main st', '556 Sutter St', '123 pasadena st'],
            'postal_code': ['12345', '94107', '99401'],
            'street_crossing_name': ['main', 'hide', 'mission', '16th', 'pasadena', 'mcallister']
        }
        res = self.matched.format(template)
        self.assertEqual(res, expected)


    def test_list_dict_accumulation(self):
        template = {
            'profiles': [{
                'first_names': S('first_name'),
                'last_name': S('last_name'),
            }],
            'addresses': [{
                'street': S('street_address'),
                'postal_code': S('postal_code'),
            }],
            'crossing': [{
                'street_crossing_name': S('street_crossing_name')
            }],
        }
        expected = {
            'profiles': [{
                'first_names': 'Marc',
                'last_name': 'Simon'
            }, {
                'first_names': 'Bryan',
                'last_name': 'Coloma'
            }],
            'addresses': [{
                'street': '123 main st',
                'postal_code': '12345'
            }, {
                'street': '556 Sutter St',
                'postal_code': '94107'
            }, {
                'street': '123 pasadena st',
                'postal_code': '99401'
            }],
            'crossing': [{
                'street_crossing_name': 'main'
            }, {
                'street_crossing_name': 'hide'
            }, {
                'street_crossing_name': 'mission'
            }, {
                'street_crossing_name': '16th'
            }, {
                'street_crossing_name': 'pasadena'
            }, {
                'street_crossing_name': 'mcallister'
            }]
        }
        res = self.matched.format(template)
        self.assertEqual(res, expected)


class TestTransformation(unittest.TestCase):
    def setUp(self):
        self.match_template = test_match_template
        self.data = test_data
        self.matched = match(self.match_template, self.data)

    def test_simple_match_transformation(self):
        match_template = {
            'first_name': MatchTrans(S('first_name'), lambda x: 'First Name is ' + x),
            'last_name': MatchTrans(S('last_name'), lambda x: 'Last Name is ' + x)
        }

        data = {
            'first_name': 'Marc',
            'last_name': 'Simon',
        }

        format_template = {
            'first_name': S('first_name'),
            'last_name': S('last_name'),
        }

        res = transform(data, match_template, format_template)
        self.assertEqual(res, {
            'first_name': 'First Name is Marc',
            'last_name': 'Last Name is Simon'
        })

    def test_list_match_transformation(self):
        '''
        List transformation are not allowed in MatchTrans.
        Should raise error
        '''

        with self.assertRaises(IncorrectMatchTypeException) as e:
            {
                'profile_list': MatchTrans([{
                    'first_name': S('first_name'),
                    'last_name': S('last_name'),
                    'addresses': [{
                        'street': S('street_address'),
                        'postal_code': S('postal_code'),
                        'street_crossing': [{
                            'name': S('street_crossing_name')
                        }]
                    }]
                }], lambda x: x)
            }


    def test_dict_match_transformation(self):
        def split_names(name):
            v = name.split(' ')
            return {
                'first_name': v[0],
                'last_name': v[1],
            }

        match_template = {
            'profile_list': [{
                'name': MatchTrans({
                    'first_name': S('first_name'),
                    'last_name': S('last_name'),
                }, split_names)
            }]
        }

        data = {
            'profile_list': [{
                'name': 'Marc Simon'
            }, {
                'name': 'Bryan Coloma'
            }]
        }

        format_template = {
            'profiles': [{
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }]
        }

        res = transform(data, match_template, format_template)
        expected = {
            'profiles': [{
                'first_name': 'Marc',
                'last_name': 'Simon'
            }, {
                'first_name': 'Bryan',
                'last_name': 'Coloma'
            }]
        }
        self.assertEqual(res, expected)


    def test_simple_format_transformation(self):
        template = {
            'profiles': [{
                'first_name': FormatTrans(S('first_name'), lambda x: 'First Name is ' + x),
                'last_name': FormatTrans(S('last_name'), lambda x: 'Last Name is ' + x)
            }]
        }

        res = self.matched.format(template)
        expected = {
            'profiles': [{
                'first_name': 'First Name is Marc',
                'last_name': 'Last Name is Simon'
            }, {
                'first_name': 'First Name is Bryan',
                'last_name': 'Last Name is Coloma'
            }]
        }
        self.assertEqual(res, expected)


    def test_list_format_transformation(self):
        def replace_names(profile):
            profile['first_name'] = 'First Name is ' + profile['first_name']
            profile['last_name'] = 'Last Name is ' + profile['last_name']
            return profile

        template = {
            'profiles': FormatTrans([{
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }], lambda x: _.map(x, replace_names))
        }

        res = self.matched.format(template)
        expected = {
            'profiles': [{
                'first_name': 'First Name is Marc',
                'last_name': 'Last Name is Simon'
            }, {
                'first_name': 'First Name is Bryan',
                'last_name': 'Last Name is Coloma'
            }]
        }
        self.assertEqual(res, expected)


    def test_dict_format_transformation(self):
        def replace_names(profile):
            profile['first_name'] = 'First Name is ' + profile['first_name']
            profile['last_name'] = 'Last Name is ' + profile['last_name']
            return profile

        template = {
            'profiles': [
                FormatTrans({
                    'first_name': S('first_name'),
                    'last_name': S('last_name'),
                }, replace_names)
            ]
        }

        res = self.matched.format(template)
        expected = {
            'profiles': [{
                'first_name': 'First Name is Marc',
                'last_name': 'Last Name is Simon'
            }, {
                'first_name': 'First Name is Bryan',
                'last_name': 'Last Name is Coloma'
            }]
        }
        self.assertEqual(res, expected)


    def test_multiple_template_transformation(self):
        '''
        Emulating the encompass_to_mismo_format_template income format
        '''
        match_template = {
            'employment': [{
                'basePayAmount': S('base_pay_amount'),
                'commissions': S('commissions_amount'),
                'overtimeAmount': S('overtime_amount'),
                'otherAmount': S('other_amount'),
            }],
            'other_incomes': [{
                'income_type': S('other_income_type'),
                'amount': S('other_income_amounts')
            }]
        }

        data = {
            'employment': [{
                'basePayAmount': 100,
                'commissions': 200,
                'overtimeAmount': 300,
                'otherAmount': 400,
            }, {
                'basePayAmount': 1,
                'commissions': 2,
                'otherAmount': 0,
            }],
            'other_incomes': [{
                'income_type': 'alimony',
                'amount': 123,
            }, {
                'income_type': 'alimony',
                'amount': 321,
            }, {
                'income_type': 'royalties',
                'amount': 10,
            }, {
                'income_type': 'others',
                'amount': 30,
            }]
        }


        def sum_same_other_income_types(incomes):
            income_type_key = 'income_type'
            monthly_amount_key = 'amount'
            def reducer(acc, income):
                key = income.get(income_type_key)
                value = income.get(monthly_amount_key)

                if not key or not value:
                    return acc

                try:
                    value = float(value)
                except ValueError:
                    return acc

                if not acc.get(key):
                    acc[key] = income
                else:
                    acc[key][monthly_amount_key] += value
                return acc

            result = _.reduce(incomes, reducer, {}).values()
            return list(result) or []


        def filter_empty_income(incomes):
            employer_incomes = incomes.get('employer_incomes')
            other_incomes = incomes.get('other_incomes')
            employer_incomes = _.filter(employer_incomes, lambda x: x.get('amount', None))
            other_incomes = _.filter(other_incomes, lambda x: x.get('amount', None))

            return employer_incomes + other_incomes

        format_template = FormatTrans({
            'employer_incomes': [{
                'income_type': 'Base',
                'amount': S('base_pay_amount'),
            }, {
                'income_type': 'Commision',
                'amount': S('commissions_amount'),
            }, {
                'income_type': 'Overtime',
                'amount': S('overtime_amount')
            }, {
                'income_type': 'Other',
                'amount': S('other_amount')
            }],
            'other_incomes': FormatTrans([{
                'income_type': FormatTrans(S('other_income_type'), lambda x: { 'royalties': 'others' }.get(x) or x),
                'amount': S('other_income_amounts')
            }], sum_same_other_income_types)
        }, filter_empty_income)

        res = transform(data, match_template, format_template)
        expected = [{
            'income_type': 'Base',
            'amount': 100
        }, {
            'income_type': 'Base',
            'amount': 1
        }, {
            'income_type': 'Commision',
            'amount': 200
        }, {
            'income_type': 'Commision',
            'amount': 2
        }, {
            'income_type': 'Overtime',
            'amount': 300
        }, {
            'income_type': 'Other',
            'amount': 400
        }, {
            'income_type': 'alimony',
            'amount': 444.0
        }, {
            'income_type': 'others',
            'amount': 40.0
        }]

        self.assertEqual(res, expected)


    def test_mix_trans(self):
        '''
        During the match transformation, change first_name to lowercase and assigned it to first_name signal
        During the format tranformation, add `First name is` as prefix to name.
        Same for last_name with upper transformation.
        '''
        template = {
            'profiles': [{
                'first_name': Trans(S('first_name'), format=lambda x: "First name is " + x, match=lambda x: x.lower() if x else None),
                'last_name': Trans(S('last_name'), format=lambda x: "Last name is " + x, match=lambda x: x.upper() if x else None),
            }]
        }

        data = {
            'profiles': [{
                'first_name': 'Marc',
                'last_name': 'Simon',
            }, {
                'first_name': 'Brian',
                'last_name': 'Coloma',
            }]
        }

        res = transform(data, template, template)
        expected = {
            'profiles': [{
                'first_name': 'First name is marc',
                'last_name': 'Last name is SIMON'
            }, {
                'first_name': 'First name is brian',
                'last_name': 'Last name is COLOMA'
            }]
        }
        self.assertEqual(res, expected)


    def test_list_trans_empty(self):
        data = {
            'profile': {
                'street_addr': 'Hide st',
            }
        }

        match_template = {
            'profile': {
                'first_name': S('first_name'),
                'last_name': S('last_name'),
                'street_addr': S('street_addr')
            }
        }

        format_template = {
            'name': Trans({
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }, lambda x: (x.get('first_name') or '') + '-' + (x.get('last_name') or ''))
        }

        res = transform(data, match_template, format_template)
        self.assertEqual(res, { 'name': '-'})




class TestFull(unittest.TestCase):
    def test_single_match(self):
        data = {'name': 'john'}
        template = {'name': S('name')}

        m = match(template, data)
        result = format(template, m)
        self.assertEqual(result, data)


    def test_two_matches(self):
        data = [{'name': 'john'}, {'name': 'abe'}]
        template = [{'name': S('name')}]

        m = match(template, data)
        result = format(template, m)
        self.assertEqual(result, data)


    def test_filter_match(self):
        match_template = {
            'profiles': [{
                'username': S('username'),
                'permissions': [S('permissions')],
                'role': 'admin'
            }, {
                'username': S('username'),
                'user_id': S('user_id'),
                'role': 'user'
            }],
        }

        format_template = [{
            'username': S('username'),
            'permissions': [S('permissions')],
            'user_id': S('user_id')
        }]


        data = {
            'profiles': [{
                'username': 'marc',
                'permissions': [
                    'access_1',
                    'access_2',
                ],
                'role': 'admin',
                'user_id': 'marc_1234'
            }, {
                'username': 'bryan',
                'permissions': [
                    'user_access_1',
                    'user_access_2',
                ],
                'role': 'user',
                'user_id': 'bryan_1234'
            }]
        }

        result = transform(data, match_template, format_template)
        self.assertEqual(result, [
            {
                "username": "marc",
                "permissions": [
                    "access_1",
                    "access_2"
                ]
            },
            {
                "username": "bryan",
                'permissions': [],
                "user_id": "bryan_1234"
            }
        ])


    def test_list_depth(self):
        data = [{
            'name': 'john',
            'addresses': [{
                'state': 'CA'
            }, {
                'state': 'CT'
            }]
        }, {
            'name': 'allan',
            'addresses': [{
                'state': 'CA'
            }, {
                'state': 'WA'
            }]
        }]

        match_template = [{
            'name': S('name'),
            'addresses': [{'state': S('state')}]
        }]
        m = match(match_template, data)

        format_template = {
            'names': [S('name')],
            'states': [S('state')]
        }

        expected = {
            "names": [
                "john",
                "allan"
            ],
            "states": [
                "CA",
                "CT",
                "CA",
                "WA"
            ]
        }
        result = format(format_template, m)
        self.assertEqual(result, expected)


    def test_list_depth2(self):
        data = [{
            'name': 'john',
            'addresses': [{
                'state': 'CA'
            }, {
                'state': 'CT'
            }]
        }, {
            'name': 'allan',
            'addresses': [{
                'state': 'CA'
            }, {
                'state': 'WA'
            }]
        }]

        match_template = [{
            'name': S('name'),
            'addresses': [{'state': S('state')}]
        }]
        m = match(match_template, data)

        format_template = [{
            'names': S('name'),
            'states': [S('state')]
        }]

        expected = [
            {
                "names": "john",
                "states": [
                    "CA",
                    "CT"
                ]
            },
            {
                "names": "allan",
                "states": [
                    "CA",
                    "WA"
                ]
            }
        ]

        result = format(format_template, m)
        self.assertEqual(result, expected)


    def test_cartesian_product(self):
        data = {
            'u': [random.random() for i in range(1000)],
            'v': [random.random() for i in range(1000)],
            'w': [random.random() for i in range(1000)],
            'x': [random.random() for i in range(1000)],
            'y': [random.random() for i in range(1000)],
            'z': [random.random() for i in range(1000)]
        }

        template = {
            'u': [S('u')],
            'v': [S('v')],
            'w': [S('w')],
            'x': [S('x')],
            'y': [S('y')],
            'z': [S('z')],
        }

        result = transform(data, template, template)
        self.assertEqual(result, data)

    def test_transformation(self):
        data = {'state': 'California'}
        template = {
            'state': Trans(
                S('state'),
                lambda x: {'CA': 'California'}.get(x),
                lambda x: {'California': 'CA'}.get(x),
            )
        }
        result = transform(data, template, template)
        self.assertEqual(result, data)


    def test_transformation_2(self):
        data = {
            'yrs': 12.5
        }
        parse_template = {
            'yrs': S('yrs')
        }
        format_template = {
            'residency': Trans(S('yrs'), int)
        }

        m = match(parse_template, data)
        result = format(format_template, m)
        self.assertEqual(result, {'residency': 12})


    def test_join(self):
        data = {
            'names': [{
                'ssn': 123456789,
                'name': 'mario'
            }, {
                'ssn': 987654321,
                'name': 'luigi'
            }],
            'hats': [{
                'ssn': 123456789,
                'hat_color': 'red'
            }, {
                'ssn': 987654321,
                'hat_color': 'green'
            }]
        }
        match_template = {
            'names': [{
                'ssn': S('ssn'),
                'name': S('name')
            }],
            'hats': [{
                'ssn': S('ssn'),
                'hat_color': S('color')
            }]
        }

        format_template = Trans([{
            'name': S('name'),
            'ssn': S('ssn'),
            'color': S('color')
        }], lambda x: RegUtils.dict_join(x, 'ssn'))

        expected = [{
            'name': 'mario',
            'ssn': 123456789,
            'color': 'red'
        },
            {
            'name': 'luigi',
            'ssn': 987654321,
            'color': 'green'
        }]

        result = transform(data, match_template, format_template)
        self.assertEqual(result, expected)


    def test_multiple_sub_template(self):
        '''
        Emulating the encompass_to_mismo_format_template income format
        '''
        match_template = {
            'employment': [{
                'basePayAmount': S('base_pay_amount'),
                'commissions': S('commissions_amount'),
                'overtimeAmount': S('overtime_amount'),
                'otherAmount': S('other_amount'),
            }],
            'other_incomes': [{
                'income_type': S('other_income_type'),
                'amount': S('other_income_amounts')
            }]
        }

        data = {
            'employment': [{
                'basePayAmount': 100,
                'commissions': 200,
                'overtimeAmount': 300,
                'otherAmount': 400,
            }, {
                'basePayAmount': 1,
                'commissions': 2,
            }]
        }

        format_template = {
            'employer_incomes': [{
                'income_type': 'Base',
                'amount': S('base_pay_amount'),
            }, {
                'income_type': 'Commision',
                'amount': S('commissions_amount'),
            }, {
                'income_type': 'Overtime',
                'amount': S('overtime_amount')
            }, {
                'income_type': 'Other',
                'amount': S('other_amount')
            }]
        }

        res = transform(data, match_template, format_template)
        expected = {
            'employer_incomes': [{
                'income_type': 'Base',
                'amount': 100
            }, {
                'income_type': 'Base',
                'amount': 1
            }, {
                'income_type': 'Commision',
                'amount': 200
            }, {
                'income_type': 'Commision',
                'amount': 2
            }, {
                'income_type': 'Overtime',
                'amount': 300
            }, {
                'income_type': 'Other',
                'amount': 400
            }]
        }
        self.assertEqual(res, expected)

# class TestObject(TestCase):
#     def test_match_object(self):
#         match_template = {
#             'profile': {
#                 'user': {
#                     'id': S('user_id'),
#                 },
#                 'is_ssn_validated': S('profile_ssn_validated'),
#                 'get_fico': S('profile_fico') # get_fico is a function
#             },
#             'urla_form_type': S('urla_form_type')
#         }

#         template = {
#             'user_id': S('user_id'),
#             'is_ssn_validated': S('profile_ssn_validated'),
#             'fico': S('profile_fico'),
#             'urla_form_type': S('urla_form_type')
#         }

#         application = create_entire_mock_application()
#         res = transform(application, match_template, template)
#         self.assertEqual(res, {
#             'user_id': 'MEYWKYJTGEZGIZLE',
#             'is_ssn_validated': False,
#             'fico': 750,
#             'urla_form_type': '2009'
#         })

#     def test_query_set(self):
#         expected = []
#         for i in range(5):
#             app = create_entire_mock_application(fixed_data=False)
#             fico = app.profile.recent_credit_report.fico
#             app.profile.recent_credit_report.update(fico=fico + i)
#             expected.append({
#                 'id': app.id,
#                 'fico': app.profile.get_fico()
#             })

#         match_template = [{
#             'id': S('application_id'),
#             'profile': {
#                 'get_fico': S('profile_fico') # get_fico is a function
#             },
#         }]

#         template = [{
#             'id': S('application_id'),
#             'fico': S('profile_fico'),
#         }]

#         apps = Application.objects.all()

#         self.assertEqual(type(apps), QuerySet)
#         res = transform(apps, match_template, template)

#         self.assertEqual(res, expected)

#     def test_related_manager(self):
#         app = create_entire_mock_application(fixed_data=False)
#         profile = app.profile

#         expected = [app.id]
#         for i in range(4):
#             app = create_entire_mock_application(fixed_data=False)
#             app.update(profile = profile)
#             expected.append(app.id)

#         match_template = {
#             'id': S('id'),
#             'applications': [{
#                 'id': S('application_id'),
#                 'last_target_dti': S('last_target_dti'),
#             }]
#         }

#         format_template = [S('application_id')]

#         res = transform(profile, match_template, format_template)
#         self.assertEqual(res, expected)


class TestXmlToDictSpecific(TestCase):

    def test_match_single_when_list(self):
        '''
        Handle the case where the match template is incorrectly assuming there is only one value, while the data is a list.
        That often happen when using xmltodict with a incomplete xml example.
        Warning is displayed and optimaly it should be fix
        '''
        match_template = {
            'profile': {
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }
        }

        data = {
            'profile': [{
                'first_name': 'Marc',
                'last_name': 'Simon',
            }, {
                'first_name': 'Bryan',
                'last_name': 'Coloma',
            }]
        }

        template = {
            'first_name': S('first_name'),
            'last_name': S('last_name'),
        }

        res = transform(data, match_template, template)
        expected = {
            'first_name': 'Marc',
            'last_name': 'Simon'
        }
        self.assertEqual(res, expected)


    def test_match_list_when_single(self):
        '''
        Handle the case where the match template is asking for a list, while the data is a single element.
        This often happen with xmltodict, but isn't an issue
        '''
        match_template = {
            'profile': [{
                'first_name': S('first_name'),
                'last_name': S('last_name'),
            }]
        }

        data = {
            'profile': {
                'first_name': 'Marc',
                'last_name': 'Simon',
            }
        }

        template = [{
            'first_name': S('first_name'),
            'last_name': S('last_name'),
        }]

        res = transform(data, match_template, template)
        expected = [{
            'first_name': 'Marc',
            'last_name': 'Simon'
        }]
        self.assertEqual(res, expected)
