#!/usr/bin/env python3
"""Package a verified full flash set together with offline installation docs."""
from pathlib import Path
import argparse
import hashlib
import json
import stat
import time
import zipfile
from firmware import ROOT, verify_bundle


def package_release(bundle, output):
    report = verify_bundle(bundle)
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    variant = 'personalization' if report['admin_enabled_by_default'] else 'standard'
    filename = f'Cozy_E5770_{report["version"]}_{variant}.zip'
    members = {name: (bundle/name).read_bytes() for name in ('MANIFEST.json', 'SHA256SUMS')}
    for value in report['images'].values():
        members[value['file']] = (bundle/value['file']).read_bytes()
    for name in ('INSTALL.md', 'RECOVERY.md', 'BUILD.md'):
        members[name] = (ROOT/'docs'/name).read_bytes()
    members['NOTICE.md'] = (ROOT/'NOTICE.md').read_bytes()
    members['FLASHER_LOCK.json'] = (ROOT/'firmware/flasher.lock.json').read_bytes()
    members['VALIDATION.json'] = (json.dumps(report, indent=2)+'\n').encode()
    members['README.txt'] = (
        f'Cozy E5770 {report["version"]} — {variant}\n\n'
        'Read INSTALL.md before any device write. Both BIN images are required.\n'
        'Complete experimental flash set; not hardware-qualified or newly OEM-signed.\n'
        'Direct installation from stock 21.318.01.00.00 is not verified.\n'
        'Private NV/calibration backups and a verified recovery path are prerequisites.\n'
        'Source: https://github.com/lrehmann/Huawei_E5770_mod_fw_webui\n'
    ).encode()
    output.mkdir(parents=True, exist_ok=True)
    target = output/filename
    date = time.gmtime(manifest['source_date_epoch'])[:6]
    if date[0] < 1980:
        date = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=date)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG|0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, members[name], compresslevel=9)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(members):
            raise ValueError('Release ZIP verification failed')
        for name, data in members.items():
            if archive.read(name) != data:
                raise ValueError(f'Release ZIP content mismatch: {name}')
    with target.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {filename}\n')
    print(json.dumps({'file':str(target),'bytes':target.stat().st_size,'sha256':checksum,
                      'variant':variant,'hardware_validated':False}, indent=2))
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-dir',type=Path,default=ROOT/'firmware/experimental')
    parser.add_argument('--output',type=Path,default=ROOT/'build/releases')
    args=parser.parse_args()
    package_release(args.bundle_dir,args.output)
