import string
from urllib.parse import quote
from .engine import Engine


class APNIC(Engine):
    DELAY = 0
    MAX_RESULTS_IN_A_SEARCH = 10000
    RDAP_URL = 'https://rdap.apnic.net'
    ORG_QUERY = '/entities?fn={org_name}'  # This one is case sensitive

    def __init__(self, org_name: str, args):
        super().__init__()
        self.org_name = org_name.lower() if org_name else None
        self.args = args
        self._request_db = self.request_rdap
        self.config = self.args.config

    def _find_network_handles(self) -> list[str]:
        return [n['cidrs'][0]
                for o in self.orgs
                for n in o['networks']]
    
    def _letter_case_permutations(self, word: str) -> list[str]:
        '''Generate all possible permutations of case in letters.'''
        if not word:  # Base case: empty string
            return ['']
        else:
            first_char = word[0]
            lower = first_char.lower()
            upper = first_char.upper()
            rest_permutations = self._letter_case_permutations(word[1:])
            permutations = [lower + p for p in rest_permutations] + [upper + p for p in rest_permutations]
            return permutations
    
    def _enrich_org_name(self, level: int) -> list[str]:
        if level not in (1, 2):
            raise Exception('level must be either 1 or 2')
        
        org_name = self.org_name

        if level == 1:
            enriched_org_names = [
                org_name,
                f'* {org_name} *',
                f'{org_name} *',
                f'{org_name}*',
                f'* {org_name}',
                f'*{org_name}',
                f'*-{org_name}',
                f'*-{org_name}*',
                f'*-{org_name}-*',
                f'{org_name}-*',
                f'*{org_name}-*',
            ]
        elif level == 2:
            enriched_org_names = []
            for l in string.ascii_letters + string.digits:
                enriched_org_names.append(f'{org_name} {l}*')
                enriched_org_names.append(f'{l}* {org_name}')
                enriched_org_names.append(f'*{org_name} {l}*')
                enriched_org_names.append(f'{l}* {org_name}*')
        
        return [quote(i) for i in enriched_org_names]
    
    def _search_db_and_get_all_pages(self, query: str) -> list:
        orig_org_name = self.org_name
        pages = []
        for i, cased_org_name in enumerate(
                (self.org_name.upper(),
                self.org_name.capitalize(),
                self.org_name.lower())
            ):
            pages.append(
                self._request_db(query.format(org_name=f'*{cased_org_name}*'))
            )
            self.org_name = cased_org_name

            # if len(self._extract_lookup_keys_from_pages((pages[i],))) >= self.MAX_RESULTS_IN_A_SEARCH:
            enriched_org_names = self._enrich_org_name(level=1)
            if self.args.max_enrich:
                enriched_org_names += self._enrich_org_name(level=2)

            for enriched_org_name in enriched_org_names:
                pages.append(
                    self._request_db(
                        query.format(org_name=enriched_org_name)
                    )
                )

        self.org_name = orig_org_name
        return pages