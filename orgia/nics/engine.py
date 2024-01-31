import httpx
from string import ascii_lowercase, digits
from urllib.parse import quote
from time import sleep
from traceback import print_exc


class RDAP:
    def request_rdap(self, query: str) -> dict:
        url = self.RDAP_URL + query
        r = self._http_request(url)
        if not r:
            return None
        return r.json()
    
    def search_entities(self, fn: str) -> list[str]:
        entities = self.request_rdap(f'/entities?fn={quote(fn)}')
        if entities:
            return [e['handle']
                    for e in entities['entitySearchResults']
                    if [l[3]
                        for l in e['vcardArray'][1]
                        if l[0] == 'fn'
                        ][0] == 'org']  # return orgs only
        return []

    def get_entity_by_handle(self, entity_handle: str) -> dict:
        rdap_entity_response = self.request_rdap(f'/entity/{entity_handle}')
        return self.parse_entity_response(rdap_entity_response)
    
    def get_asn_by_handle(self, asn_handle: str) -> dict:
        rdap_asn_response = self.request_rdap(f'/autnum/{asn_handle.replace("AS", "")}')
        return self.parse_asn_response(rdap_asn_response)
    
    def get_network_by_handle(self, network_handle: str) -> dict:
        rdap_network_response = self.request_rdap(f'/ip/{quote(network_handle)}')
        return self.parse_network_response(rdap_network_response)
    
    def parse_entity_response(self, rdap_entity_response: dict) -> dict:
        j = rdap_entity_response

        if not j:
            if self.args.debug:
                print('Skipped Organisation for previous request')
            return {}
        
        support_emails = [
            l[3] for e in j['entities']
            for l in e['vcardArray'][1] if l[0] == 'email'
        ] if 'entities' in j.keys() else []
        asns = [
            self.parse_asn_response(a) for a in j['autnums']
        ] if 'autnums' in j.keys() else []
        networks = [
            self.parse_network_response(n) for n in j['networks']
            if not self.args.ip4_only or (self.args.ip4_only and n['ipVersion'] == 'v4')
        ] if 'networks' in j.keys() else [] 

        registered = None
        last_changed = None
        
        if events := j.get('events'):
            for e in events:
                event_action = e.get('eventAction')
                event_date = e.get('eventDate')
                if event_date:
                    if event_action == 'registration':
                        registered = event_date
                    elif event_action == 'last changed':
                        last_changed = event_date

        entity = {
            'handle': j['handle'],
            'name': [l[3] for l in j['vcardArray'][1] if l[0] == 'fn'][0],
            'last_changed': last_changed,
            'registered': registered,
            'support_emails': support_emails,
            'asns': asns,
            'networks': networks,
            'source': self.__class__.__name__
        }
        return entity

    def parse_asn_response(self, rdap_asn_response: dict) -> dict:
        a = rdap_asn_response

        if not a:
            if self.args.debug:
                print('- Skipped ASN for previous request')
            return {}
        
        registered = None
        last_changed = None
        
        if events := a.get('events'):
            for e in events:
                event_action = e.get('eventAction')
                event_date = e.get('eventDate')
                if event_date:
                    if event_action == 'registration':
                        registered = event_date
                    elif event_action == 'last changed':
                        last_changed = event_date
    
        r = {
            'handle': a['handle'],
            'name': a['name'],
            'last_changed': last_changed,
            'registered': registered,
            'source': self.__class__.__name__
        }
        r['networks'] = [
            self.parse_network_response(n) for n in a['networks']
            if not self.args.ip4_only or (self.args.ip4_only and n['ipVersion'] == 'v4')
        ] if 'networks' in a.keys() else []

        r['entities'] = [
            self.parse_entity_response(e) for e in a['entities']
            if [l[3]
                for l in e['vcardArray'][1]
                if l[0] == 'kind'
                ][0] == 'org'
        ] if 'entities' in a.keys() else []

        return r

    def parse_network_response(self, rdap_network_response: dict) -> dict:
        n = rdap_network_response

        if not n:
            if self.args.debug:
                print('Skipped network for previous request')
            return {}
        
        registered = None
        last_changed = None
        
        if events := n.get('events'):
            for e in events:
                event_action = e.get('eventAction')
                event_date = e.get('eventDate')
                if event_date:
                    if event_action == 'registration':
                        registered = event_date
                    elif event_action == 'last changed':
                        last_changed = event_date

        r = {
            'handle': n['handle'],
            'ip_version': n['ipVersion'],
            'cidrs': [f"{c[n['ipVersion'] + 'prefix']}/{c['length']}"
                      for c in n['cidr0_cidrs']
                      ] if n.get('cidr0_cidrs') else [n['handle']],
            'last_changed': last_changed,
            'registered': registered,
            'source': self.__class__.__name__
        }
        r['name'] = n.get('name')
        r['country'] = n.get('country')

        r['description'] = None
        if remarks := n.get('remarks'):
            for remark in remarks:
                if description := remark.get('description'):
                    r['description'] = description
        
        r['entities'] = [
            self.parse_entity_response(e) for e in n['entities']
            if [l[3]
                for l in e['vcardArray'][1]
                if l[0] == 'kind'
                ][0] == 'org'
        ] if 'entities' in n.keys() else []

        return r


