from sys import stderr, stdout
from yaml import safe_load
from os.path import exists, isfile
from os import mkdir
from json import dumps

from . import BANNER, VERSION
from .nics import RIPE, ARIN, LACNIC, AFRINIC, APNIC
from argparse import ArgumentParser


def get_args():
    parser = ArgumentParser(
        prog='orgia',
        description='Use RDAP and WHOIS to find ASNs, Networks, and CIDRs about Organisations.',
        epilog='by sttlr'
    )

    parser.add_argument(
        '--org',
        help='organization name (ex. "Hilton")',
        metavar='ORG_NAME'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {VERSION}'
    )
    parser.add_argument(
        '--silent',
        help='display results only (useful for piping to jq)',
        action='store_true'
    )
    parser.add_argument(
        '--debug',
        help='print debug info',
        action='store_true'
    )

    parser.add_argument(
        '-c', '--config',
        help='path to .yaml config file',
        metavar='PATH'
    )

    parser.add_argument(
        '--sources',
        help='comma separated, possible values: '
             'all (default), arin, ripe, apnic, afrinic, lacnic',
        metavar='SOURCE',
        default='all'
    )

    parser.add_argument(
        '--orgs-input-file',
        help='path to input file with Organisation handles',
        metavar='PATH'
    )
    parser.add_argument(
        '--asns-input-file',
        help='path to input file with ASN handles',
        metavar='PATH'
    )
    parser.add_argument(
        '--networks-input-file',
        help='path to input file with Network handles',
        metavar='PATH'
    )

    parser.add_argument(
        '--max-enrich',
        help='use level 2 when trying to bruteforce entity name',
        action='store_true'
    )

    parser.add_argument(
        '-o', '--output',
        help='path to output file (default stdout)',
        metavar='PATH'
    )

    parser.add_argument(
        '--adjacent',
        help='parse adjacent (dirty): ASNs from Orgs and Orgs from Networks',
        action='store_true'
    )

    output_info_group = parser.add_mutually_exclusive_group()
    output_info_group.add_argument(
        '--orgs',
        help='show only Organisation handles in output',
        action='store_true'
    )
    output_info_group.add_argument(
        '--asns',
        help='show only ASNs in output',
        action='store_true'
    )
    output_info_group.add_argument(
        '--networks',
        help='show only Network handles in output',
        action='store_true'
    )
    output_info_group.add_argument(
        '--cidrs',
        help='show only CIDRs in output',
        action='store_true'
    )
    output_info_group.add_argument(
        '--export-all',
        help='folder to export everything',
        metavar='PATH'
    )

    parser.add_argument(
        '--jsonl',
        help='show output in jsonl formal',
        action='store_true'
    )
    
    parser.add_argument(
        '--ip4-only',
        help='show only IPv4 networks in output',
        action='store_true'
    )

    parser.add_argument(
        '--country',
        help='filter results by country'
    )

    args = parser.parse_args()

    if not any((
        args.org,
        args.orgs_input_file,
        args.asns_input_file,
        args.networks_input_file
    )):
        raise Exception('No input options. Provide Organisation name (--org) or input files (--*-input-file).')
    
    for f in (args.orgs_input_file,
              args.asns_input_file,
              args.networks_input_file):
        if f and (not exists(f) or not isfile(f)):
            raise Exception(f'File "{f}" doens\'t exist')
        
    if not any((
        args.orgs,
        args.asns,
        args.networks,
        args.cidrs,
        args.export_all
    )):
        raise Exception('No output options. Provide one of: --orgs, --asns, --networks, --cidrs, --export-all')

    if not args.sources:
        args.sources = ('all',)
    else:
        sources = args.sources.split(',')
        if 'all' in sources and len(sources) > 1:
            raise Exception('Remove "all" to select specific sources.')
        
        for s in sources:
            if s not in ('all', 'ripe', 'arin', 'lacnic', 'apnic', 'afrinic'):
                raise Exception(f'"{s}" is an invalid source option')
        
        if len(set(sources)) != len(sources):
            raise Exception('Please remove duplicate sources.')

        args.sources = sources

    if args.cidrs and args.jsonl:
        raise Exception('Can\'t use --cidrs and --jsonl.')
    
    if args.export_all:
        if exists(args.export_all):
            if isfile(args.export_all):
                raise Exception(f'"{args.export_all}" is an existing file. '
                                'Please provide folder name.')
        else:
            mkdir(args.export_all)

    if args.config:
        if not exists(args.config):
            raise Exception(f'File "{args.config}" doesn\'t exist.')
        elif not isfile(args.config):
            raise Exception(f'"{args.config}" is a folder.')
        else:
            args.config = safe_load(open(args.config).read())

    return args


def main():
    args = get_args()

    if not args.silent:
        print(BANNER, file=stderr, flush=True)
    
    output_fd = open(args.output, 'w') if args.output else stdout

    org_name = args.org
    
    sources = []
    for s in args.sources:
        match s.lower():
            case 'all':
                sources = [
                    cls(org_name, args)
                    for cls in (RIPE, LACNIC, AFRINIC, APNIC, ARIN)
                ]
                break
            case 'ripe':
                sources.append(RIPE(org_name, args))
            case 'arin':
                sources.append(ARIN(org_name, args))
            case 'lacnic':
                sources.append(LACNIC(org_name, args))
            case 'afrinic':
                sources.append(AFRINIC(org_name, args))
            case 'apnic':
                sources.append(APNIC(org_name, args))

    for t, f in (('entity', args.orgs_input_file),
                 ('autnum', args.asns_input_file),
                 ('ip', args.networks_input_file)):
        if not f:
            continue

        handles = (o for o in open(f).read().split('\n') if o)
        
        for handle in handles:
            if t == 'autnum':
                handle = handle.replace('AS', '')

            if class_name := sources[0].rdap_bootstrap(t, handle):
                if s := [s for s in sources
                         if s.__class__.__name__ == class_name]:
                    s = s[0]
                else:
                    break

                type_to_source_handles = {
                    'entity': s.org_handles,
                    'autnum': s.asn_handles,
                    'ip': s.network_handles
                }
                type_to_source_handles[t].append(handle)

    for s in sources:
        if args.export_all:
            continue
        elif args.orgs:
            data_source = s.orgs
            handles = s.org_handles
        elif args.asns:
            data_source = s.asns
            handles = ['AS' + a for a in s.asn_handles]
        elif args.networks:
            data_source = s.networks
            handles = s.network_handles
        elif args.cidrs:
            handles = s.cidrs

        if args.jsonl:
            for o in data_source:
                print(dumps(o), file=output_fd, flush=True)
        else:
            for handle in handles:
                print(handle, file=output_fd, flush=True)
    
    if args.export_all:
        with (open(f'{args.export_all}/cidrs.txt', 'w') as cidrs_fd,
              open(f'{args.export_all}/orgs.jsonl', 'w') as orgs_fd,
              open(f'{args.export_all}/asns.jsonl', 'w') as asns_fd,
              open(f'{args.export_all}/networks.jsonl', 'w') as networks_fd):
            for s in sources:
                for cidr in s.cidrs:
                    cidrs_fd.write(cidr)
                    cidrs_fd.write('\n')

                for org in s.orgs:
                    orgs_fd.write(dumps(org))
                    orgs_fd.write('\n')
                
                for asn in s.asns:
                    asns_fd.write(dumps(asn))
                    asns_fd.write('\n')

                for network in s.networks:
                    networks_fd.write(dumps(network))
                    networks_fd.write('\n')

    if args.output:
        output_fd.close()
