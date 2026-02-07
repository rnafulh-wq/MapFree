class BaseEngine:

    def feature_extraction(self, ctx):
        raise NotImplementedError

    def matching(self, ctx):
        raise NotImplementedError

    def sparse(self, ctx):
        raise NotImplementedError

    def dense(self, ctx):
        raise NotImplementedError
