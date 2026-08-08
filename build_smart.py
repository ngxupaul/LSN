#!/usr/bin/env python3
"""Generate LỆ SƠN NAM SMART VILLAGE – demo thi (self-contained HTML).

Nguồn vị trí thật: 66 nhà vẽ tay từ app (backups/*.geojson mới nhất).
Dữ liệu nhân hộ khẩu: MÔ PHỎNG, ẩn danh (tuân thủ Nghị định 13/2023 cho bản demo).
Các vùng "tổ" được gom theo vị trí địa lý để minh họa (Tổ 1..4).
"""
import json, math, os, random, glob

# ---- Nguồn dữ liệu vẽ tay mới nhất ----
files = sorted(glob.glob("backups/*.geojson"))
if not files:
    files = ["data/zone_buildings.geojson"]
SRC = files[-1]
with open(SRC) as f:
    drawn = json.load(f)
houses = [ft for ft in drawn["features"] if ft["geometry"]["type"] == "Polygon"]
print("houses:", len(houses), "from", SRC)

random.seed(42)  # deterministic demo

# ---- Sinh dữ liệu hộ MÔ PHỎNG (ẩn danh) ----
OWNER_LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
OWNER_FIRST = ["Văn A", "Thị B", "Văn C", "Thị D", "Văn E", "Thị F", "Văn G", "Thị H", "Văn K", "Thị L", "Văn M", "Thị N", "Văn P", "Thị Q"]

def centroid(coords):
    xs = [p[0] for p in coords]; ys = [p[1] for p in coords]
    return sum(xs)/len(xs), sum(ys)/len(ys)

sim = []
for i, ft in enumerate(houses):
    c = centroid(ft["geometry"]["coordinates"][0])
    members = random.randint(2, 7)
    elderly = min(random.randint(0, 2), members)
    children = min(random.randint(0, 3), members - elderly)
    policy = random.random() < 0.08
    support = random.random() < 0.12
    vneid = random.random() < 0.78
    bhyt = random.random() < 0.92
    sim.append({
        "id": "LSN-H%03d" % (i + 1),
        "owner": "%s %s" % (random.choice(OWNER_LAST), random.choice(OWNER_FIRST)),
        "members": members, "elderly": elderly, "children": children,
        "policy": policy, "support": support, "vneid": vneid, "bhyt": bhyt,
        "geom": ft["geometry"]["coordinates"][0],
        "c": [c[0], c[1]],  # lng, lat
    })

