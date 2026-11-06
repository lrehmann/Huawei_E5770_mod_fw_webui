(function () {
  'use strict';
  if (window.top !== window.self) { document.body.textContent = 'Open Cozy settings in a separate window.'; return; }
  var keys = ['version','theme','label','message','dim_seconds','sleep_seconds','poll_seconds','boot64','boot128'];
  var settings = {version:'1',theme:'cat',label:'COZY HOTSPOT',message:'HELLO FRIEND',dim_seconds:'10',sleep_seconds:'15',poll_seconds:'30'};
  var preview = new URLSearchParams(window.location.search).get('preview') === '1';
  var csrf = '', ready = false, saving = false, screen = 'hello', timer, failures = 0;
  var el = function (id) { return document.getElementById(id); };
  var api = '/cgi-bin/settings.cgi';
  el('router-link').href = 'http://' + window.location.hostname + '/html/home.html';
  function notify(message, error) { el('connection').textContent = message; el('connection').className = 'connection' + (error ? ' error' : ''); }
  function fields() {
    ['label','message','dim_seconds','sleep_seconds','poll_seconds'].forEach(function (key) { settings[key] = el(key).value; });
    settings.label = settings.label.toUpperCase(); settings.message = settings.message.toUpperCase();
  }
  function validate(s) {
    if (s.version !== '1' || ['cat','cloud','sprout'].indexOf(s.theme) < 0 ||
        !/^[A-Z0-9 ._-]{1,16}$/.test(s.label) || !/^[A-Z0-9 !?.'_-]{1,18}$/.test(s.message) ||
        !/^[0-9]+$/.test(s.dim_seconds) || +s.dim_seconds < 1 || +s.dim_seconds > 60 ||
        !/^[0-9]+$/.test(s.sleep_seconds) || +s.sleep_seconds < +s.dim_seconds || +s.sleep_seconds > 300 ||
        ['5','10','30','60'].indexOf(s.poll_seconds) < 0) {
      throw new Error('Check your name, message and screen times. Screen off must be at least as long as dim.');
    }
  }
  function draw() {
    fields();
    el('device-label').textContent = settings.label || 'YOUR POCKET PAL';
    el('message-count').textContent = settings.message.length;
    try {
      validate(settings);
      var bytes = CozyPixels.render(settings.theme, settings.message, 64, screen === 'bye');
      CozyPixels.paint(el('preview'), bytes);
      el('save').disabled = !ready || preview || saving;
      el('message').setCustomValidity(''); el('sleep_seconds').setCustomValidity('');
    } catch (e) {
      el('save').disabled = true;
      el('save-note').textContent = e.message;
    }
  }
  function fill(s) {
    settings = s;
    ['label','message','dim_seconds','sleep_seconds','poll_seconds'].forEach(function (key) {
      var field = el(key);
      if (field.tagName === 'SELECT' && !Array.prototype.some.call(field.options, function (o) {return o.value === s[key];})) {
        var option = document.createElement('option'); option.value = s[key]; option.textContent = s[key] + ' seconds'; field.appendChild(option);
      }
      field.value = s[key];
    });
    document.querySelectorAll('[data-theme]').forEach(function (button) {
      var selected = button.dataset.theme === s.theme;
      button.classList.toggle('selected', selected); button.setAttribute('aria-pressed', String(selected));
    });
    draw();
  }
  function profile() {
    fields(); validate(settings);
    settings.boot64 = CozyPixels.hex(CozyPixels.render(settings.theme, settings.message, 64, false));
    settings.boot128 = CozyPixels.hex(CozyPixels.render(settings.theme, settings.message, 128, false));
    var clean = {}; keys.forEach(function (key) { clean[key] = settings[key]; }); return clean;
  }
  function request(url, options) {
    options = options || {}; options.credentials = 'same-origin'; options.cache = 'no-store';
    var controller = new AbortController(), stop = setTimeout(function () { controller.abort(); }, 12000);
    options.signal = controller.signal;
    return fetch(url, options).then(function (r) { return r.json().then(function (json) {
      if (!r.ok) { var error = new Error(json.error || 'Connection failed'); error.status = r.status; throw error; } return json;
    }); }).finally(function () { clearTimeout(stop); });
  }
  function schedule() {
    clearTimeout(timer);
    if (!preview && ready && !document.hidden) timer = setTimeout(status, Math.min(+settings.poll_seconds * Math.pow(2,failures),300) * 1000);
  }
  function status() {
    if (document.hidden) return;
    request(api + '?status').then(function (data) {
      failures = 0; el('battery').textContent = data.battery_percent === null ? '—' : data.battery_percent + '%';
    }).catch(function (e) {
      failures = Math.min(failures+1,5);
      if (e.status === 401) { ready = false; el('save').disabled = true; notify('Your session ended. Sign in through Router settings, then reload this page.',true); }
    }).finally(schedule);
  }
  document.querySelectorAll('[data-theme]').forEach(function (button) {
    button.addEventListener('click', function () { settings.theme = button.dataset.theme; fill(settings); });
  });
  document.querySelectorAll('[data-screen]').forEach(function (button) {
    button.addEventListener('click', function () {
      screen = button.dataset.screen;
      document.querySelectorAll('[data-screen]').forEach(function (b) { b.setAttribute('aria-pressed',String(b === button)); });
      draw();
    });
  });
  el('settings').addEventListener('input', function () { el('save-note').textContent = 'Screen changes take effect the next time your hotspot starts.'; draw(); schedule(); });
  el('settings').addEventListener('submit', function (event) {
    event.preventDefault(); if (!ready || preview || saving) return;
    try {
      var clean = profile(), body = 'csrf=' + csrf + '\n' + keys.map(function (key) { return key + '=' + clean[key]; }).join('\n') + '\n';
      saving = true; draw();
      request(api, {method:'POST',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:body}).then(function () {
        el('save-note').textContent = 'Saved. Your new screens will greet you the next time your hotspot starts.';
      }).catch(function (e) {
        if (e.status === 401) ready = false;
        notify(e.message,true);
      }).finally(function () { saving = false; draw(); });
    } catch (e) { notify(e.message,true); }
  });
  el('export').addEventListener('click', function () {
    try {
      var url = URL.createObjectURL(new Blob([JSON.stringify(profile(),null,2) + '\n'], {type:'application/json'}));
      var a = document.createElement('a'); a.href = url; a.download = 'my-cozy-hotspot.json'; a.click();
      setTimeout(function () { URL.revokeObjectURL(url); },1000);
    } catch (e) { notify(e.message,true); }
  });
  el('import').addEventListener('click', function () { el('profile-file').click(); });
  el('profile-file').addEventListener('change', function () {
    var file = this.files[0]; if (!file) return;
    if (file.size > 12288) { notify('That look is too large. Use a Cozy profile exported from this page.',true); return; }
    file.text().then(function (text) {
      var parsed = JSON.parse(text), clean = {};
      if (!parsed || typeof parsed !== 'object' || Object.keys(parsed).length !== 9 || keys.some(function (key) { return typeof parsed[key] !== 'string'; })) throw new Error('This is not a Cozy profile.');
      keys.forEach(function (key) { clean[key] = parsed[key]; }); validate(clean);
      fill(clean); notify(preview ? 'Preview · Look imported locally. Export it to keep it.' : 'Look imported. Save my settings to apply it.');
    }).catch(function (e) { notify(e.message,true); });
    this.value = '';
  });
  document.addEventListener('visibilitychange', function () { if (document.hidden) clearTimeout(timer); else schedule(); });
  fill(settings);
  if (preview) { notify('Preview · Explore your look here. Saving to a device is disabled.'); el('battery').textContent = 'PREVIEW'; return; }
  request(api).then(function (data) {
    validate(data.settings);
    if (!/^[a-f0-9]{64}$/.test(data.csrf)) throw new Error('Invalid settings response.');
    csrf = data.csrf; ready = true; fill(data.settings); notify('Connected · Signed in with your router account.'); status();
  }).catch(function (e) { notify(e.message + '. Open Router settings to sign in, then reload this page.',true); });
}());
