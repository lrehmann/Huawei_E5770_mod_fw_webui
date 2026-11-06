"""Build and verify complete experimental E5770 firmware containers offline.

Only the three filesystem partitions are rebuilt. The original transport
prefix, embedded signature metadata, and all other partition bytes are retained.
No OEM signature is created or authenticated, and this module has no device I/O.
"""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import stat
import struct
from balong import HEADER, partitions, cpio_entries
from build import newc_entry
from pixels import ROOT

MAX_FS_BYTES = 64 * 1024 * 1024  # Parser/build bound, not a flash-capacity claim.
FS_NAMES = ('app', 'system', 'web')
ADMIN_MARKER = 'etc/cozy/admin-enabled'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or '\0' in name:
        raise ValueError(f'Unsafe firmware path: {name!r}')
    return path.as_posix()


def load_layout():
    layout = json.loads((ROOT / 'firmware/base-layout.json').read_text())
    required = {
        'firmware': [0x110000, 0x200000, 0x10000, 0x90000, 0x220000, 0x230000,
                     0x240000, 0x250000, 0x590000, 0x5a0000],
        'webui': [0xa0000, 0xb0000, 0x5b0000],
    }
    for kind, codes in required.items():
        if [p['code'] for p in layout['images'][kind]['partitions']] != codes:
            raise ValueError(f'Incomplete or wrong E5770 base layout: {kind}')
    return layout


def collect_filesystem(name, layout, admin_enabled=False, root=ROOT):
    source = root / name
    baseline = {e['name']: e for e in layout['filesystems'][name]}
    deleted = set(layout['deleted_paths'].get(name, []))
    for path in deleted:
        safe_name(path)
        if path not in baseline or path == '.':
            raise ValueError(f'Unknown deletion in {name}: {path}')

    def removed(path):
        return any(path == d or path.startswith(d + '/') for d in deleted)

    current = {'.': source}
    for p in source.rglob('*'):
        current[p.relative_to(source).as_posix()] = p
    result = {}
    total = 0
    for path in sorted(set(baseline) | set(current)):
        safe_name(path)
        if removed(path):
            continue
        # This build-only opt-in cannot enter the default image accidentally.
        if name == 'system' and path == ADMIN_MARKER:
            raise ValueError('The admin marker is generated only by --enable-admin; remove it from the source tree')
        old = baseline.get(path)
        p = current.get(path)
        if p is None:
            if not stat.S_ISDIR(old['mode']):
                raise ValueError(f'Missing base file {name}/{path}; review an explicit deleted_paths entry')
            data = b''
            mode = old['mode']
        else:
            s = p.lstat()
            kind = stat.S_IFMT(s.st_mode)
            if old and kind != stat.S_IFMT(old['mode']):
                raise ValueError(f'Unreviewed object-type change: {name}/{path}')
            if stat.S_ISLNK(kind):
                data = os.readlink(p).encode()
            elif stat.S_ISREG(kind):
                if s.st_size > MAX_FS_BYTES - total:
                    raise ValueError(f'Filesystem size bound exceeded in {name}')
                data = p.read_bytes()
            elif stat.S_ISDIR(kind):
                data = b''
            else:
                raise ValueError(f'Unsupported filesystem object: {name}/{path}')
            mode = old['mode'] if old else kind | (stat.S_IMODE(s.st_mode) & 0o777)
            if stat.S_ISLNK(mode):
                mode = stat.S_IFLNK | 0o777
        total += len(data)
        if total > MAX_FS_BYTES:
            raise ValueError(f'Filesystem size bound exceeded in {name}')
        result[path] = {'name': path, 'mode': mode, 'uid': old['uid'] if old else 0,
                        'gid': old['gid'] if old else 0, 'data': data}
    if name == 'system' and admin_enabled:
        result[ADMIN_MARKER] = {'name': ADMIN_MARKER, 'mode': stat.S_IFREG | 0o644,
                                'uid': 0, 'gid': 0, 'data': b'1\n'}
    return [result[path] for path in sorted(result)]