# ---- Gom 4 tổ theo kinh độ (tây→đông) ----
sim.sort(key=lambda h: h["c"][0])
N = len(sim)
k = 4
tos = []
for t in range(k):
    grp = sim[t * N // k: (t + 1) * N // k]
    if not grp:
        continue
    tos.append({
        "id": t + 1,
        "name": "Tổ %d" % (t + 1),
        "house_ids": [h["id"] for h in grp],
        "members": sum(h["members"] for h in grp),
        "elderly": sum(h["elderly"] for h in grp),
        "children": sum(h["children"] for h in grp),
        "policy": sum(1 for h in grp if h["policy"]),
        "support": sum(1 for h in grp if h["support"]),
        "vneid": sum(1 for h in grp if h["vneid"]),
        "bhyt": sum(1 for h in grp if h["bhyt"]),
    })

# ---- Phản ánh hạ tầng (mô phỏng) ----
REPORT_TYPES = [("Đèn đường hỏng", "#f59e0b"), ("Đường xuống cấp", "#dc2626"),
                ("Rác thải tồn đọng", "#16a34a"), ("Ngập nước", "#2563eb"), ("An ninh", "#7c3aed")]
reports = []
for r in range(10):
    h = random.choice(sim)
    t, color = REPORT_TYPES[r % len(REPORT_TYPES)]
    reports.append({
        "id": "PR-%03d" % (r + 1),
        "type": t, "color": color,
        "desc": "Phản ánh: %s – khu vực %s" % (t, h["id"]),
        "pos": [h["c"][1] + random.uniform(-0.0003, 0.0003), h["c"][0] + random.uniform(-0.0003, 0.0003)],
        "status": random.choice(["Mới", "Đang xử lý", "Đã xử lý"]),
    })

data = {
    "houses": sim,
    "tos": tos,
    "reports": reports,
    "meta": {"name": "Thôn Lệ Sơn Nam", "x": "Hòa Tiến, Hòa Vang, Đà Nẵng", "source": SRC, "n": N},
}

PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lệ Sơn Nam Smart Village – Quản lý nhân hộ khẩu thông minh</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root { --g:#16a34a; --y:#f59e0b; --r:#dc2626; --b:#2563eb; --t:#1f2937; --m:#6b7280; --line:#e5e7eb; --card:#fff; --shadow:0 6px 24px rgba(17,24,39,.14); --radius:14px; }
  * { box-sizing:border-box; }
  html,body { height:100%; margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; color:var(--t); }
  /* HEADER */
  header { background:linear-gradient(90deg,#065f46,#0e9f6e 60%,#16a34a); color:#fff; padding:10px 18px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; box-shadow:0 2px 10px rgba(0,0,0,.25); position:relative; z-index:1100; }
  header h1 { font-size:17px; margin:0; letter-spacing:.3px; }
  header .sub { font-size:11px; opacity:.85; }
  header .badge { background:#fde68a; color:#78350f; border-radius:999px; font-size:10.5px; font-weight:700; padding:3px 10px; }
  header .demo-btn { margin-left:auto; background:#fff; color:#065f46; border:none; border-radius:10px; padding:8px 16px; font:700 13px system-ui; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.2); }
  header .demo-btn:hover { transform:translateY(-1px); }
  /* DASHBOARD */
  #dash { display:flex; gap:10px; padding:10px 14px; background:#f8fafc; border-bottom:1px solid var(--line); overflow-x:auto; position:relative; z-index:1050; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:8px 14px; min-width:120px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
  .card .lbl { font-size:11px; color:var(--m); font-weight:600; }
  .card .val { font-size:20px; font-weight:800; margin-top:2px; }
  .card .val small { font-size:11px; font-weight:600; color:var(--m); }
  .card.hot { border-left:4px solid var(--r); }
  .card.warn { border-left:4px solid var(--y); }
  .card.ok { border-left:4px solid var(--g); }
  /* LAYOUT */
  #wrap { display:flex; height:calc(100% - 118px); position:relative; }
  #map { flex:1; height:100%; }
  /* FILTERS */
  #filters { position:absolute; z-index:900; top:12px; left:12px; display:flex; gap:6px; flex-wrap:wrap; max-width:420px; }
  #filters button { border:1px solid var(--line); background:#fff; border-radius:999px; padding:5px 12px; font:600 12px system-ui; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.2); }
  #filters button.active { background:#dcfce7; border-color:var(--g); color:#065f46; }
  #filters button.red.active { background:#fee2e2; border-color:var(--r); color:#991b1b; }
  /* SIDE PANEL */
  #side { width:350px; background:#fff; border-left:1px solid var(--line); overflow-y:auto; padding:14px; font-size:13px; }
  #side h2 { margin:0 0 10px; font-size:16px; }
  #side .kv { display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px dashed #eee; }
  #side .kv b { color:var(--t); }
  #side .bar { height:8px; background:#eef2f7; border-radius:99px; margin:3px 0 10px; overflow:hidden; }
  #side .bar i { display:block; height:100%; background:var(--g); border-radius:99px; }
  #side .house { padding:6px 8px; border:1px solid var(--line); border-radius:8px; margin:4px 0; cursor:pointer; background:#fafafa; }
  #side .house:hover { background:#f0fdf4; }
  #side .rep { padding:6px 8px; border:1px solid #fde68a; background:#fffbeb; border-radius:8px; margin:4px 0; font-size:12px; }
  #side .empty { color:var(--m); padding:20px 0; text-align:center; }
  /* LEGEND */
  .legend { position:absolute; z-index:900; bottom:14px; right:14px; background:rgba(255,255,255,.95); border:1px solid var(--line); border-radius:12px; padding:9px 12px; font-size:12px; box-shadow:var(--shadow); line-height:1.9; }
  .legend i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-2px; }
  /* POPUP nhỏ */
  .leaflet-popup-content { font:13px system-ui; }
  footer { position:absolute; z-index:1050; bottom:0; left:0; right:0; background:rgba(255,255,255,.9); border-top:1px solid var(--line); font-size:11.5px; color:var(--m); padding:5px 14px; display:flex; gap:18px; }
</style>
</head>
<body>
<header>
  <h1>🏡 LỆ SƠN NAM SMART VILLAGE</h1>
  <span class="sub">Quản lý nhân hộ khẩu thông minh · Hòa Tiến, Hòa Vang, Đà Nẵng</span>
  <span class="badge">DEMO – dữ liệu mô phỏng</span>
  <button class="demo-btn" onclick="startDemo()">▶️ Demo 60 giây</button>
</header>
<div id="dash">
  <div class="card"><div class="lbl">Tổng hộ dân</div><div class="val" id="dHos">–</div></div>
  <div class="card ok"><div class="lbl">Nhân khẩu</div><div class="val" id="dMem">–</div></div>
  <div class="card"><div class="lbl">Người cao tuổi</div><div class="val" id="dEld">–</div></div>
  <div class="card"><div class="lbl">Trẻ em</div><div class="val" id="dKid">–</div></div>
  <div class="card warn"><div class="lbl">Hộ chính sách</div><div class="val" id="dPol">–</div></div>
  <div class="card hot"><div class="lbl">Hộ cần hỗ trợ</div><div class="val" id="dSup">–</div></div>
  <div class="card ok"><div class="lbl">Tỷ lệ VNeID mức 2</div><div class="val" id="dVn">–</div></div>
  <div class="card hot"><div class="lbl">Phản ánh đang xử lý</div><div class="val" id="dRp">–</div></div>
</div>
<div id="wrap">
  <div id="map"></div>
  <div id="filters">
    <button class="red" onclick="tog('sup')">🆘 Cần hỗ trợ</button>
    <button onclick="tog('pol')">🚩 Chính sách</button>
    <button onclick="tog('vneid')">🟦 VNeID mức 2</button>
    <button onclick="tog('bhyt')">🟩 BHYT</button>
    <button class="red" onclick="tog('rep')">⚠️ Phản ánh</button>
  </div>
  <div class="legend">
    <i style="background:#16a34a"></i> Nhà ổn định<br>
    <i style="background:#f59e0b"></i> Hộ chính sách<br>
    <i style="background:#dc2626"></i> Hộ cần hỗ trợ<br>
    <i style="background:rgba(30,64,175,.25);border:2px solid #1e40af"></i> Ranh giới tổ<br>
    <i style="background:#7c3aed;border-radius:50%"></i> Điểm phản ánh
  </div>
  <div id="side">
    <div class="empty">👈 Bấm vào một <b>ngôi nhà</b> hoặc <b>vùng tổ</b> trên bản đồ để xem dữ liệu chi tiết.</div>
  </div>
</div>
<footer>
  <span><b>Lệ Sơn Nam Smart Village</b> – bản demo dùng dữ liệu mô phỏng (Nghị định 13/2023/NĐ-CP); vị trí nhà lấy từ bản đồ vẽ tay thực tế của thôn.</span>
  <span>Phân tích: click nhà/tổ · Lọc: nút trên bản đồ · Phản ánh: chấm tím</span>
</footer>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = __DATA__;
const houses = DATA.houses, tos = DATA.tos, reports = DATA.reports;

// ---------- DASHBOARD ----------
const tot = {h: houses.length, mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, vn: 0, bh: 0};
houses.forEach(h => {
  tot.mem += h.members; tot.eld += h.elderly; tot.kid += h.children;
  if (h.policy) tot.pol++; if (h.support) tot.sup++;
  if (h.vneid) tot.vn++; if (h.bhyt) tot.bh++;
});
const openRep = reports.filter(r => r.status !== 'Đã xử lý').length;
document.getElementById('dHos').innerHTML = tot.h + ' <small>hộ</small>';
document.getElementById('dMem').innerHTML = tot.mem + ' <small>người</small>';
document.getElementById('dEld').textContent = tot.eld;
document.getElementById('dKid').textContent = tot.kid;
document.getElementById('dPol').textContent = tot.pol;
document.getElementById('dSup').textContent = tot.sup;
document.getElementById('dVn').innerHTML = Math.round(tot.vn / tot.h * 100) + '<small>%</small>';
document.getElementById('dRp').textContent = openRep;

// ---------- MAP ----------
const map = L.map('map', {preferCanvas: true}).setView([15.9606, 108.1855], 16);
const googleHybrid = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
  {maxZoom: 20, subdomains: ['mt0','mt1','mt2','mt3'], attribution: 'Tiles &copy; Google (tham chiếu demo)'});
googleHybrid.addTo(map);
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19});
L.control.layers({'Google Hybrid': googleHybrid, 'OSM': osm}).addTo(map);

function houseColor(h) {
  if (h.support) return '#dc2626';
  if (h.policy) return '#f59e0b';
  return '#16a34a';
}
const houseLayer = L.featureGroup().addTo(map);
houses.forEach(h => {
  const poly = L.polygon(h.geom.map(p => [p[1], p[0]]), {
    color: houseColor(h), weight: 2, fillColor: houseColor(h), fillOpacity: .55
  });
  poly.h = h;
  poly.on('click', () => showHouse(h));
  poly.bindTooltip(h.id, {sticky: true});
  houseLayer.addLayer(poly);
});

// ---------- VÙNG TỔ ----------
function hull(pts) {
  const p = pts.slice().sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const cr = (o, a, b) => (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]);
  const lo = [], up = [];
  p.forEach(q => { while (lo.length >= 2 && cr(lo[lo.length-2], lo[lo.length-1], q) <= 0) lo.pop(); lo.push(q); });
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up[up.length-2], up[up.length-1], q) <= 0) up.pop(); up.push(q); }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
const TO_COLORS = ['#1e40af', '#b45309', '#065f46', '#7c3aed', '#be185d', '#0369a1'];
const toLayer = L.featureGroup().addTo(map);
tos.forEach((t, i) => {
  const ids = new Set(t.house_ids);
  const pts = houses.filter(h => ids.has(h.id)).map(h => [h.c[0], h.c[1]]);
  let ring;
  if (pts.length >= 3) ring = hull(pts);
  else { const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]); ring = [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)], [Math.min(...xs), Math.max(...ys)]]; }
  const color = TO_COLORS[i % TO_COLORS.length];
  const poly = L.polygon(ring.map(p => [p[1], p[0]]), {color: color, weight: 2.5, fillColor: color, fillOpacity: .12});
  poly.t = t;
  poly.on('click', () => showTo(t, i));
  poly.bindTooltip(t.name + ' – ' + t.house_ids.length + ' hộ', {sticky: true});
  toLayer.addLayer(poly);
  // nhãn tổ
  const c = poly.getBounds().getCenter();
  L.marker(c, {icon: L.divIcon({className: '', html: '<div style="background:' + color + ';color:#fff;border-radius:8px;padding:3px 9px;font:700 12px system-ui;box-shadow:0 2px 6px rgba(0,0,0,.35)">' + t.name + '</div>', iconSize: [0, 0]})}).addTo(toLayer);
});

