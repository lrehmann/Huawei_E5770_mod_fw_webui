#!/usr/bin/env python3
"""Fetch/check the pinned upstream base and extract only its two named images."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlsplit
from pixels import ROOT


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        if urlsplit(url).scheme != 'https':
            raise ValueError('Refusing a non-HTTPS firmware redirect')
        return super().redirect_request(request, fp, code, message, headers, url)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extractor(archive, member):
    for binary in ('bsdtar', 'tar'):
        command = shutil.which(binary)
        if command:
            version = subprocess.check_output([command, '--version'], text=True)
            if 'bsdtar' in version.lower():
                return [command, '-xOf', str(archive), member]
    for binary in ('7zz', '7z'):
        command = shutil.which(binary)
        if command:
            return [command, 'e', '-so', str(archive), member]
    raise ValueError('Install libarchive-tools (bsdtar) or 7-Zip to extract the upstream .7z archive')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='use an already-downloaded upstream archive')
    parser.add_argument('--output', type=Path, default=ROOT/'.cache/releases/unpacked')
    args = parser.parse_args()
    lock = json.loads((ROOT/'firmware/base-download.json').read_text())
    layout = json.loads((ROOT/'firmware/base-layout.json').read_text())
    cache = ROOT/'.cache/releases'
    cache.mkdir(parents=True, exist_ok=True)
    archive = args.archive.resolve() if args.archive else cache/lock['archive_file']
    if not archive.exists():
        if args.archive:
            raise FileNotFoundError(archive)
        request = urllib.request.Request(lock['url'], headers={'User-Agent': 'Cozy-E5770-base-fetch/1'})
        opener = urllib.request.build_opener(HTTPSRedirect())
        fd, temporary = tempfile.mkstemp(prefix='base-download-', dir=cache)
        try:
            with os.fdopen(fd, 'wb') as target, opener.open(request, timeout=60) as response:
                count = 0
                while chunk := response.read(1024*1024):
                    count += len(chunk)
                    if count > lock['bytes']:
                        raise ValueError('Upstream archive exceeds its pinned size')
                    target.write(chunk)
            if Path(temporary).stat().st_size != lock['bytes'] or sha(Path(temporary)) != lock['sha256']:
                raise ValueError('Upstream archive checksum/size mismatch')
            os.replace(temporary, archive)
        finally:
            Path(temporary).unlink(missing_ok=True)
    if archive.stat().st_size != lock['bytes'] or sha(archive) != lock['sha256']:
        raise ValueError('Upstream archive checksum/size mismatch')
    args.output.mkdir(parents=True, exist_ok=True)
    for kind in ('firmware', 'webui'):
        spec = layout['images'][kind]
        target = args.output/spec['file']
        if target.exists() and sha(target) == spec['sha256']:
            print(f'Verified {target}')
            continue
        fd, temporary = tempfile.mkstemp(prefix='base-image-', dir=args.output)
        try:
            with os.fdopen(fd, 'wb') as stream:
                subprocess.run(extractor(archive.resolve(), spec['file']), stdout=stream, check=True, timeout=120)
            if sha(Path(temporary)) != spec['sha256']:
                raise ValueError(f'Extracted image checksum mismatch: {spec["file"]}')
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print(f'Verified {target}')


if __name__ == '__main__':
    main()
