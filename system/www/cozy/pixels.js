(function (root) {
  'use strict';
  function render(theme, message, height, goodbye) {
    var glyphs = root.COZY_GLYPHS;
    if (['cat', 'cloud', 'sprout'].indexOf(theme) < 0 || [64, 128].indexOf(height) < 0 ||
        message.length > 18 || message.split('').some(function (c) { return !glyphs[c]; })) {
      throw new Error('Use up to 18 letters, numbers, spaces or simple punctuation.');
    }
    var pixels = new Uint8Array(128 * height), oy = (height - 64) / 2;
    function point(x, y) {
      if (x >= 0 && x < 128 && y + oy >= 0 && y + oy < height) pixels[(y + oy) * 128 + x] = 1;
    }
    function line(x0, y0, x1, y1) {
      var dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
      var sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
      while (true) {
        point(x0, y0);
        if (x0 === x1 && y0 === y1) break;
        var twice = 2 * err;
        if (twice >= dy) { err += dy; x0 += sx; }
        if (twice <= dx) { err += dx; y0 += sy; }
      }
    }
    function path(points) {
      for (var i = 1; i < points.length; i++) line(points[i-1][0], points[i-1][1], points[i][0], points[i][1]);
    }
    function text(value, y) {
      var x = Math.floor((128 - (value.length * 6 - 1)) / 2);
      value.split('').forEach(function (c) {
        glyphs[c].forEach(function (bits, row) {
          for (var col = 0; col < 5; col++) if (bits & (1 << (4 - col))) point(x + col, y + row);
        });
        x += 6;
      });
    }
    text('COZY HOTSPOT', 1);
    if (theme === 'cat') {
      path([[48,39],[46,25],[47,15],[56,20],[72,20],[81,15],[82,25],[80,39],[74,43],[54,43],[48,39]]);
      if (goodbye) { line(53,29,58,29); line(70,29,75,29); }
      else { line(55,27,55,29); line(73,27,73,29); }
      path([[61,33],[64,35],[67,33]]);
      line(43,31,51,33); line(43,36,51,35); line(77,33,85,31); line(77,35,85,36);
    } else if (theme === 'cloud') {
      path([[44,39],[40,36],[40,29],[44,25],[50,25],[50,20],[56,15],[65,15],[71,19],[73,24],[81,24],[87,29],[87,36],[82,40],[44,40]]);
      line(55,29,goodbye ? 59 : 55,goodbye ? 29 : 31);
      line(73,29,goodbye ? 77 : 73,goodbye ? 29 : 31);
      path([[61,34],[64,36],[67,34]]);
    } else {
      path([[64,43],[64,29],[58,24],[49,23],[45,17],[54,16],[61,19],[64,26],[67,19],[74,16],[83,17],[79,23],[70,24],[64,29]]);
      line(52,43,76,43); line(57,46,71,46); point(60,38); point(68,38);
    }
    [[30,22],[96,33]].forEach(function (p) { line(p[0]-2,p[1],p[0]+2,p[1]); line(p[0],p[1]-2,p[0],p[1]+2); });
    text(goodbye ? 'SWEET DREAMS' : message, 55);
    var bytes = new Uint8Array(16 * height);
    for (var y = 0; y < height; y++) for (var x = 0; x < 128; x += 8) {
      var byte = 255;
      for (var bit = 0; bit < 8; bit++) if (pixels[y * 128 + x + bit]) byte ^= 1 << (7-bit);
      bytes[y * 16 + x/8] = byte;
    }
    return bytes;
  }
  function hex(bytes) { return Array.prototype.map.call(bytes, function (v) { return ('0' + v.toString(16)).slice(-2); }).join(''); }
  function paint(canvas, bytes) {
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#0d2622'; ctx.fillRect(0, 0, 128, 64); ctx.fillStyle = '#d4ffe3';
    for (var y = 0; y < 64; y++) for (var x = 0; x < 128; x++) {
      if (!(bytes[y * 16 + Math.floor(x/8)] & (1 << (7 - x%8)))) ctx.fillRect(x, y, 1, 1);
    }
  }
  root.CozyPixels = { render: render, hex: hex, paint: paint };
}(typeof window === 'undefined' ? globalThis : window));