// ---------- PHẢN ÁNH ----------
const repLayer = L.featureGroup().addTo(map);
reports.forEach(r => {
  const m = L.circleMarker(r.pos, {radius: 7, color: '#fff', weight: 2, fillColor: r.color, fillOpacity: 1});
  m.r = r;
  m.bindPopup('<b>' + r.id + '</b> – ' + r.type + '<br>' + r.desc + '<br>Trạng thái: <b>' + r.status + '</b>');
  repLayer.addLayer(m);
});

// ---------- SIDE PANEL ----------
const side = document.getElementById('side');
function esc(s) { return String(s == null ? '' : s).replace(/</g, '&lt;'); }
function bar(pct, color) { return '<div class="bar"><i style="width:' + pct + '%;background:' + color + '"></i></div>'; }
function statRow(k, v) { return '<div class="kv"><span>' + k + '</span><b>' + v + '</b></div>'; }
function aggRows(g) {
  const n = g.house_ids ? g.house_ids.length : 1;
  const vn = Math.round(g.vneid / n * 100), bh = Math.round(g.bhyt / n * 100);
  return statRow('Số hộ', g.house_ids.length) + statRow('Nhân khẩu', g.members) +
    statRow('Người cao tuổi', g.elderly) + statRow('Trẻ em', g.children) +
    statRow('Hộ chính sách', g.policy) + statRow('Hộ cần hỗ trợ', g.support) +
    '<div style="margin-top:6px"><b>Tỷ lệ VNeID mức 2:</b> ' + vn + '%</div>' + bar(vn, '#2563eb') +
    '<b>Tỷ lệ BHYT:</b> ' + bh + '%' + bar(bh, '#16a34a');
}
function showTo(t, i) {
  const color = TO_COLORS[i % TO_COLORS.length];
  const ids = new Set(t.house_ids);
  const list = houses.filter(h => ids.has(h.id));
  side.innerHTML = '<h2 style="color:' + color + '">🏘 ' + esc(t.name) + ' – Lệ Sơn Nam</h2>' +
    aggRows(t) +
    '<h3 style="margin:12px 0 6px">Danh sách hộ (' + list.length + ')</h3>' +
    list.map(h => '<div class="house" onclick="flyHouse(\'' + h.id + '\')">' +
      '<b>' + h.id + '</b> · ' + esc(h.owner) + ' · ' + h.members + ' người · ' +
      (h.vneid ? '🟦VNeID' : '⬜') + (h.bhyt ? ' 🟩BHYT' : '') +
      (h.policy ? ' 🚩' : '') + (h.support ? ' 🆘' : '') + '</div>').join('') +
    '<h3 style="margin:12px 0 6px">Phản ánh khu vực</h3>' +
    (reports.filter(r => r.status !== 'Đã xử lý').length ? reports.filter(r => r.status !== 'Đã xử lý').map(r => '<div class="rep">⚠️ ' + r.id + ' · ' + r.type + ' · <b>' + r.status + '</b></div>').join('') : '<div class="empty" style="padding:8px">Không có phản ánh tồn đọng</div>');
  side.scrollTop = 0;
}
function showHouse(h) {
  side.innerHTML = '<h2>🏠 ' + esc(h.id) + '</h2>' +
    statRow('Chủ hộ (ẩn danh)', esc(h.owner)) +
    statRow('Nhân khẩu', h.members) +
    statRow('Người cao tuổi', h.elderly) +
    statRow('Trẻ em', h.children) +
    statRow('Hộ chính sách', h.policy ? 'Có 🚩' : 'Không') +
    statRow('Hộ cần hỗ trợ', h.support ? 'Có 🆘' : 'Không') +
    '<div style="margin-top:6px"><b>VNeID mức 2:</b> ' + (h.vneid ? 'Đã định danh' : 'Chưa') + '</div>' + bar(h.vneid ? 100 : 10, '#2563eb') +
    '<b>BHYT:</b> ' + (h.bhyt ? 'Đã có thẻ' : 'Chưa có') + bar(h.bhyt ? 100 : 10, '#16a34a') +
    '<h3 style="margin:12px 0 6px">Phản ánh gần đây</h3>' +
    (reports.filter(r => Math.abs(r.pos[0] - h.c[1]) < 0.0012 && Math.abs(r.pos[1] - h.c[0]) < 0.0012).map(r => '<div class="rep">⚠️ ' + r.type + ' · <b>' + r.status + '</b></div>').join('') || '<div class="empty" style="padding:8px">Không có phản ánh</div>') +
    '<button style="margin-top:12px;width:100%;padding:8px;border:none;border-radius:9px;background:#f3f4f6;cursor:pointer;font:600 13px system-ui" onclick="side.innerHTML=emptyInit">↩️ Quay lại</button>';
}
const emptyInit = '<div class="empty">👈 Bấm vào một <b>ngôi nhà</b> hoặc <b>vùng tổ</b> trên bản đồ để xem dữ liệu chi tiết.</div>';
window.flyHouse = function(id) {
  const h = houses.find(x => x.id === id);
  if (!h) return;
  map.flyTo([h.c[1], h.c[0]], 19);
  houseLayer.eachLayer(l => { if (l.h && l.h.id === id) l.openPopup(); });
};
window.gotoHouse = flyHouse;

