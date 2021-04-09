from pydash import _

def dict_join(x, on):
    '''
    Take a list of dictionary and join then on `on`
    '''
    def reducer(acc, value):
        el = _.find(acc, lambda x: x.get(on) == value.get(on))
        if el:
            for k,v in value.items():
                if v is not None:
                    el[k] = v
        else:
            acc.append(value)
        return acc

    return _.reduce(x, reducer, [])
