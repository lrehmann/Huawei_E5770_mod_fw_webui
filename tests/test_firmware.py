import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pixels import render, patch_animation
from build import newc_entry, package
from balong import HEADER, crc16, partitions, cpio_entries


class Pixels(unittest.TestCase):
    def test_browser_and_build_renderers_match(self):
        script = '''global.window=globalThis;require('./system/www/cozy/glyphs.js');require('./system/www/cozy/pixels.js');
const result=[];for(const t of ['cat','cloud','sprout'])for(const h of [64,128])for(const bye of [false,true])for(const m of ['HELLO FRIEND',"LUKE'S HOTSPOT!",'ABCDEFGHIJKLMNOPQR'])result.push(CozyPixels.hex(CozyPixels.render(t,m,h,bye)));process.stdout.write(JSON.stringify(result));'''
        actual = json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT))
        expected = [render(t,m,h,bye).hex() for t in ['cat','cloud','sprout'] for h in [64,128]
                    for bye in [False,True] for m in ['HELLO FRIEND',"LUKE'S HOTSPOT!",'ABCDEFGHIJKLMNOPQR']]
        self.assertEqual(actual,expected)

    def test_screen_sizes_and_invalid_messages(self):
        self.assertEqual(len(render(height=64)),1024)
        self.assertEqual(len(render(height=128)),2048)
        self.assertNotEqual(render('cat'),render('cloud'))
        for message in ['x','a'*19,'<script>','♡']:
            with self.assertRaises(ValueError): render(message=message)

    def test_runtime_overlay_matches_build_frames_and_preserves_other_screens(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            for folder,height in [('oled',128),('oled_128x64',64)]:
                source = ROOT/'web/WebApp/common/config'/folder/'animation.xml'
                before = ET.fromstring(source.read_bytes())
                boot,bye = render('sprout','TAKE ME ALONG',height),render('sprout',height=height,goodbye=True)
                (temp/'boot').write_text(boot.hex()+'\n'); (temp/'bye').write_text(bye.hex()+'\n')
                out = subprocess.check_output(['awk','-v','boot='+str(temp/'boot'),'-v','bye='+str(temp/'bye'),'-f',str(ROOT/'system/etc/cozy/animation.awk'),str(source)])
                after = ET.fromstring(out)
                for e in after:
                    original = before.find(e.tag)
                    if e.tag in ('welcome','fast_power_up','fast_power_down','ani_power_off'):
                        frames = e.findall('bitmap/frame')
                        self.assertEqual(len(frames),int(e.findtext('bmp_total')))
                        for frame in frames:
                            data = bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',frame.text))
                            self.assertEqual(data,boot if e.tag in ('welcome','fast_power_up') else bye)
                        for field in ['width','height','sx','sy','frequency','priority']:
                            self.assertEqual(e.findtext(field),original.findtext(field))
                    else:
                        self.assertEqual(ET.tostring(e),ET.tostring(original))


class ProfileValidation(unittest.TestCase):
    def setUp(self):
        self.profile = dict(line.split('=',1) for line in (ROOT/'system/etc/cozy/default.profile').read_text().splitlines())

    def validate(self,profile):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            (temp/'profile').write_bytes(profile.encode())
            source=(ROOT/'system/bin/cozy-validate').read_text().replace('/system/etc/cozy/profile.awk',"'"+str(ROOT/'system/etc/cozy/profile.awk')+"'")
            (temp/'validate').write_text(source)
            return subprocess.run(['/bin/sh',str(temp/'validate'),str(temp/'profile')],capture_output=True).returncode

    def text(self,profile=None):
        return ''.join(k+'='+v+'\n' for k,v in (self.profile if profile is None else profile).items())

    def test_valid(self): self.assertEqual(self.validate(self.text()),0)

    def test_rejects_unknown_duplicate_missing_and_executable_data(self):
        invalid = [self.text()+'theme=cloud\n',self.text()+'command=touch /tmp/pwn\n',self.text().replace('version=1\n','')]
        for key,value in [('label','$(touch /tmp/pwn)'),('label','<img onerror=x>'),('message','BAD\x00NAME'),
                          ('message','A'*19),('theme','../../etc'),('boot64','f'*2047),('boot128','g'*4096),
                          ('sleep_seconds','5'),('poll_seconds','0'),('dim_seconds','-1')]:
            p=copy.copy(self.profile);p[key]=value;invalid.append(self.text(p))
        for text in invalid:
            with self.subTest(profile=text[:70]): self.assertNotEqual(self.validate(text),0)


class NativeWeb(unittest.TestCase):
    def test_custom_page_is_registered_and_launcher_markup_is_balanced(self):
        tree=ET.parse(ROOT/'web/WebApp/common/config/global/config.xml').getroot()
        self.assertEqual(tree.findtext('menu/settings/system/cozy'),'cozy')
        menu=gzip.decompress((ROOT/'web/WebApp/common/html/leftmenu.html.gz').read_bytes()).decode()
        self.assertIn('id="cozy"',menu);self.assertIn('href="cozy.html"',menu)
        class Divs(HTMLParser):
            depth=0
            minimum=0
            def handle_starttag(self,tag,attrs):
                if tag=='div':self.depth+=1
            def handle_endtag(self,tag):
                if tag=='div':self.depth-=1;self.minimum=min(self.minimum,self.depth)
        parser=Divs();parser.feed(gzip.decompress((ROOT/'web/WebApp/common/html/cozy.html.gz').read_bytes()).decode())
        self.assertEqual(parser.depth,0);self.assertEqual(parser.minimum,0)

    def test_native_page_guard_accepts_only_configured_custom_page(self):
        source=gzip.decompress((ROOT/'web/WebApp/common/js/main.js.gz').read_bytes()).decode()
        begin=source.index('function checkModuleEnable(');end=source.index('// document.write',begin)
        script='''const vm=require('vm'),fs=require('fs');const ctx={g_PageUrlTree:{},allowed:true,decisions:[],redirects:[],checkObjectExist:function(tree,...path){this.paths=path;return this.allowed;},checkGotoHome:function(ok){this.decisions.push(ok);},gotoPageWithoutHistory:function(url){this.redirects.push(url);},HOME_PAGE_URL:'home.html'};vm.createContext(ctx);vm.runInContext(fs.readFileSync(0,'utf8'),ctx);ctx.checkModuleEnable('cozy');ctx.allowed=false;ctx.checkModuleEnable('cozy');process.stdout.write(JSON.stringify({decisions:ctx.decisions,redirects:ctx.redirects,paths:ctx.paths}));'''
        # Bind callbacks explicitly: the vendor calls these as ordinary functions.
        script=script.replace('vm.createContext(ctx);','ctx.checkObjectExist=ctx.checkObjectExist.bind(ctx);ctx.checkGotoHome=ctx.checkGotoHome.bind(ctx);ctx.gotoPageWithoutHistory=ctx.gotoPageWithoutHistory.bind(ctx);vm.createContext(ctx);')
        result=json.loads(subprocess.check_output(['node','-e',script],input=source[begin:end].encode()))
        self.assertEqual(result,{'decisions':[True,False],'redirects':[],'paths':['settings','system','cozy']})

    def test_device_information_treats_api_values_as_text(self):
        source=gzip.decompress((ROOT/'web/WebApp/common/js/deviceinformation.js.gz').read_bytes())
        script='''const vm=require('vm'),fs=require('fs');const ctx={document:{},$:function(){return{ready:function(){}};},getConfigData:function(){},common_unknown:'Unknown',common_colon:':',system_label_device_name:'Device name',system_label_my_number:'Phone',wlan_label_lan_mac_address:'LAN',wlan_label_wan_mac_address:'WAN'};vm.createContext(ctx);vm.runInContext(fs.readFileSync(0,'utf8'),ctx);process.stdout.write(ctx.createListForDevice('DeviceName','<img src=x onerror="alert(1)">'));'''
        output=subprocess.check_output(['node','-e',script],input=source).decode()
        self.assertNotIn('<img',output);self.assertIn('&lt;img',output);self.assertIn('&quot;',output)

    def test_sensitive_actions_are_not_in_guest_allowlist(self):
        tree=ET.parse(ROOT/'web/WebApp/common/config/webserver/authority.xml').getroot()
        guests={e.text for e in tree.findall('not_need_login_post_restful_list/uri')}
        for path in ['/device/restore-default','/sdcard/deletefile','/sdcard/fileupload','/mlog/mobile-logger','/online-update/autoupdate-config']:
            self.assertNotIn(path,guests)
        self.assertNotIn('/html/cozy.html',{e.text for e in tree.findall('not_need_login_visited_res_list/uri')})


class ShellHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fakebin = self.root/'bin'; self.fakebin.mkdir()
        self.run = self.root/'run'; self.run.mkdir()
        self.store = self.root/'userdata'; self.store.mkdir()
        self.base = self.root/'etc'; self.base.mkdir()
        for name in ['default.profile','profile.awk','upstream-root-hash.sha256']:
            (self.base/name).write_bytes((ROOT/'system/etc/cozy'/name).read_bytes())
        validator=(ROOT/'system/bin/cozy-validate').read_text().replace('/system/etc/cozy/profile.awk',str(self.base/'profile.awk'))
        (self.fakebin/'cozy-validate').write_text('#!/bin/sh\n'+validator.split('\n',1)[1]);(self.fakebin/'cozy-validate').chmod(0o755)
        self.env = dict(os.environ,PATH=str(self.fakebin)+':'+os.environ['PATH'],MOCK_STATE='0',MOCK_SESSION='SessionID=good',MOCK_BATTERY='7',MOCK_FAIL='0',MOCK_ROOT=str(self.root))
        self.mock('curl', '''import os,sys
from pathlib import Path
a=sys.argv[1:];out=Path(a[a.index('--output')+1]);url=a[-1]
if os.environ.get('MOCK_CURL_FAIL')=='1':sys.exit(22)
if url.endswith('/SesTokInfo'):data='<response><SesInfo>'+os.environ['MOCK_SESSION']+'</SesInfo><TokInfo>abc123</TokInfo></response>'
elif url.endswith('/state-login'):data='<response><State>'+os.environ['MOCK_STATE']+'</State></response>'
elif url.endswith('/monitoring/status'):data='<response><BatteryPercent>'+os.environ['MOCK_BATTERY']+'</BatteryPercent></response>'
else:
 data=''.join('0.0.0.0 ads'+str(i)+'.example.com\\n' for i in range(150))
 if os.environ.get('MOCK_EMPTY')=='1':data='<html>bad gateway</html>'
out.write_text(data)
''')
        self.mock('timeout','''import os,sys
a=sys.argv[1:]
if a[0]=='-t':a=a[2:]
os.execvp(a[0],a)
''')
        self.mock('sha256sum','''import sys,hashlib
print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()+'  -')
''')
        self.mock('xtables-multi','''import os,sys,json
from pathlib import Path
p=Path(os.environ['MOCK_ROOT'])/'rules.json';rules=json.loads(p.read_text()) if p.exists() else []
a=sys.argv[1:];family=a.pop(0);op=a.pop(0);chain=a.pop(0)
if op=='-I' and a and a[0].isdigit():a.pop(0)
rule=[family,chain]+a
if op=='-C':sys.exit(0 if rule in rules else 1)
if os.environ.get('MOCK_FAIL')=='1':sys.exit(1)
if op=='-F':rules=[r for r in rules if r[:2]!=[family,chain]]
elif op=='-D':
 if rule not in rules:sys.exit(1)
 rules.remove(rule)
elif op=='-I':rules.insert(0,rule)
elif op=='-A':rules.append(rule)
p.write_text(json.dumps(rules))
''')
        for command in ['pkill','telnetd','adb','mount','busybox','sleep','ecall','atc']:
            self.mock(command,'''import os,sys
from pathlib import Path
with (Path(os.environ['MOCK_ROOT'])/'commands').open('a') as f:f.write(Path(sys.argv[0]).name+' '+' '.join(sys.argv[1:])+'\\n')
''')
        self.mock('pidof','import sys;sys.exit(1)\n')
        self.mock('ip',"import os;print('inet '+os.environ.get('MOCK_IP','192.168.8.1')+'/24 brd 192.168.8.255 scope global br0')\n")

    def tearDown(self): self.temp.cleanup()

    def mock(self,name,body):
        p=self.fakebin/name;p.write_text('#!'+sys.executable+'\n'+body);p.chmod(0o755)

    def stage(self,path):
        text=(ROOT/path).read_text()
        # Only staged test copies are rewritten. Production has no test-path overrides.
        text=text.replace('/system/etc/cozy',str(self.base)).replace('/data/userdata',str(self.store)).replace('/var/run/cozy-admin',str(self.run))
        text=text.replace('/system/bin/cozy-validate',str(self.fakebin/'cozy-validate'))
        text=text.replace('PATH=/system/bin:/system/xbin:/bin:/sbin','PATH='+self.env['PATH'])
        text=text.replace('/system/etc/dnsmasq-adblock-list.conf',str(self.base/'list'))
        text=text.replace('/system/etc/.adblock.',str(self.base/'.adblock.'))
        text=text.replace('/var/run/cozy-adblock',str(self.root/'adblock'))
        text=text.replace('/proc/kallsyms',str(self.root/'kallsyms')).replace('/var/usb_mode',str(self.root/'usb_mode'))
        p=self.root/(Path(path).name+'.test');p.write_text(text)
        return p


class SettingsCGI(ShellHarness):
    def setUp(self):
        super().setUp();self.script=self.stage('system/www/cozy/cgi-bin/settings.cgi')
        (self.run/'bind-address').write_text('192.168.8.1\n');(self.run/'csrf').write_text('a'*64)

    def request(self,body=None,**changes):
        env=dict(self.env,REQUEST_METHOD='GET' if body is None else 'POST',HTTP_HOST='192.168.8.1:8080',HTTP_COOKIE='SessionID=good',QUERY_STRING='',HTTP_REFERER='http://192.168.8.1:8080/cgi-bin/ui.cgi',CONTENT_TYPE='text/plain;charset=UTF-8')
        data=b'' if body is None else body if isinstance(body,bytes) else body.encode()
        env['CONTENT_LENGTH']=str(len(data));env.update(changes)
        proc=subprocess.run(['/bin/sh',str(self.script)],input=data,env=env,capture_output=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr.decode())
        head,raw=proc.stdout.split(b'\r\n\r\n',1)
        status=re.search(rb'Status: ([0-9]+)',head)
        return int(status[1]) if status else 200,json.loads(raw),head

    def body(self): return 'csrf='+'a'*64+'\n'+(self.base/'default.profile').read_text()

    def test_authenticated_read_is_no_store(self):
        code,data,head=self.request();self.assertEqual(code,200);self.assertEqual(data['csrf'],'a'*64)
        self.assertEqual(data['settings']['theme'],'cat');self.assertIn(b'no-store',head)
        self.assertFalse((self.store/'cozy/profile').exists())

    def test_atomic_save_and_no_write_for_same_profile(self):
        code,data,_=self.request(self.body());self.assertEqual(code,200);self.assertTrue(data['saved'])
        target=self.store/'cozy/profile';self.assertEqual(target.read_text(),(self.base/'default.profile').read_text())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
        before=target.stat().st_mtime_ns;self.request(self.body());self.assertEqual(target.stat().st_mtime_ns,before)
        self.assertEqual(list((self.store/'cozy').iterdir()),[target])

    def test_failed_commit_keeps_previous_profile_and_cleans_staging(self):
        folder=self.store/'cozy';folder.mkdir();target=folder/'profile';target.write_bytes((self.base/'default.profile').read_bytes())
        before=target.read_bytes()
        self.mock('mv','import sys;sys.exit(1)\n')
        code,_,_=self.request(self.body().replace('label=COZY HOTSPOT','label=MY POCKET PAL'))
        self.assertEqual(code,507);self.assertEqual(target.read_bytes(),before)
        self.assertEqual(list(folder.iterdir()),[target])

    def test_unauthenticated_stale_or_rotated_sessions_fail_closed(self):
        for changes in [{'HTTP_COOKIE':''},{'MOCK_STATE':'-1'},{'MOCK_STATE':'1'},{'MOCK_STATE':'<x/>'},{'MOCK_SESSION':'SessionID=replaced'},{'HTTP_COOKIE':'SessionID=good; SessionID=bad'}]:
            with self.subTest(changes=changes):self.assertEqual(self.request(self.body(),**changes)[0],401)
        self.assertFalse((self.store/'cozy/profile').exists())

    def test_upstream_failure_fails_closed(self):
        self.assertEqual(self.request(MOCK_CURL_FAIL='1')[0],503)

    def test_wrong_host_origin_csrf_and_method(self):
        cases=[({'HTTP_HOST':'attacker.example:8080'},403),({'HTTP_REFERER':'http://attacker.example/'},403),
               ({'REQUEST_METHOD':'DELETE'},405),({'CONTENT_TYPE':'application/json'},415)]
        for changes,want in cases:self.assertEqual(self.request(self.body(),**changes)[0],want)
        self.assertEqual(self.request(self.body().replace('csrf=aaa','csrf=baa',1))[0],403)

    def test_rejects_injection_duplicate_and_truncated_input(self):
        for body in [self.body()+'theme=cloud\n',self.body().replace('label=COZY HOTSPOT','label=$(touch PWN)'),self.body().replace('boot64=', 'bad='),self.body().replace('HELLO FRIEND','BAD\x00NAME')]:
            self.assertEqual(self.request(body)[0],400)
        self.assertEqual(self.request(self.body(),CONTENT_LENGTH='8193')[0],413)
        self.assertEqual(self.request(self.body(),CONTENT_LENGTH='nonsense')[0],400)
        self.assertEqual(self.request(self.body(),CONTENT_LENGTH=str(len(self.body())+1))[0],400)
        self.assertEqual(self.request(HTTP_COOKIE='SessionID=$(touch PWN)')[0],401)
        self.assertFalse((self.store/'cozy/profile').exists())

    def test_battery_json_is_always_valid(self):
        for value,expected in [('7',7),('007',7),('100',100),('101',None),('999999999999',None),('x',None)]:
            code,data,_=self.request(QUERY_STRING='status',MOCK_BATTERY=value)
            self.assertEqual(code,200);self.assertEqual(data['battery_percent'],expected)


class RemoteAccess(ShellHarness):
    def setUp(self):
        super().setUp();self.script=self.stage('app/bin/oled_hijack/remote_access.sh')

    def execute(self,action='boot',**changes):
        return subprocess.run(['/bin/sh',str(self.script),action],env=dict(self.env,**changes),capture_output=True,timeout=10)

    def commands(self): return (self.root/'commands').read_text() if (self.root/'commands').exists() else ''

    def test_default_disables_debug_even_with_stale_enabled_mode(self):
        (self.store/'remote_access').write_text('2\n')
        self.assertEqual(self.execute().returncode,0)
        self.assertEqual((self.store/'remote_access').read_text(),'0\n')
        commands=self.commands();self.assertIn('pkill telnetd',commands);self.assertNotIn('telnetd -l',commands)
        rules=json.loads((self.root/'rules.json').read_text());self.assertIn(['iptables','COZY_DEBUG','-j','REJECT'],rules)

    def test_original_shared_root_password_is_rejected(self):
        (self.store/'cozy_debug_enable').touch()
        original=subprocess.check_output(['git','show','a4b7711f7564bfd408ce925564b128e05c20313d:system/usr/default_files/passwd_def'],cwd=ROOT)
        (self.store/'passwd').write_bytes(original)
        (self.store/'remote_access').write_text('2\n')
        self.assertEqual(self.execute('get').returncode,0)
        self.assertNotEqual(self.execute('set_next').returncode,0)

    def test_unique_password_and_opt_in_allow_lan_only_debug(self):
        (self.store/'cozy_debug_enable').touch();(self.store/'passwd').write_text('root:$6$unique$example:0:0::/:/bin/ash\n')
        (self.store/'remote_access').write_text('2\n')
        self.assertEqual(self.execute().returncode,0)
        self.assertIn('telnetd -l',self.commands());self.assertIn('adb ',self.commands())
        rules=json.loads((self.root/'rules.json').read_text())
        for rule in rules:
            if rule[:2]==['iptables','COZY_DEBUG'] and rule[-1]=='ACCEPT': self.assertIn('br0',rule)

    def test_firewall_failure_never_starts_listeners(self):
        (self.store/'cozy_debug_enable').touch();(self.store/'passwd').write_text('root:$6$unique$example:0:0::/:/bin/ash\n')
        (self.store/'remote_access').write_text('2\n')
        self.assertNotEqual(self.execute(MOCK_FAIL='1').returncode,0)
        self.assertNotIn('telnetd -l',self.commands());self.assertIn('pkill adbd',self.commands())


class AdminService(ShellHarness):
    def test_no_listener_if_firewall_fails(self):
        script=self.stage('system/bin/cozy-admin')
        p=subprocess.run(['/bin/sh',str(script),'start'],env=dict(self.env,MOCK_FAIL='1'),capture_output=True,timeout=10)
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.root/'commands').exists())

    def test_listener_binds_only_private_lan_and_uses_explicit_root(self):
        script=self.stage('system/bin/cozy-admin')
        p=subprocess.run(['/bin/sh',str(script),'start'],env=self.env,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        commands=(self.root/'commands').read_text()
        self.assertIn('httpd -f -p 192.168.8.1:8080 -h /system/www/cozy',commands)
        self.assertEqual((self.run/'csrf').stat().st_mode & 0o777,0o600)


class KernelPatchGates(ShellHarness):
    def setUp(self):
        super().setUp()
        (self.root/'kallsyms').write_text('00001000 r page00\n00002000 T g_bAtDataLocked\n00003000 T nv_readEx\n00004000 T nv_writeEx\n')

    def test_no_kernel_memory_writes_by_default(self):
        script=self.stage('system/etc/patchblocked.sh')
        p=subprocess.run(['/bin/bash',str(script),'boot'],env=self.env,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse((self.root/'commands').exists())

    def test_ecm_patch_requires_its_own_opt_in(self):
        (self.store/'cozy_usb_ecm_patch_enable').touch()
        script=self.stage('system/etc/patchblocked.sh')
        p=subprocess.run(['/bin/bash',str(script),'boot'],env=self.env,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        lines=(self.root/'commands').read_text().splitlines();self.assertEqual(len(lines),4)

    def test_usb_menu_skips_unprovisioned_ecm_mode(self):
        (self.root/'usb_mode').write_text('1\n')
        script=self.stage('app/bin/oled_hijack/usb_mode.sh')
        p=subprocess.run(['/bin/bash',str(script),'set_next'],env=self.env,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual((self.root/'usb_mode').read_text(),'3\n')


class Adblock(ShellHarness):
    def run_update(self,**changes):
        script=self.stage('system/bin/adblock_update')
        return subprocess.run(['/bin/sh',str(script)],env=dict(self.env,**changes),capture_output=True,timeout=10)

    def test_failed_or_empty_download_preserves_last_good_list(self):
        target=self.base/'list';target.write_text('last good\n')
        for changes in [{'MOCK_CURL_FAIL':'1'},{'MOCK_EMPTY':'1'}]:
            self.assertNotEqual(self.run_update(**changes).returncode,0)
            self.assertEqual(target.read_text(),'last good\n')
        self.assertFalse((self.root/'commands').exists())

    def test_success_commits_validated_list_and_restores_readonly_mount(self):
        (self.base/'list').write_text('old list\n')
        p=self.run_update();self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(len((self.base/'list').read_text().splitlines()),150)
        commands=(self.root/'commands').read_text();self.assertIn('remount,rw',commands);self.assertIn('remount,ro',commands)


class Containers(unittest.TestCase):
    def test_crc_known_vector(self): self.assertEqual(crc16(b'123456789'),0x906e)

    def container(self,payload=b'test'):
        fields=[0xa55aaa55,100,1,b'\0'*8,0x590000,len(payload),b'\0'*16,b'\0'*16,b'test'+b'\0'*28,0,4096]
        head=bytearray(HEADER.pack(*fields));head[92:94]=struct.pack('<H',crc16(head))
        return bytes(92)+head+struct.pack('<H',crc16(payload))+payload

    def test_valid_and_corrupt_container(self):
        data=self.container();parts=partitions(data);self.assertEqual(len(parts),1)
        self.assertTrue(parts[0].header_crc_ok);self.assertTrue(parts[0].block_crc_ok)
        parts=partitions(data[:-1]+b'X');self.assertFalse(parts[0].block_crc_ok)
        with self.assertRaises(ValueError): partitions(data[:-2])

    def test_deterministic_archives_preserve_links_and_root_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);source=temp/'source';source.mkdir();(source/'file').write_text('test')
            (source/'link').symlink_to('/system/bin/busybox')
            package(source,temp/'one.cpio',1234);package(source,temp/'two.cpio',1234)
            self.assertEqual((temp/'one.cpio').read_bytes(),(temp/'two.cpio').read_bytes())
            items={e['name']:e for e in cpio_entries((temp/'one.cpio').read_bytes())}
            self.assertEqual(items['link']['data'],b'/system/bin/busybox');self.assertTrue(stat.S_ISLNK(items['link']['mode']))
            self.assertEqual(stat.S_IMODE(items['link']['mode']),0o777)
            self.assertTrue(all(e['uid']==e['gid']==0 for e in items.values()))

    def test_reader_rejects_unsafe_names_and_truncated_payloads(self):
        stream=io.BytesIO();newc_entry(stream,'../escape',b'x',0o100644,1,1)
        with self.assertRaises(ValueError): list(cpio_entries(stream.getvalue()))


if __name__=='__main__': unittest.main()
