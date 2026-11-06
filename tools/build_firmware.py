#!/usr/bin/env python3
"""Assemble or verify the complete experimental firmware + WebUI flash set."""
from pathlib import Path
import argparse
import json
import os
import tempfile
from build import validate_sources
from firmware import (ROOT, FS_NAMES, load_layout, digest, collect_filesystem,
                      make_cpio, assemble_container, filesystem_fingerprint,
                      image_names, verify_bundle, validate_container)


def templates(base_dir, template_dir, layout):
    result = {}
    manifest = None
    if base_dir is None:
        manifest = json.loads((template_dir / 'MANIFEST.json').read_text())
    for kind in ('firmware', 'webui'):
        spec = layout['images'][kind] if base_dir is not None else manifest['images'][kind]
        name = spec['file']
        if Path(name).name != name:
            raise ValueError('Unsafe template filename')
        directory = base_dir if base_dir is not None else template_dir
        data = (directory / name).read_bytes()
        if digest(data) != spec['sha256']:
            raise ValueError(f'Template checksum mismatch: {name}')
        validate_container(data, layout['images'][kind])
        result[kind] = data
    return result


def build_set(base_dir, template_dir, output, admin_enabled=False):
    validate_sources()
    layout = load_layout()
    version = (ROOT / 'firmware/VERSION').read_text().strip()
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', (ROOT / 'system/etc/cozy/build-epoch').read_text().strip()))
    if not 0 <= epoch <= 0xffffffff:
        raise ValueError('Invalid SOURCE_DATE_EPOCH')
    if base_dir is None and output.resolve() == template_dir.resolve():
        raise ValueError('Build into a separate directory, then review the result before replacing templates')
    if any(output.resolve() == ROOT/p or ROOT/p in output.resolve().parents for p in FS_NAMES):
        raise ValueError('Output must be outside the source filesystem trees')
    original = templates(base_dir, template_dir, layout)
    entries = {name: collect_filesystem(name, layout, admin_enabled) for name in FS_NAMES}
    filesystems = {name: make_cpio(value, epoch) for name, value in entries.items()}
    names = image_names(version, admin_enabled)
    manifest = {
        'schema_version': 1, 'format': 'cozy-complete-experimental-firmware',
        'version': version, 'base_release': layout['base_release'],
        'firmware_version': layout['firmware_version'], 'webui_version': layout['webui_version'],
        'source_date_epoch': epoch, 'admin_enabled_by_default': admin_enabled,
        'filesystem_source_sha256': {name: filesystem_fingerprint(value) for name, value in entries.items()},
        'complete_flash_set': True, 'hardware_validated': False, 'oem_signature_validated': False,
        'direct_stock_install_validated': False,
        'installation_precondition': 'Compatible E5770 modified/technological firmware and a verified recovery path',
        'images': {},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cozy-firmware-', dir=output.parent) as temp:
        staging = Path(temp)
        for kind in ('firmware', 'webui'):
            data = assemble_container(original[kind], layout['images'][kind], filesystems)
            parsed = validate_container(data, layout['images'][kind])
            (staging / names[kind]).write_bytes(data)
            manifest['images'][kind] = {
                'file': names[kind], 'bytes': len(data), 'sha256': digest(data),
                'partitions': [{'name': p.name, 'code': f'{p.code:08x}', 'bytes': len(p.data),
                                'sha256': digest(p.data), 'changed': p.name in FS_NAMES} for p in parsed],
            }
        (staging / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staging / 'SHA256SUMS').write_text(''.join(f"{manifest['images'][kind]['sha256']}  {names[kind]}\n"
                                                 for kind in ('firmware', 'webui')))
        report = verify_bundle(staging, layout)
        output.mkdir(parents=True, exist_ok=True)
        for file in staging.iterdir():
            os.replace(file, output / file.name)
    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experimental', action='store_true', help='acknowledge untested experimental firmware assembly')
    parser.add_argument('--base-dir', type=Path, help='directory containing the two original, pinned upstream BIN files')
    parser.add_argument('--template-dir', type=Path, default=ROOT/'firmware/experimental', help='committed complete images used for unchanged base components')
    parser.add_argument('--output', type=Path, default=ROOT/'build/complete-firmware')
    parser.add_argument('--enable-admin', action='store_true', help='explicitly opt into starting the experimental native-authenticated LAN companion at boot')
    parser.add_argument('--check', action='store_true', help='verify the template bundle against source, base hashes, CRCs, and filesystem metadata without device access')
    args = parser.parse_args()
    try:
        if args.check:
            if args.base_dir or args.enable_admin:
                parser.error('--check cannot be combined with --base-dir or --enable-admin')
            validate_sources()
            print(json.dumps(verify_bundle(args.template_dir), indent=2))
        else:
            if not args.experimental:
                parser.error('--experimental is required; image assembly does not establish hardware compatibility')
            build_set(args.base_dir, args.template_dir, args.output, args.enable_admin)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'Firmware verification/build failed: {exc}\n')


if __name__ == '__main__':
    main()
