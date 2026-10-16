// Brush-ink drawing helpers: bold tapered strokes, spiral curls, thorns and
// leaves as SVG paths. Every shape is generated from parameters.
const INK = (() => {
  const bez = (p0, p1, p2, p3, t) => {
    const u = 1 - t;
    return [u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
            u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]];
  };
  function sample(segs, n = 48) {
    const pts = [];
    segs.forEach((s, i) => { for (let k = (i ? 1 : 0); k <= n; k++) pts.push(bez(...s, k / n)); });
    return pts;
  }
  // spiral that continues the heading `a` smoothly and winds inward
  function curl(p, a, r0, turns, dir, n = 90) {
    const nrm = [Math.cos(a + dir * Math.PI / 2), Math.sin(a + dir * Math.PI / 2)];
    const c = [p[0] + nrm[0] * r0, p[1] + nrm[1] * r0];
    const th0 = Math.atan2(p[1] - c[1], p[0] - c[0]);
    const pts = [];
    for (let k = 1; k <= n; k++) {
      const t = k / n, th = th0 + dir * t * turns * 2 * Math.PI, r = r0 * (1 - 0.72 * t);
      pts.push([c[0] + Math.cos(th) * r, c[1] + Math.sin(th) * r]);
    }
    return pts;
  }
  function lengths(pts) {
    const acc = [0];
    for (let i = 1; i < pts.length; i++) acc.push(acc[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    return acc;
  }
  function outline(pts, widths) {
    const L = [], R = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      let dx = b[0] - a[0], dy = b[1] - a[1]; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l;
      const w = widths[i] / 2;
      L.push([pts[i][0] - dy * w, pts[i][1] + dx * w]); R.push([pts[i][0] + dy * w, pts[i][1] - dx * w]);
    }
    const f = p => p[0].toFixed(1) + ' ' + p[1].toFixed(1);
    return 'M' + L.map(f).join('L') + 'L' + R.reverse().map(f).join('L') + 'Z';
  }
  // brush stroke: thin start, full body, thin end (profile = [start, peakAt, end] as fractions of w)
  function brush(segs, w, start = .25, end = .1, peak = .35) {
    const pts = sample(segs), acc = lengths(pts), L = acc[acc.length - 1] || 1;
    const widths = acc.map(s => {
      const t = s / L;
      const up = Math.min(1, t / peak), down = Math.min(1, (1 - t) / (1 - peak));
      return w * Math.max(.04, Math.min(start + (1 - start) * Math.sin(up * Math.PI / 2), end + (1 - end) * Math.sin(down * Math.PI / 2)));
    });
    return outline(pts, widths);
  }
  // a brush stroke that ends in a spiral curl with a round ink drop at its heart
  function tendril(segs, w, curlR, dir = 1, turns = 1.2, start = .3) {
    const body = sample(segs), n = body.length;
    const a = Math.atan2(body[n - 1][1] - body[n - 2][1], body[n - 1][0] - body[n - 2][0]);
    const c = curl(body[n - 1], a, curlR, turns, dir);
    const pts = body.concat(c), acc = lengths(pts), L = acc[acc.length - 1], Lb = acc[n - 1];
    const widths = acc.map(s => s <= Lb
      ? w * (start + (1 - start) * Math.sin(Math.min(1, s / (Lb * .55)) * Math.PI / 2)) * (1 + .18 * Math.sin(Math.PI * s / Lb))
      : w * Math.max(.18, 1 - .82 * (s - Lb) / (L - Lb)));
    const end = pts[pts.length - 1], r = w * .32;
    return outline(pts, widths) + `M${end[0] + r} ${end[1]}a${r} ${r} 0 1 0 ${-2 * r} 0a${r} ${r} 0 1 0 ${2 * r} 0Z`;
  }
  // pointed leaf / thorn growing from p along angle a
  function leaf(p, a, len, wid, bend = .25) {
    const ca = Math.cos(a), sa = Math.sin(a), nx = -sa, ny = ca;
    const tip = [p[0] + ca * len + nx * len * bend * .4, p[1] + sa * len + ny * len * bend * .4];
    const m1 = [p[0] + ca * len * .35 + nx * wid * 1.5, p[1] + sa * len * .35 + ny * wid * 1.5];
    const m1b = [p[0] + ca * len * .8 + nx * wid * .9, p[1] + sa * len * .8 + ny * wid * .9];
    const m2 = [p[0] + ca * len * .75 - nx * wid * .35, p[1] + sa * len * .75 - ny * wid * .35];
    const m2b = [p[0] + ca * len * .3 - nx * wid * .5, p[1] + sa * len * .3 - ny * wid * .5];
    return `M${p[0]} ${p[1]}C${m1[0]} ${m1[1]} ${m1b[0]} ${m1b[1]} ${tip[0]} ${tip[1]}C${m2[0]} ${m2[1]} ${m2b[0]} ${m2b[1]} ${p[0]} ${p[1]}Z`;
  }
  return { sample, brush, tendril, leaf, outline };
})();
