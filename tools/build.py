#!/usr/bin/env python3
"""Create deterministic, root-owned experimental filesystem archives, without sudo."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import subprocess
from pixels import ROOT


def newc_entry(stream, name, data, mode, inode, epoch):
    encoded = name.encode() + b'\0'
    values = [inode,mode,0,0,2 if stat.S_ISDIR(mode) else 1,epoch,len(data),0,0,0,0,len(encoded),0]
    header = b'070701' + ''.join(f'{v:08x}' for v in values).encode()
    stream.write(header + encoded)
    stream.write(b'\0' * ((-(110+len(encoded))) % 4))
    stream.write(data)
    stream.write(b'\0' * ((-len(data)) % 4))


def package(source, target, epoch):
    paths = [source] + sorted(source.rglob('*'))
    entries = []
    with target.open('wb') as stream:
        for i,p in enumerate(paths,1):
            name = '.' if p == source else p.relative_to(source).as_posix()
            s = p.lstat()
            if p.is_symlink():
                data = os.readlink(p).encode()
            elif stat.S_ISREG(s.st_mode):
                data = p.read_bytes()
            elif stat.S_ISDIR(s.st_mode):
                data = b''
            else:
                raise ValueError(f'Unsupported filesystem object: {p}')
            mode = stat.S_IFMT(s.st_mode) | (stat.S_IMODE(s.st_mode) & 0o777)
            newc_entry(stream,name,data,mode,i,epoch)
            entries.append({'path':name,'mode':oct(mode),'bytes':len(data),
                            'sha256':hashlib.sha256(data).hexdigest()})
        newc_entry(stream,'TRAILER!!!',b'',0,len(paths)+1,epoch)
        stream.write(b'\0' * ((-stream.tell()) % 512))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experimental',action='store_true',help='acknowledge these are unvalidated filesystem archives')
    parser.add_argument('--output',type=Path,default=ROOT/'build/experimental')
    args = parser.parse_args()
    if not args.experimental:
        parser.error('--experimental is required; no flashable or signed firmware is produced')
    output = args.output.resolve()
    if any(output == ROOT/p or ROOT/p in output.parents for p in ('app','system','web')):
        parser.error('Output must be outside the firmware trees')
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH',(ROOT/'system/etc/cozy/build-epoch').read_text().strip()))
    if not 0 <= epoch <= 0xffffffff:
        parser.error('Invalid SOURCE_DATE_EPOCH')
    lock=json.loads((ROOT/'audit/base-lock.json').read_text())
    for file,expected in lock['binaries'].items():
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Unreviewed binary/ABI change: {file}; port and review the hooks before updating the lock')
    default = ROOT/'system/etc/cozy/default.profile'
    profile = default.read_bytes()
    if len(profile)>8192 or any(c!=10 and not 32<=c<=126 for c in profile):
        raise ValueError('Invalid bytes in default profile')
    subprocess.run(['awk','-f',str(ROOT/'system/etc/cozy/profile.awk'),str(default)],check=True)
    for file in ('system/bin/cozy-admin','system/bin/cozy-apply','system/www/cozy/cgi-bin/settings.cgi'):
        if not os.access(ROOT/file,os.X_OK):
            raise ValueError(f'Missing executable bit: {file}')
    output.mkdir(parents=True,exist_ok=True)
    manifest = {'format':'cozy-experimental-filesystems-v1','flash_ready':False,
                'source_date_epoch':epoch,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
                'partitions':{}}
    for name in ('app','system','web'):
        target = output/f'{name}-mod.cpio'
        entries = package(ROOT/name,target,epoch)
        digest = hashlib.file_digest(target.open('rb'),'sha256').hexdigest()
        (output/f'{target.name}.sha256').write_text(f'{digest}  {target.name}\n')
        manifest['partitions'][name] = {'file':target.name,'sha256':digest,'bytes':target.stat().st_size,'entries':entries}
        print(f'{name}: {target.stat().st_size:,} bytes; sha256 {digest}')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Experimental filesystem archives only. Device flashing is not implemented.')


if __name__ == '__main__':
    main()
