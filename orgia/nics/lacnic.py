from .engine import Engine


class LACNIC(Engine):
    DELAY = 0
    MAX_RESULTS_IN_A_SEARCH = 100
    RDAP_URL = 'https://rdap.lacnic.net/rdap'
    ORG_QUERY = '/entities?fn={org_name}'

    def __init__(self, org_name: str, args):
        super().__init__()
        self.org_name = org_name
        self.args = args
        self._request_db = self.request_rdap
        self.config = self.args.config
        