class Engine(RDAP):
    def __init__(self) -> None:
        self._orgs = None
        self._org_handles = None

        self._asns = None
        self._asn_handles = None

        self._networks = None
        self._network_handles = None

        self.config = None
    
    def _in_list(self, type: str, color: str, handle_or_dict: str | dict) -> bool:
        if not self.config:
            return
        
        match handle_or_dict:
            case str():
                if handle_or_dict in self.config.get(type, {}).get(f'{color}list-handles', []):
                    return True
            case dict():
                if handle_or_dict['handle'] in self.config.get(type, {}).get(f'{color}list-handles', []):
                    return True
                for name in self.config.get(type, {}).get(f'{color}list-names', []):
                    if name in handle_or_dict['name']:
                        return True
                for email in self.config.get(type, {}).get(f'{color}list-emails', []):
                    if email in handle_or_dict.get('support_emails', []):
                        return True
        
        return False
    
    def _in_whitelist(self, type: str, handle_or_dict: str | dict) -> bool:
        return self._in_list(type, 'white', handle_or_dict)

    def _in_blacklist(self, type: str, handle_or_dict: str | dict) -> bool:
        return self._in_list(type, 'black', handle_or_dict)

    def _org_in_whitelist(self, org: str | dict) -> bool:
        return self._in_whitelist('orgs', org)
    
    def _asn_in_whitelist(self, asn: str | dict) -> bool:
        return self._in_whitelist('asns', asn)

    def _network_in_whitelist(self, network: str | dict) -> bool:
        return self._in_whitelist('networks', network)
    
    def _org_in_blacklist(self, org: str | dict) -> bool:
        return self._in_blacklist('orgs', org)
    
    def _asn_in_blacklist(self, asn: str | dict) -> bool:
        return self._in_blacklist('asns', asn)

    def _network_in_blacklist(self, network: str | dict) -> bool:
        return self._in_blacklist('networks', network)

    @property
    def org_handles(self) -> list[str]:
        if self._org_handles is None:
            self._org_handles = list(set(self._find_org_handles())) if self.org_name else []
        self._org_handles = [
            o for o in self._org_handles
            if self._org_in_whitelist(o)
            or not self._org_in_blacklist(o)
        ]
        return self._org_handles
    
    @org_handles.setter
    def org_handles(self, value) -> None:
        self._org_handles = [
            o for o in value
            if self._org_in_whitelist(o)
            or not self._org_in_blacklist(o)
        ]

    @property
    def asn_handles(self) -> list[str]:
        if self._asn_handles is None:
            self._asn_handles = list(set(self._find_asn_handles())) if self.org_name else []
        self._asn_handles = [
            a for a in self._asn_handles
            if self._asn_in_whitelist(a)
            or not self._asn_in_blacklist(a)
        ]
        return self._asn_handles
    
    @asn_handles.setter
    def asn_handles(self, value) -> None:
        self._asn_handles = [
            a for a in value
            if self._asn_in_whitelist(a)
            or not self._asn_in_blacklist(a)
        ]

    @property
    def network_handles(self) -> list[str]:
        if self._network_handles is None:
            self._network_handles = list(set(self._find_network_handles())) if self.org_name else []
        self._network_handles = [
            n for n in self._network_handles
            if self._network_in_whitelist(n)
            or not self._network_in_blacklist(n)
        ]
        return self._network_handles
    
    @network_handles.setter
    def network_handles(self, value) -> None:
        self._network_handles = [
            n for n in value
            if self._network_in_whitelist(n)
            or not self._network_in_blacklist(n)
        ]

    def _http_request(self, url: str,
                      headers=None, cookies=None, follow_redirects: bool=False,
                      retry_count: int=0):
        try:
            if self.args.debug:
                print(f'Requested {url}')

            sleep(self.DELAY)
            r = httpx.get(url, headers=headers, cookies=cookies,
                          follow_redirects=follow_redirects, timeout=15)
            
            if str(r.url) != url:
                if self.args.debug:
                    print(f'Redirected to {str(r.url)}')
                
            if r.status_code in (301, 302):
                return r
            elif r.status_code in (403, 404):
                return None
            r.raise_for_status()
        except Exception:
            retry_count += 1
            if self.args.debug:
                print_exc()
            if retry_count < 5:  # retry 4 times
                self._http_request(url=url, headers=headers, cookies=cookies,
                                   follow_redirects=follow_redirects, retry_count=retry_count + 1)
        return r

    def rdap_bootstrap(self, type: str, query: str) -> None:
        if type not in ('entity', 'autnum', 'ip'):
            raise Exception('type options: entity, autnum, ip')
        
        origin_to_class_name = {
            'rdap.arin.net': 'ARIN',
            'rdap.db.ripe.net': 'RIPE',
            'rdap.lacnic.net': 'LACNIC',
            'rdap.apnic.net': 'APNIC',
            'rdap.afrinic.net': 'AFRINIC'
        }
        base_url = f'https://rdap-bootstrap.arin.net/bootstrap/{type}/{quote(query)}'

        sleep(0.1)
        if r := self._http_request(base_url, follow_redirects=True):
            origin = r.url.netloc.decode()
            # if next_request := r.next_request:
            #     origin = next_request.url.netloc.decode()
            return origin_to_class_name.get(origin)

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
            for l in ascii_lowercase + digits:
                enriched_org_names.append(f'{org_name} {l}*')
                enriched_org_names.append(f'{l}* {org_name}')
                enriched_org_names.append(f'*{org_name} {l}*')
                enriched_org_names.append(f'{l}* {org_name}*')
        
        return [quote(i) for i in enriched_org_names]
    
    def _extract_lookup_keys_from_pages(self, pages: list) -> tuple:
        return [e['handle']
                for p in pages
                for e in p.get('entitySearchResults', p.get('entities'))
                if [l[3]
                    for l in e['vcardArray'][1]
                    if l[0] == 'kind'
                    ][0] == 'org']  # return orgs only
    
    def _search_db_and_get_all_pages(self, query: str) -> list:
        wildcards_formatted_query = query.format(org_name=f'*{self.org_name}*')
        pages = [self._request_db(wildcards_formatted_query)]

        # use wildcard query to determine if we should try to bruteforce
        if len(self._extract_lookup_keys_from_pages((pages[0],))) >= self.MAX_RESULTS_IN_A_SEARCH:
            enriched_org_names = self._enrich_org_name(level=1)
            if self.args.max_enrich:
                enriched_org_names += self._enrich_org_name(level=2)

            for enriched_org_name in enriched_org_names:
                pages.append(
                    self._request_db(
                        query.format(org_name=enriched_org_name)
                    )
                )
        return pages
    
    @property
    def orgs(self) -> list[dict]:
        if self._orgs is None:
            self._orgs = []
            for org_handle in self.org_handles:
                org = self.get_entity_by_handle(org_handle)

                if not self._org_in_whitelist(org) and self._org_in_blacklist(org):
                    continue

                self._orgs.append(org)

                for n in org['networks']:
                    if not self._network_in_whitelist(n) and self._network_in_blacklist(n):
                        continue

                    if n['cidrs']:
                        if (n['handle'] not in self.network_handles
                            and n['cidrs'][0] not in self.network_handles):
                            self.network_handles.append(n['cidrs'][0])
                            self.networks.append(self.get_network_by_handle(n['cidrs'][0]))
                
                if self.args.adjacent:
                    if not self.args.silent and self.args.debug:
                        print('Using adjacent mode: appending ASNs from Org')
                    for a in org['asns']:
                        if not self._asn_in_whitelist(a) and self._asn_in_blacklist(a):
                            continue

                        if a['handle'] not in self.asn_handles:
                            self.asn_handles.append(a['handle'])
                            self.asns.append(self.get_asn_by_handle(a['handle']))

        return self._orgs

    @orgs.setter
    def orgs(self, value):
        self._orgs = value

    @property
    def asns(self) -> list[dict]:
        if self._asns is None:
            self._asns = []
            for asn_handle in self.asn_handles:
                asn = self.get_asn_by_handle(asn_handle)

                if not self._asn_in_whitelist(asn) and self._asn_in_blacklist(asn):
                    continue

                self._asns.append(asn)

                for n in asn['networks']:
                    if not self._network_in_whitelist(n) and self._network_in_blacklist(n):
                        continue

                    if n['cidrs']:
                        if (n['handle'] not in self.network_handles
                            and n['cidrs'][0] not in self.network_handles):
                            self.network_handles.append(n['cidrs'][0])
                            self.networks.append(n['cidrs'][0])

                # if self.args.adjacent:
                for e in asn['entities']:
                    if not self._org_in_whitelist(e) and self._org_in_blacklist(e):
                        continue

                    if e['handle'] not in self.org_handles:
                        org = self.get_entity_by_handle(e['handle'])
                        if org:
                            self.org_handles.append(e['handle'])
                            self.orgs.append(org)
                    
        return self._asns
    
    @asns.setter
    def asns(self, value):
        self._asns = value

    @property
    def networks(self) -> list[dict]:
        if self._networks is None:
            self._networks = []
            for network_handle in self.network_handles:
                network = self.get_network_by_handle(network_handle)

                if not self._network_in_whitelist(network) and self._network_in_blacklist(network):
                    continue
                
                if self.args.ip4_only and network['ip_version'] != 'v4':
                    continue
                self._networks.append(network)

                if self.args.adjacent:
                    if not self.args.silent and self.args.debug:
                        print('Using adjacent mode: appending Orgs from Network')
                    for e in network['entities']:
                        if not self._org_in_whitelist(e) and self._org_in_blacklist(e):
                            continue

                        org = self.get_entity_by_handle(e['handle'])
                        if org:
                            self.org_handles.append(e['handle'])
                            self.orgs.append(org)
        return self._networks

    @networks.setter
    def networks(self, value):
        self._networks = value

    @property
    def cidrs(self) -> list[str]:
        cidrs = []
        for org in [*self.orgs, *self.asns]:
            for network in org['networks']:
                for cidr in network['cidrs']:
                    cidrs.append(cidr)
        for network in self.networks:
            if self.args.ip4_only and network['ip_version'] != 'v4':
                    continue
            for cidr in network['cidrs']:
                cidrs.append(cidr)
        return list(set(cidrs))

    def _find_org_handles(self) -> list[str]:
        return self._extract_lookup_keys_from_pages(
            self._search_db_and_get_all_pages(self.ORG_QUERY)
        )

    def _find_asn_handles(self) -> list[str]:
        return [a['handle']
                for o in self.orgs
                for a in o['asns']]
    
    def _find_network_handles(self) -> list[str]:
        return [n['handle']
                for o in [*self.orgs,
                          *[a['networks'] for a in self.asns]]
                for n in o['networks']]