// ---------- BỘ LỌC ----------
let fSup = false, fPol = false, fVn = false, fBh = false, fRep = false;
function applyFilter() {
  houseLayer.eachLayer(l => {
    const h = l.h;
    const on = (!fSup || h.support) && (!fPol || h.policy) && (!fVn || h.vneid) && (!fBh || h.bhyt);
    l.setStyle({fillOpacity: on ? .55 : .06, opacity: on ? 1 : .35, weight: on ? 2 : 1});
    l.bringToFront();
  });
  repLayer.eachLayer(m => { m.setStyle({radius: fRep || true ? 7 : 7, fillOpacity: (!fRep || true) ? 1 : .15}); });
  if (!fRep) repLayer.eachLayer(m => m.setStyle({fillOpacity: .18, opacity: .5}));
  else repLayer.eachLayer(m => m.setStyle({fillOpacity: 1, opacity: 1}));
}
function tog(k) {
  if (k === 'sup') { fSup = !fSup; document.querySelector('#filters button').classList.toggle('active', fSup); }
  if (k === 'pol') { fPol = !fPol; document.querySelectorAll('#filters button')[1].classList.toggle('active', fPol); }
  if (k === 'vneid') { fVn = !fVn; document.querySelectorAll('#filters button')[2].classList.toggle('active', fVn); }
  if (k === 'bhyt') { fBh = !fBh; document.querySelectorAll('#filters button')[3].classList.toggle('active', fBh); }
  if (k === 'rep') { fRep = !fRep; document.querySelectorAll('#filters button')[4].classList.toggle('active', fRep); }
  applyFilter();
}
applyFilter();

// ---------- DEMO 60 GIÂY ----------
let demoRunning = false;
window.startDemo = function() {
  if (demoRunning) return; demoRunning = true;
  const steps = [];
  map.flyTo([15.9606, 108.1855], 16);
  tos.forEach((t, i) => steps.push(() => { map.flyTo(toLayer.getLayers()[i * 2].getBounds().getCenter(), 17); showTo(t, i); }));
  steps.push(() => { map.flyTo([15.9606, 108.1855], 16); showTo(tos[0], 0); });
  let k = 0;
  const tick = () => { if (k < steps.length) { steps[k++](); setTimeout(tick, 1600); } else demoRunning = false; };
  setTimeout(tick, 800);
};
</script>
</body>
</html>
"""

PAGE = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))

out = "smart-village.html"
with open(out, "w") as f:
    f.write(PAGE)
print("WROTE", out, len(PAGE), "bytes |", N, "houses,", len(tos), "tổ,", len(reports), "reports")
