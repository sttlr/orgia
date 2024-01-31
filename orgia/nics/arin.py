from urllib.parse import quote_plus
from bs4 import BeautifulSoup, SoupStrainer
from .engine import Engine
from traceback import print_exc


class ARIN(Engine):
    DELAY = 0.1
    MAX_RESULTS_IN_A_SEARCH = 256
    DB_URL = 'https://whois.arin.net/ui/query.do?advanced=true'
    ORG_QUERY = '&r=ORGANIZATION&ORGANIZATION=handle&ORGANIZATION=name&q={org_name}'
    INET_QUERY = '&r=NETWORK&NETWORK=handle&NETWORK=name&q={org_name}'
    ASN_QUERY = '&r=ASN&ASN=handle&ASN=name&q={org_name}'
    RDAP_URL = 'https://rdap.arin.net/registry'

    def __init__(self, org_name: str, args):
        super().__init__()
        self.org_name = org_name
        self.args = args
        self.config = self.args.config

    def _request_db(self, query: str) -> str:
        url = self.DB_URL + query.split('&q=')[0] + '&q=' + quote_plus(query.split('&q=')[1])
        r = self._http_request(url, headers={'Accept': 'text/html'})
        if not r:
            return None
        return r.text
    
    def _get_network_cidr_from_handle(self, network_handle: str):
        try:
            r = self._http_request(f'https://whois.arin.net/rest/net/{network_handle}')
        except Exception:
            if self.args.debug:
                print_exc()
            return None
        soup = BeautifulSoup(r.text, 'xml')
        return soup.find('startAddress').text.strip() + '/' + soup.find('cidrLength').text.strip()

    def _extract_lookup_keys_from_pages(self, pages: list) -> tuple:
        lookup_keys = set()
        parse_only = SoupStrainer('div', {'id': 'maincontent'})

        for p in pages:
            soup = BeautifulSoup(p, 'lxml', parse_only=parse_only)
            found_keys = [a.text for a in soup.select('table > tr > td:nth-child(1) > a')]
            # if len(found_keys) >= self.MAX_RESULTS_IN_A_SEARCH:
            #     print('MORE THAN', self.MAX_RESULTS_IN_A_SEARCH)
            lookup_keys.update(found_keys)

        return tuple(lookup_keys)

    def _find_asn_handles(self) -> list[str]:
        return self._extract_lookup_keys_from_pages(
            self._search_db_and_get_all_pages(self.ASN_QUERY)
        )
    
    def _find_network_handles(self):
        return [
            cidr
            for network_handle in 
            self._extract_lookup_keys_from_pages(
                self._search_db_and_get_all_pages(self.INET_QUERY)
            )
            if (cidr := self._get_network_cidr_from_handle(network_handle))
        ]