def make_cpio(entries, epoch):
    stream = io.BytesIO()
    for i, e in enumerate(entries, 1):
        newc_entry(stream, e['name'], e['data'], e['mode'], i, epoch, e['uid'], e['gid'])
    newc_entry(stream, 'TRAILER!!!', b'', 0, len(entries) + 1, epoch)
    stream.write(b'\0' * ((-stream.tell()) % 512))
    return stream.getvalue()


def read_cpio(data):
    if len(data) > MAX_FS_BYTES:
        raise ValueError('Filesystem archive is too large')
    iterator = cpio_entries(data)
    entries = []
    while True:
        try:
            entries.append(next(iterator))
        except StopIteration as done:
            end = done.value
            break
    if not isinstance(end, int) or any(data[end:]):
        raise ValueError('Unexpected data after the CPIO trailer')
    names = [e['name'] for e in entries]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate CPIO paths')
    return entries


def encode_partition(header, payload):
    fields = list(HEADER.unpack(header))
    blocksize = fields[-1]
    if not 1 <= blocksize <= 16 * 1024 * 1024:
        raise ValueError('Unsupported CRC block size')
    from balong import crc16
    checksums = [crc16(payload[i:i + blocksize]) for i in range(0, len(payload), blocksize)]
    fields[1] = HEADER.size + 2 * len(checksums)
    fields[5] = len(payload)
    fields[9] = 0
    fields[9] = crc16(HEADER.pack(*fields))
    result = HEADER.pack(*fields) + struct.pack('<' + 'H' * len(checksums), *checksums) + payload
    return result + b'\0' * ((-len(result)) % 4)


def validate_container(data, image_layout):
    if data[:92].hex() != image_layout['prefix_hex']:
        raise ValueError('Wrong Huawei transport prefix')
    parsed = partitions(data)
    expected = image_layout['partitions']
    if len(parsed) != len(expected):
        raise ValueError('Missing or extra firmware partitions')
    for part, spec in zip(parsed, expected):
        if part.code != spec['code'] or part.name != spec['name']:
            raise ValueError('Firmware partition order/identity changed')
        if not part.header_crc_ok or not part.block_crc_ok:
            raise ValueError(f'CRC failure in {part.name}')
        actual_header = HEADER.unpack_from(data, part.offset)
        base_header = HEADER.unpack(bytes.fromhex(spec['header_hex']))
        for index, (actual, base) in enumerate(zip(actual_header, base_header)):
            if index not in (1, 5, 9) and actual != base:
                raise ValueError(f'Unexpected {part.name} header metadata change')
        if not spec['modified'] and digest(part.data) != spec['sha256']:
            raise ValueError(f'Immutable base component changed: {part.name}')
    last = parsed[-1]
    end = last.offset + HEADER.unpack_from(data, last.offset)[1] + len(last.data)
    aligned = (end + 3) & ~3
    if aligned != len(data) or any(data[end:aligned]):
        raise ValueError('Unexpected container trailer or padding')
    return parsed


def assemble_container(template, image_layout, filesystems):
    parsed = validate_container(template, image_layout)
    output = bytearray(template[:92])
    for i, (part, spec) in enumerate(zip(parsed, image_layout['partitions'])):
        if spec['modified']:
            output.extend(encode_partition(bytes.fromhex(spec['header_hex']), filesystems[part.name]))
        else:
            end = parsed[i + 1].offset if i + 1 < len(parsed) else len(template)
            output.extend(template[part.offset:end])
    data = bytes(output)
    validate_container(data, image_layout)
    return data


def filesystem_fingerprint(entries):
    items = []
    for e in entries:
        items.append({'name': e['name'], 'mode': e['mode'], 'uid': e['uid'],
                      'gid': e['gid'], 'bytes': len(e['data']), 'sha256': digest(e['data'])})
    return digest(json.dumps(items, sort_keys=True, separators=(',', ':')).encode())


