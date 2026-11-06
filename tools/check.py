#!/usr/bin/env python3
"""Run all offline checks; writes an inspectable verification result."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import shutil
import sys
import unittest
from pixels import ROOT
from audit import scan


def main():
    shells=['build.sh','system/bin/cozy-admin','system/bin/cozy-apply','system/bin/cozy-validate',
            'system/bin/adblock_update','system/bin/entware','app/bin/oled_hijack/remote_access.sh',
            'system/www/cozy/cgi-bin/settings.cgi','system/www/cozy/cgi-bin/ui.cgi']
    for path in shells:
        subprocess.run(['sh','-n',str(ROOT/path)],check=True)
    legacy_shells=['system/etc/autorun.sh','system/etc/patchblocked.sh','app/bin/oled_hijack/usb_mode.sh','system/bin/iptables-fixttl-wrapper.sh']
    for path in legacy_shells:
        subprocess.run(['bash','-n',str(ROOT/path)],check=True)
    if shutil.which('shellcheck'):
        subprocess.run(['shellcheck','--shell=busybox','--severity=warning']+[str(ROOT/p) for p in shells if p!='build.sh'],check=True)
    scripts=['system/www/cozy/app.js','system/www/cozy/pixels.js','system/www/cozy/glyphs.js',
             'web/WebApp/common/js/deviceinformation.js.gz','web/WebApp/common/js/cozy-launch.js.gz','web/WebApp/common/js/main.js.gz']
    for path in scripts:
        data=(ROOT/path).read_bytes()
        if path.endswith('.gz'): data=gzip.decompress(data)
        subprocess.run(['node','--check'],input=data,check=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():return 1
    inventory=scan()
    if inventory['parse_errors']:
        print(json.dumps(inventory['parse_errors'],indent=2));return 1
    out=ROOT/'build/verification';out.mkdir(parents=True,exist_ok=True)
    (out/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    builds=[]
    for name in ['first','second']:
        directory=out/name
        subprocess.run([sys.executable,str(ROOT/'tools/build.py'),'--experimental','--output',str(directory)],check=True)
        builds.append({part:hashlib.file_digest((directory/f'{part}-mod.cpio').open('rb'),'sha256').hexdigest() for part in ['app','system','web']})
    if builds[0]!=builds[1]:raise ValueError('Filesystem archives are not reproducible')
    report={'offline_checks_passed':True,'unit_tests':result.testsRun,'shell_files_checked':len(shells)+len(legacy_shells),
            'shellcheck_available':bool(shutil.which('shellcheck')),
            'javascript_files_checked':len(scripts),'inventory':inventory['counts'],
            'archive_sha256':builds[0],'repeat_build_identical':True,'hardware_tested':False,'flash_ready':False}
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0


if __name__=='__main__':sys.exit(main())
