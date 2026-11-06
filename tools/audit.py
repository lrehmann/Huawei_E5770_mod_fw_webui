#!/usr/bin/env python3
"""Inventory every firmware file, inspect text/gzip/XML and hardening of ARM ELFs."""
from pathlib import Path
import argparse
import collections
import gzip
import hashlib
import json
import os
import re
import struct
import xml.etree.ElementTree as ET
from pixels import ROOT


def elf_info(data):
    if data[:5] != b'\x7fELF\x01' or data[5] != 1 or len(data)<52:
        return None
    kind,machine = struct.unpack_from('<HH',data,16)
    offset = struct.unpack_from('<I',data,28)[0]
    size,count = struct.unpack_from('<HH',data,42)
    stack = None
    relro = False
    for n in range(count):
        pos = offset+n*size
        if size<32 or pos+32>len(data):
            return {'malformed':True}
        ph = struct.unpack_from('<IIIIIIII',data,pos)
        if ph[0] == 0x6474e551:
            stack = bool(ph[6] & 1)
        if ph[0] == 0x6474e552:
            relro = True
    strings = re.findall(rb'[ -~]{6,}',data)
    versions = [s.decode() for s in strings if re.search(rb'(BusyBox v[0-9]|^OpenSSL [0-9]|^curl [0-9]|^dnsmasq-[0-9]|^OpenVPN [0-9]|^Linux version)',s)]
    return {'type':kind,'machine':machine,'executable_stack':stack,'gnu_relro_segment':relro,
            'stack_canary_symbol':b'__stack_chk_fail' in data,'version_strings':versions[:12]}


def scan():
    inventory, errors = [], []
    counts = collections.Counter()
    for base in ('app','system','web'):
        for p in sorted((ROOT/base).rglob('*')):
            name = p.relative_to(ROOT).as_posix()
            if p.is_symlink():
                inventory.append({'path':name,'kind':'symlink','target':os.readlink(p)})
                counts['symlinks'] += 1
                continue
            if not p.is_file():
                continue
            data = p.read_bytes()
            info = {'path':name,'kind':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            counts['files'] += 1
            counts['bytes'] += len(data)
            elf = elf_info(data)
            if elf:
                info['elf'] = elf
                counts['elfs'] += 1
            if p.suffix == '.gz':
                try:
                    data = gzip.decompress(data)
                    info['gzip_uncompressed_bytes'] = len(data)
                    counts['gzip_checked'] += 1
                except (gzip.BadGzipFile,EOFError,OSError) as e:
                    errors.append({'path':name,'error':'gzip: '+str(e)})
            if p.suffix == '.xml':
                try:
                    ET.fromstring(data)
                    counts['xml_valid'] += 1
                except ET.ParseError as e:
                    errors.append({'path':name,'error':'xml: '+str(e)})
            if b'\0' not in data:
                text = data.decode('utf-8',errors='replace')
                counts['text_files_scanned'] += 1
                flags = {}
                patterns = {'http_urls':r'http://[^\s<>"\x27]+','eval_calls':r'\beval\s+',
                            'html_sinks':r'\.html\s*\(|innerHTML\s*=',
                            'shell_exec':r'\bsystem\s*\(|\bpopen\s*\(',
                            'offensive_startup_text':r'(?i)not for resale[^\n]{0,40}|\bfaggot\b'}
                for key,pattern in patterns.items():
                    hits = list(re.finditer(pattern,text))
                    if hits:
                        flags[key] = {'count':len(hits),'lines':sorted(set(text.count('\n',0,m.start())+1 for m in hits))[:40]}
                if flags:
                    info['review_flags'] = flags
            inventory.append(info)
    return {'schema_version':1,'scope':'repository filesystem trees; static inspection, not a complete binary security audit',
            'counts':dict(counts),'parse_errors':errors,'inventory':inventory}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'audit/inventory.json')
    args = parser.parse_args()
    result = scan()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'counts':result['counts'],'parse_errors':result['parse_errors']},indent=2))


if __name__ == '__main__':
    main()