def compare_filesystem(payload, expected, name):
    actual = read_cpio(payload)
    actual_map = {e['name']: e for e in actual}
    expected_map = {e['name']: e for e in expected}
    if set(actual_map) != set(expected_map):
        raise ValueError(f'{name} filesystem paths do not match current source and base layout')
    for path, want in expected_map.items():
        got = actual_map[path]
        for field in ('mode', 'uid', 'gid', 'data'):
            if got[field] != want[field]:
                raise ValueError(f'{name}/{path}: {field} does not match source')


def image_names(version, admin_enabled=False):
    if not version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz.-' for c in version):
        raise ValueError('Invalid release version')
    label = '_ADMIN' if admin_enabled else ''
    return {'firmware': f'Cozy_E5770_{version}{label}_FW.BIN',
            'webui': f'Cozy_E5770_{version}_WEBUI.BIN'}


def verify_bundle(directory, layout=None, root=ROOT):
    layout = load_layout() if layout is None else layout
    manifest = json.loads((directory / 'MANIFEST.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('format') != 'cozy-complete-experimental-firmware':
        raise ValueError('Unknown firmware bundle manifest')
    if manifest.get('complete_flash_set') is not True or any(manifest.get(k) is not False for k in
        ('hardware_validated', 'oem_signature_validated', 'direct_stock_install_validated')):
        raise ValueError('Unexpected firmware validation/support claims')
    admin = manifest.get('admin_enabled_by_default')
    if not isinstance(admin, bool):
        raise ValueError('Invalid companion default')
    version = (root / 'firmware/VERSION').read_text().strip()
    if manifest['version'] != version:
        raise ValueError('Bundle version does not match the source version')
    names = image_names(version, admin)
    epoch = int(manifest['source_date_epoch'])
    if not 0 <= epoch <= 0xffffffff:
        raise ValueError('Invalid archive epoch')
    expected_fs = {name: collect_filesystem(name, layout, admin, root) for name in FS_NAMES}
    if manifest['filesystem_source_sha256'] != {name: filesystem_fingerprint(entries) for name, entries in expected_fs.items()}:
        raise ValueError('Firmware payload/source fingerprint mismatch')
    summary = {}
    for kind in ('firmware', 'webui'):
        spec = manifest['images'][kind]
        if spec['file'] != names[kind] or Path(spec['file']).name != spec['file']:
            raise ValueError('Unexpected image filename')
        data = (directory / spec['file']).read_bytes()
        if len(data) != spec['bytes'] or digest(data) != spec['sha256']:
            raise ValueError(f'{kind} image SHA-256/size mismatch')
        parsed = validate_container(data, layout['images'][kind])
        rows = [{'name': p.name, 'code': f'{p.code:08x}', 'bytes': len(p.data),
                 'sha256': digest(p.data), 'changed': p.name in FS_NAMES} for p in parsed]
        if spec['partitions'] != rows:
            raise ValueError(f'{kind} partition manifest mismatch')
        for part in parsed:
            if part.name in FS_NAMES:
                compare_filesystem(part.data, expected_fs[part.name], part.name)
                # Also verifies timestamps, inode ordering and archive padding.
                if part.data != make_cpio(expected_fs[part.name], epoch):
                    raise ValueError(f'{part.name} archive encoding is not canonical')
        summary[kind] = {'file': spec['file'], 'sha256': spec['sha256'], 'partitions': len(parsed)}
    sums = ''.join(f"{summary[kind]['sha256']}  {summary[kind]['file']}\n" for kind in ('firmware', 'webui'))
    if (directory / 'SHA256SUMS').read_text() != sums:
        raise ValueError('SHA256SUMS does not match the manifest')
    return {'verified': True, 'version': version, 'images': summary,
            'admin_enabled_by_default': admin, 'hardware_validated': False, 'oem_signature_validated': False}
