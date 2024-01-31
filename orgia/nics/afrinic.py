from .engine import Engine


class AFRINIC(Engine):
    DELAY = 0
    MAX_RESULTS_IN_A_SEARCH = 10000
    RDAP_URL = 'https://rdap.afrinic.net/rdap'
    ORG_QUERY = '/entities?fn={org_name}'

    def __init__(self, org_name: str, args):
        super().__init__()
        self.org_name = org_name
        self.args = args
        self._request_db = self.request_rdap
        self.config = self.args.config
