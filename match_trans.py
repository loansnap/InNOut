import logging

from . import S

logger = logging.getLogger('in_n_out')

class IncorrectMatchTypeException(Exception):
    def __init__(self):
        super().__init__(
            "MatchTrans first parameter must either be a dictionary `string -> S` or `S` type"
        )

class MatchTransException(Exception):
    pass

class MatchTrans():
    def __init__(self, template, func, strict=False, debug=False):
        if not isinstance(template, dict) and not isinstance(template, S):
            raise IncorrectMatchTypeException()

        if isinstance(template, dict):
            for key, value in template.items():
                if not isinstance(key, str) or not isinstance(value, S):
                    raise IncorrectMatchTypeException()

        self.template = template
        self.func = func
        self.strict = strict
        self.debug_log = debug

    def __debug(self, s):
        if self.debug_log:
            print(f"MatchTrans: {s}")
        logger.debug(s)

    def transform(self, data, store, debug=None, dir=None):
        if debug:
            self.debug_log = True

        try:
            self.__debug(f"Running transform function. function={self.func} template={self.template}, input data={data}")
            res = self.func(data)
            self.__debug(f"Successfully ran transform function. res={res}")
        except Exception as e:
            if self.strict:
                raise e
            else:
                logger.warning(f"Error in MatchTrans. function={self.func} template={self.template}, input data={data}")
                return

        if not isinstance(res, dict) and isinstance(self.template, dict):
            if self.strict:
                raise MatchTransException(f"Incorrect type returned. Expecting dict. function={self.func}, function_result={res} template={self.template}, input data={data}")
            else:
                logger.warning(f"Error in MatchTrans transform function. Incorrect type returned. Expecting dict. function={self.func}, function_result={res} template={self.template}, input data={data}")
                return

        if not isinstance(res, dict):
            store.add(self.template.key, res)
        else:
            for key, value in res.items():
                if key in self.template.keys():
                    store.add(self.template[key].key, value)
                else:
                    raise MatchTransException(f"Transform function returned unknown key '{key}'. function={self.func}, function_result={res} template={self.template}, input data={data}") # TODO: put error in commonError
