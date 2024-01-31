# orgia
Use RDAP and WHOIS to find ASNs, Networks, and CIDRs about Organisations.

Useful for conducting Recon on a big Organisation.

For example, after running orgia the OG way on "Hilton", I got ```96436``` v4 IPs.

## Installation
### pipx
Global installation:
```sh
pipx install git+https://github.com/sttlr/orgia
orgia -h
```

Or run without installing:
```sh
pipx run --spec git+https://github.com/sttlr/orgia orgia -h
```

### Docker
```sh
git clone https://github.com/sttlr/orgia
cd orgia
```
```sh
docker build -t orgia .
docker run --rm orgia -h
```

## Usage
```
usage: orgia [-h] [--org ORG_NAME] [--version] [--silent] [--debug] [-c PATH] [--sources SOURCE]
             [--orgs-input-file PATH] [--asns-input-file PATH] [--networks-input-file PATH]
             [--max-enrich] [-o PATH] [--adjacent]
             [--orgs | --asns | --networks | --cidrs | --export-all PATH] [--jsonl] [--ip4-only]

Use RDAP and WHOIS to find ASNs, Networks, and CIDRs about Organisations.

options:
  -h, --help            show this help message and exit
  --org ORG_NAME        organization name (ex. "Hilton")
  --version             show program's version number and exit
  --silent              display results only (useful for piping to jq)
  --debug               print debug info
  -c PATH, --config PATH
                        path to .yaml config file
  --sources SOURCE      comma separated, possible values: all (default), arin, ripe, apnic,
                        afrinic, lacnic
  --orgs-input-file PATH
                        path to input file with Organisation handles
  --asns-input-file PATH
                        path to input file with ASN handles
  --networks-input-file PATH
                        path to input file with Network handles
  --max-enrich          use level 2 when trying to bruteforce entity name
  -o PATH, --output PATH
                        path to output file (default stdout)
  --adjacent            parse adjacent (dirty): ASNs from Orgs and Orgs from Networks
  --orgs                show only Organisation handles in output
  --asns                show only ASNs in output
  --networks            show only Network handles in output
  --cidrs               show only CIDRs in output
  --export-all PATH     folder to export everything
  --jsonl               show output in jsonl formal
  --ip4-only            show only IPv4 networks in output

by sttlr
```

### Quick
Get CIDRs for specified Orgname:
```sh
orgia --org ORGNAME --cidrs
```

### Enriched
Try even more enriched Orgnames when searching.
```sh
orgia --org ORGNAME --max-enrich --cidrs
```

### Resolve only
If you have input files with handles, pass them via ```--asns-input-file```, ```--orgs-input-file```, ```--networks-input-file``` and orgia will resolve them for you:
```sh
orgia --asns-input-file ORGNAME_asn_handles.txt \
  --orgs-input-file ORGNAME_org_handles_.txt \
  --networks-input-file ORGNAME_networks_handles.txt
```

You can combine it with any of the output options: ```--cidrs```, ```--orgs```, ```--asns```, ```--networks```, ```--export-all```

### Specific
#### Select source
Choose source (arin, ripe, apnic, afrinic, lacnic) - default "all":
```sh
orgia --org ORGNAME --sources ripe,arin
```

#### IPv4 only
Don't print IPv6 Networks/CIDRs in the output:
```sh
orgia --org ORGNAME --ip4-only --cidrs
```

#### Pipe to jq
By default, orgia prints handles only (for ```--orgs```, ```--asns```, ```--networks```).

You can pass ```--jsonl``` to use JSON as the output format. When piping to ```jq``` also use ```--silent```:
```sh
orgia --org ORGNAME --asns --silent --jsonl | jq
```

#### Use config
Whitelist or blacklist handles, names, emails in output.

When checking, input is lowercased and ```in``` is used for comparison (checks if a config string ```in``` a test string).

You can create a config file and pass it via ```--config``` option:
```sh
orgia --org ORGNAME --cidrs --config PATH_TO_CONFIG.yaml
```

Empty config looks like this:
```yaml
orgs:
  whitelist-handles: []
  blacklist-handles: []
  whitelist-names: []
  blacklist-names: []
  whitelist-emails: []
  blacklist-emails: []

asns:
  whitelist-handles: []
  blacklist-handles: []
  whitelist-names: []
  blacklist-names: []
  whitelist-emails: []
  blacklist-emails: []
  
networks:
  whitelist-handles: []
  blacklist-handles: []
  whitelist-names: []
  blacklist-names: []
  whitelist-emails: []
  blacklist-emails: []
```

### OG
Comprehensive.

Create handle input files via [org_info](https://github.com/sttlr/org_info) - parse directly from RIPE, APNIC, AfriNIC WHOIS databases:
```sh
./bin/query_asn ORGNAME > ORGNAME_asns_from_org_info.txt
./bin/query_org ORGNAME > ORGNAME_orgs_from_org_info.txt
./bin/query_inetnum ORGNAME > ORGNAME_networks_from_org_info.txt
```

Then run the OG:
```sh
orgia --org ORGNAME \
  --sources all \
  --max-enrich \
  --asns-input-file ORGNAME_asns_from_org_info.txt \
  --orgs-input-file ORGNAME_orgs_from_org_info.txt \
  --networks-input-file ORGNAME_networks_from_org_info.txt \
  --export-all orgia_ORGNAME_export \
  --config orgia_ORGNAME_config.yaml
```

Folder with results (```orgia_ORGNAME_export```) will contain:
- ```cidrs.txt``` - list of all CIDRs
- ```asns.jsonl``` - ASN info in JSONL format
- ```orgs.jsonl``` - Organisation info in JSONL format
- ```networks.jsonl``` - Network info in JSONL format

### Adjacent mode (dirty)
You can use ```--adjacent``` option, to also extract ASNs from Orgs and Orgs from Networks.
NOTE: It's dirty, and will result in lots of trash results.

### API
You can import orgia as a package to use it in your scripts:
```python
from orgia.nics import RIPE, ARIN, LACNIC, APNIC, AFRINIC
```

Or low-level:
```python
from orgia.nics import RDAP, Engine
```

NOTE: orgia isn't designed to be used this way.

### TODO
Pull requests are welcome ;)
- Implement Async via ```httpx.AsyncClient()```
- Improve upon developer API - get rid of ```args``` argument when creating a class
- Add more options in a config file
