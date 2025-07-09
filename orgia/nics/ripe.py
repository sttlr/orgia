from urllib.parse import quote_plus
from .engine import Engine


class RIPE(Engine):
    DELAY = 0
    RESULTS_PER_PAGE = 1000
    DB_URL = f'https://apps.db.ripe.net/db-web-ui/api/rest/fulltextsearch/select?facet=false&format=xml&hl=true&wt=json&rows={RESULTS_PER_PAGE}'
    ORG_QUERY = '(organisation:("{org_name}") OR descr:("{org_name}") OR e-mail:("{org_name}") OR org-name:("{org_name}") OR remarks:("{org_name}")) AND (object-type:organisation)'
    INET_QUERY = '(descr:("{org_name}") OR netname:("{org_name}") OR remarks:("{org_name}")) AND (object-type:inetnum)'
    INET6_QUERY = '(descr:("{org_name}") OR netname:("{org_name}") OR remarks:("{org_name}")) AND (object-type:inet6num)'
    ASN_QUERY = '(descr:("{org_name}") OR as-name:("{org_name}") OR remarks:("{org_name}")) AND (object-type:aut-num)'
    RDAP_URL = 'https://rdap.db.ripe.net'

    def __init__(self, org_name: str, args):
        super().__init__()
        self.org_name = org_name
        self.args = args
        self.config = self.args.config

    def _request_db(self, query: str, page_num: int=0) -> dict:
        url = f'{self.DB_URL}&q={quote_plus(query)}&start={page_num * self.RESULTS_PER_PAGE}'
        r = self._http_request(url, headers={'Accept': 'application/json'})
        return r.json()

    def _search_db_and_get_all_pages(self, query: str) -> list:
        query = query.format(org_name=self.org_name)
        if self.args.country:
            query += f' AND (country:("{self.args.country}"))'
        
        pages = [self._request_db(query)]

        num_pages = (pages[0]['result']['numFound'] // self.RESULTS_PER_PAGE) + 1
        for page_num in range(1, num_pages):
            pages.append(self._request_db(query, page_num))
        return pages
    
    def _extract_lookup_keys_from_pages(self, pages: list) -> list:
        return [
            str['str']['value']
            for p in [
                p for p in pages
                if 'docs' in p['result'].keys()
            ]
            for doc in p['result']['docs']
            for str in doc['doc']['strs']
            if str['str']['name'] == 'lookup-key'
        ]

    def _find_asn_handles(self) -> list[str]:
        return self._extract_lookup_keys_from_pages(
            self._search_db_and_get_all_pages(self.ASN_QUERY)
        )
    
    def _find_network_handles(self):
        if self.args.ip4_only:
            return self._extract_lookup_keys_from_pages(
                self._search_db_and_get_all_pages(self.INET_QUERY)
            )
        else:
            return self._extract_lookup_keys_from_pages(
                [*self._search_db_and_get_all_pages(self.INET_QUERY),
                 *self._search_db_and_get_all_pages(self.INET6_QUERY)]
            )
    
