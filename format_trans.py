import logging

logger = logging.getLogger('in_n_out')

class FormatTrans():
    def __init__(self, template, func, strict=False, debug=False):
        self.template = template
        self.func = func
        self.strict = strict
        self.debug_log = debug

    def __debug(self, s):
        if self.debug_log:
            print(f"FormatTrans: {s}")
        logger.debug(s)

    def transform(self, get_sub_template, debug=None, dir=None):
        if debug:
            self.debug_log = True

        params = get_sub_template(self.template)

        self.__debug(f"Running transform function. function={self.func} template={self.template}, params={params}")
        try:
            result = self.func(params)
            self.__debug(f"Successfully ran transform function. result={result}, function={self.func} template={self.template}, params={params}")
            return result
        except Exception as e:
            if self.strict:
                raise e
            else:
                logger.warning(f"Error raised during transformation: error={e}, function={self.func} template={self.template}, params={params}")
                return
