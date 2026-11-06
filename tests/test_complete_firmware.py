from pathlib import Path
import copy
import json
import stat
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from balong import HEADER, partitions
from firmware import (ADMIN_MARKER, assemble_container, collect_filesystem, compare_filesystem,
                      digest, encode_partition, filesystem_fingerprint, make_cpio,
                      read_cpio, validate_container)


def entry(name, data=b'', mode=stat.S_IFREG|0o644, uid=0, gid=0):
    return {'name':name,'data':data,'mode':mode,'uid':uid,'gid':gid}


def fixture_part(name, code, payload, modified=False):
    header = HEADER.pack(0xa55aaa55, HEADER.size, 1, bytes(8), code, len(payload),
                         bytes(16), bytes(16), b'fixture'+bytes(25), 0, 4096)
    spec = {'name':name,'code':code,'sha256':digest(payload),'bytes':len(payload),
            'header_hex':header.hex(),'modified':modified}
    return spec, encode_partition(header, payload)


class ContainerAssembly(unittest.TestCase):
    def setUp(self):
        immutable, first = fixture_part('fastboot', 0x110000, b'unchanged boot component')
        self.old = make_cpio([entry('.',mode=stat.S_IFDIR|0o755),entry('version',b'old')],1234)
        filesystem, second = fixture_part('system',0x590000,self.old,True)
        self.layout = {'prefix_hex':(b'\x09'+bytes(91)).hex(),'partitions':[immutable,filesystem]}
        self.template = bytes.fromhex(self.layout['prefix_hex'])+first+second

    def test_complete_template_roundtrip_preserves_boot_component_and_replaces_filesystem(self):
        new = make_cpio([entry('.',mode=stat.S_IFDIR|0o755),entry('version',b'new')],1234)
        result = assemble_container(self.template,self.layout,{'system':new})
        parts = partitions(result)
        self.assertEqual(parts[0].data,b'unchanged boot component')
        self.assertEqual(result[:parts[1].offset],self.template[:parts[1].offset])
        self.assertEqual(parts[1].data,new)
        self.assertTrue(all(p.header_crc_ok and p.block_crc_ok for p in parts))

    def test_recomputed_crc_does_not_authorize_changed_kernel_or_boot_bytes(self):
        bad_header = bytes.fromhex(self.layout['partitions'][0]['header_hex'])
        tampered = bytes.fromhex(self.layout['prefix_hex'])+encode_partition(bad_header,b'tampered boot component')
        tampered += encode_partition(bytes.fromhex(self.layout['partitions'][1]['header_hex']),self.old)
        with self.assertRaisesRegex(ValueError,'Immutable base'):
            validate_container(tampered,self.layout)

    def test_rejects_truncated_missing_reordered_and_wrong_type_containers(self):
        first = fixture_part('fastboot',0x110000,b'unchanged boot component')[1]
        second = fixture_part('system',0x590000,self.old,True)[1]
        prefix=bytes.fromhex(self.layout['prefix_hex'])
        cases=[self.template[:-3],prefix+first,prefix+second+first,b'\x0f'+self.template[1:],self.template+b'junk']
        for data in cases:
            with self.subTest(length=len(data)),self.assertRaises(ValueError):validate_container(data,self.layout)

    def test_rejects_changed_version_header_even_with_valid_crc(self):
        fields=list(HEADER.unpack(bytes.fromhex(self.layout['partitions'][1]['header_hex'])))
        fields[8]=b'unreviewed'+bytes(22)
        first=fixture_part('fastboot',0x110000,b'unchanged boot component')[1]
        data=bytes.fromhex(self.layout['prefix_hex'])+first+encode_partition(HEADER.pack(*fields),self.old)
        with self.assertRaisesRegex(ValueError,'header metadata'):validate_container(data,self.layout)


class FilesystemCompleteness(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'app').mkdir()
        (self.root/'app/required').write_bytes(b'required source file')
        self.layout={'filesystems':{'app':[
            entry('.',mode=stat.S_IFDIR|0o775,uid=1000,gid=1000),
            entry('webroot',mode=stat.S_IFDIR|0o775,uid=1000,gid=1000),
            entry('required',b'required source file',uid=1000,gid=1000)]},'deleted_paths':{'app':[]}}

    def tearDown(self):self.temp.cleanup()

    def test_restores_missing_empty_mountpoint_and_preserves_vendor_owners(self):
        (self.root/'app/cozy-new').write_text('new file')
        entries={e['name']:e for e in collect_filesystem('app',self.layout,root=self.root)}
        self.assertTrue(stat.S_ISDIR(entries['webroot']['mode']))
        self.assertEqual((entries['webroot']['uid'],entries['webroot']['gid']),(1000,1000))
        self.assertEqual(entries['required']['uid'],1000)
        self.assertEqual(entries['cozy-new']['uid'],0)
        self.assertEqual(entries['webroot']['mode']&0o777,0o775)

    def test_missing_base_file_requires_explicit_reviewed_deletion(self):
        (self.root/'app/required').unlink()
        with self.assertRaisesRegex(ValueError,'Missing base file'):
            collect_filesystem('app',self.layout,root=self.root)
        self.layout['deleted_paths']['app']=['required']
        self.assertNotIn('required',{e['name'] for e in collect_filesystem('app',self.layout,root=self.root)})

    def test_object_type_changes_and_unsafe_deletion_are_rejected(self):
        (self.root/'app/required').unlink();(self.root/'app/required').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError,'object-type'):
            collect_filesystem('app',self.layout,root=self.root)
        self.layout['deleted_paths']['app']=['../outside']
        with self.assertRaises(ValueError):collect_filesystem('app',self.layout,root=self.root)

    def test_cpio_comparison_checks_permissions_owners_paths_and_bytes(self):
        entries=collect_filesystem('app',self.layout,root=self.root)
        compare_filesystem(make_cpio(entries,1234),entries,'app')
        for field,value in [('mode',stat.S_IFREG|0o777),('uid',999),('gid',999),('data',b'changed')]:
            bad=copy.deepcopy(entries);next(e for e in bad if e['name']=='required')[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare_filesystem(make_cpio(bad,1234),entries,'app')
        with self.assertRaises(ValueError):compare_filesystem(make_cpio(entries[:-1],1234),entries,'app')

    def test_duplicate_paths_and_hidden_trailing_data_are_rejected(self):
        e=entry('duplicate',b'data')
        with self.assertRaisesRegex(ValueError,'Duplicate'):read_cpio(make_cpio([e,e],1234))
        with self.assertRaisesRegex(ValueError,'trailer'):read_cpio(make_cpio([e],1234)+b'hidden')

    def test_admin_autostart_requires_explicit_build_opt_in(self):
        (self.root/'system/etc/cozy').mkdir(parents=True)
        layout={'filesystems':{'system':[entry('.',mode=stat.S_IFDIR|0o755)]},'deleted_paths':{'system':[]}}
        default={e['name']:e for e in collect_filesystem('system',layout,False,self.root)}
        enabled={e['name']:e for e in collect_filesystem('system',layout,True,self.root)}
        self.assertNotIn(ADMIN_MARKER,default)
        self.assertEqual(enabled[ADMIN_MARKER]['data'],b'1\n')
        self.assertNotEqual(filesystem_fingerprint(list(default.values())),filesystem_fingerprint(list(enabled.values())))
        (self.root/'system'/ADMIN_MARKER).write_text('1\n')
        with self.assertRaisesRegex(ValueError,'generated only'):
            collect_filesystem('system',layout,False,self.root)


if __name__=='__main__':unittest.main()
