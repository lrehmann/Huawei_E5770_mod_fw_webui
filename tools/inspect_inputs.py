#!/usr/bin/env python3
"""Read supplied firmware/source archives without running their contents."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import subprocess
from balong import partitions


def inspect_firmware(path):
    data=path.read_bytes()
    result={'file':path.name,'sha256':hashlib.sha256(data).hexdigest(),
            'format':'Huawei Balong raw update container','cryptographic_authenticity_verified':False,'partitions':[]}
    for part in partitions(data):
        result['partitions'].append({'name':part.name,'code':f'{part.code:08x}','offset':part.offset,
            'bytes':len(part.data),'sha256':hashlib.sha256(part.data).hexdigest(),
            'header_crc_ok':part.header_crc_ok,'block_crc_ok':part.block_crc_ok,'version':part.version})
    return result


def inspect_source(path):
    # Listing only. Paths or instructions in archive members are never executed.
    names=subprocess.check_output(['tar','-tf',str(path)],text=True,timeout=60).splitlines()
    top=collections.Counter(n.split('/')[2] for n in names if len(n.split('/'))>2)
    return {'file':path.name,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
            'archive_members':len(names),'top_level_member_counts':dict(top),
            'full_source_review_complete':False,'members':names}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path)
    parser.add_argument('--source-archive',type=Path)
    parser.add_argument('--output',type=Path,default=Path('build/supplied-inputs.json'))
    args=parser.parse_args()
    result={'firmware':inspect_firmware(args.firmware)}
    if args.source_archive:result['source']=inspect_source(args.source_archive)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'Wrote {args.output}; archive contents were not executed')
