#!/usr/bin/env python3
"""Generate LỆ SƠN NAM SMART VILLAGE – sản phẩm quản lý nhân hộ khẩu cho Trưởng thôn.

- Vị trí nhà: THẬT từ backups/*.geojson (vẽ tay)
- Dữ liệu nhân hộ khẩu: MÔ PHỎNG, ẩn danh (Nghị định 13/2023)
- Tính năng: dashboard + biểu đồ (dân số theo tổ, nhóm tuổi) + map tương tác +
  search chủ hộ (zoom) + CRUD hộ + an sinh (thăm hỏi) + phản ánh + báo cáo in
"""
import json, random, glob

# ---- Nguồn vẽ tay mới nhất ----
files = sorted(glob.glob("backups/*.geojson"))
if not files:
    files = ["data/zone_buildings.geojson"]
SRC = files[-1]
with open(SRC) as f:
    drawn = json.load(f)
houses_raw = [ft for ft in drawn["features"] if ft["geometry"]["type"] == "Polygon"]
print("houses:", len(houses_raw), "from", SRC)

random.seed(42)
LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
FIRST = ["Văn A", "Thị B", "Văn C", "Thị D", "Văn E", "Thị F", "Văn G", "Thị H", "Văn K", "Thị L", "Văn M", "Thị N", "Văn P", "Thị Q"]

def centroid(coords):
    xs = [p[0] for p in coords]; ys = [p[1] for p in coords]
    return sum(xs)/len(xs), sum(ys)/len(ys)

sim = []
for i, ft in enumerate(houses_raw):
    c = centroid(ft["geometry"]["coordinates"][0])
    members = random.randint(2, 7)
    elderly = min(random.randint(0, 2), members)
    children = min(random.randint(0, 3), members - elderly)
    sim.append({
        "id": "LSN-H%03d" % (i + 1),
        "owner": "%s %s" % (random.choice(LAST), random.choice(FIRST)),
        "members": members, "elderly": elderly, "children": children,
        "policy": random.random() < 0.08, "support": random.random() < 0.12,
        "vneid": random.random() < 0.78, "bhyt": random.random() < 0.92,
        "geom": ft["geometry"]["coordinates"][0],
        "c": [c[0], c[1]],
    })

# gom tổ theo kinh độ
sim.sort(key=lambda h: h["c"][0])
N = len(sim); k = 4
tos = []
for t in range(k):
    grp = sim[t * N // k: (t + 1) * N // k]
    if not grp:
        continue
    tos.append({"id": t + 1, "name": "Tổ %d" % (t + 1), "house_ids": [h["id"] for h in grp]})
TO_OF = {}
for t in tos:
    for hid in t["house_ids"]:
        TO_OF[hid] = t["id"]

REPORT_TYPES = [("Đèn đường hỏng", "#f59e0b"), ("Đường xuống cấp", "#dc2626"),
                ("Rác thải tồn đọng", "#16a34a"), ("Ngập nước", "#2563eb"), ("An ninh", "#7c3aed")]
reports = []
for r in range(10):
    h = random.choice(sim)
    t, color = REPORT_TYPES[r % len(REPORT_TYPES)]
    reports.append({"id": "PR-%03d" % (r + 1), "type": t, "color": color,
        "desc": "Phản ánh: %s – khu vực %s" % (t, h["id"]),
        "pos": [h["c"][1] + random.uniform(-0.0003, 0.0003), h["c"][0] + random.uniform(-0.0003, 0.0003)],
        "status": random.choice(["Mới", "Đang xử lý", "Đã xử lý"])})

data = {"houses": sim, "tos": tos, "to_of": TO_OF, "reports": reports,
        "meta": {"name": "Thôn Lệ Sơn Nam", "x": "Hòa Tiến, Hòa Vang, Đà Nẵng", "source": SRC, "n": N}}

PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lệ Sơn Nam Smart Village – Quản lý nhân hộ khẩu thông minh</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root { --g:#16a34a; --y:#f59e0b; --r:#dc2626; --b:#2563eb; --t:#1f2937; --m:#6b7280; --line:#e5e7eb; --shadow:0 6px 24px rgba(17,24,39,.14); }
  * { box-sizing:border-box; }
  html,body { height:100%; margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; color:var(--t); }
  header { background:linear-gradient(90deg,#065f46,#0e9f6e 60%,#16a34a); color:#fff; padding:8px 16px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; position:relative; z-index:1100; }
  header h1 { font-size:16px; margin:0; }
  header .sub { font-size:11px; opacity:.85; }
  header .badge { background:#fde68a; color:#78350f; border-radius:999px; font-size:10px; font-weight:700; padding:2px 9px; }
  header .btn { background:rgba(255,255,255,.16); color:#fff; border:none; border-radius:9px; padding:6px 12px; font:600 12.5px system-ui; cursor:pointer; }
  header .btn:hover { background:rgba(255,255,255,.3); }
  #searchBox { padding:7px 12px; border:none; border-radius:10px; width:220px; font:13px system-ui; outline:none; }
  #searchRes { position:absolute; top:52px; right:16px; width:300px; background:#fff; color:var(--t); border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); max-height:300px; overflow-y:auto; display:none; z-index:2000; }
  #searchRes .r { padding:8px 12px; border-bottom:1px solid #f3f4f6; cursor:pointer; font-size:12.5px; }
  #searchRes .r:hover { background:#f0fdf4; }
  #top { background:#f8fafc; border-bottom:1px solid var(--line); padding:8px 14px; position:relative; z-index:1050; }
  #dash { display:flex; gap:9px; overflow-x:auto; }
  .card { background:#fff; border:1px solid var(--line); border-radius:12px; padding:7px 12px; min-width:112px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
  .card .lbl { font-size:10.5px; color:var(--m); font-weight:600; }
  .card .val { font-size:18px; font-weight:800; margin-top:1px; }
  .card .val small { font-size:10px; font-weight:600; color:var(--m); }
  .card.hot { border-left:4px solid var(--r); }
  .card.warn { border-left:4px solid var(--y); }
  .card.ok { border-left:4px solid var(--g); }
  #charts { display:flex; gap:14px; margin-top:8px; }
  .chartbox { background:#fff; border:1px solid var(--line); border-radius:12px; padding:8px 12px; flex:1; min-width:0; }
  .chartbox h4 { margin:0 0 6px; font-size:12px; color:var(--m); }
  .hbar { display:flex; align-items:center; gap:8px; margin:3px 0; font-size:11.5px; }
  .hbar .nm { width:52px; font-weight:700; }
  .hbar .tr { flex:1; background:#eef2f7; border-radius:99px; height:14px; overflow:hidden; }
  .hbar .tr i { display:block; height:100%; border-radius:99px; }
  .hbar .vv { width:44px; text-align:right; font-weight:700; }
  .donut { width:96px; height:96px; border-radius:50%; margin:0 auto; }
  .donut-l { display:flex; justify-content:center; gap:12px; margin-top:6px; font-size:11px; flex-wrap:wrap; }
  .donut-l i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:4px; vertical-align:-1px; }
  #wrap { display:flex; height:calc(100% - 176px); position:relative; }
  #map { flex:1; height:100%; }
  #filters { position:absolute; z-index:900; top:10px; left:10px; display:flex; gap:5px; flex-wrap:wrap; max-width:430px; }
  #filters button { border:1px solid var(--line); background:#fff; border-radius:999px; padding:4px 11px; font:600 11.5px system-ui; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.2); }
  #filters button.active { background:#dcfce7; border-color:var(--g); color:#065f46; }
  #filters button.red.active { background:#fee2e2; border-color:var(--r); color:#991b1b; }
  #side { width:368px; background:#fff; border-left:1px solid var(--line); display:flex; flex-direction:column; }
  #tabs { display:flex; border-bottom:1px solid var(--line); background:#f9fafb; }
  #tabs button { flex:1; border:none; background:transparent; padding:8px 2px; font:600 11.5px system-ui; cursor:pointer; color:var(--m); border-bottom:2.5px solid transparent; }
  #tabs button.on { color:#065f46; border-bottom-color:var(--g); background:#fff; }
  #panel { flex:1; overflow-y:auto; padding:12px; font-size:13px; }
  #panel h2 { margin:0 0 10px; font-size:15.5px; }
  .kv { display:flex; justify-content:space-between; padding:3.5px 0; border-bottom:1px dashed #eee; }
  .kv b { font-weight:700; }
  .bar { height:8px; background:#eef2f7; border-radius:99px; margin:3px 0 8px; overflow:hidden; }
  .bar i { display:block; height:100%; background:var(--g); border-radius:99px; }
  .row { padding:6px 8px; border:1px solid var(--line); border-radius:8px; margin:4px 0; cursor:pointer; background:#fafafa; font-size:12.5px; }
  .row:hover { background:#f0fdf4; }
  .rep { padding:6px 8px; border:1px solid #fde68a; background:#fffbeb; border-radius:8px; margin:4px 0; font-size:12px; }
  .empty { color:var(--m); padding:16px 0; text-align:center; }
  .btn2 { padding:7px 12px; border:none; border-radius:9px; cursor:pointer; font:600 12.5px system-ui; background:#065f46; color:#fff; }
  .btn2.gray { background:#f3f4f6; color:var(--t); }
  .btn2.red { background:#fee2e2; color:#991b1b; }
  input[type=text], input[type=number], select { width:100%; padding:6px 8px; border:1px solid #d1d5db; border-radius:8px; font:13px system-ui; margin:3px 0; }
  .lbl2 { font-weight:600; font-size:12px; margin-top:6px; color:var(--m); }
  .legend { position:absolute; z-index:900; bottom:14px; right:14px; background:rgba(255,255,255,.95); border:1px solid var(--line); border-radius:12px; padding:8px 11px; font-size:11.5px; box-shadow:var(--shadow); line-height:1.9; }
  .legend i { display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:6px; vertical-align:-2px; }
  footer { position:absolute; z-index:1050; bottom:0; left:0; right:0; background:rgba(255,255,255,.92); border-top:1px solid var(--line); font-size:11px; color:var(--m); padding:4px 14px; }
  #reportArea { display:none; }
  @media print {
    body * { visibility:hidden; }
    #reportArea, #reportArea * { visibility:visible; }
    #reportArea { display:block; position:absolute; top:0; left:0; width:100%; padding:20px; font-size:12px; }
    #reportArea table { border-collapse:collapse; width:100%; margin:8px 0; }
    #reportArea th, #reportArea td { border:1px solid #333; padding:4px 7px; text-align:right; font-size:11.5px; }
    #reportArea th:first-child, #reportArea td:first-child { text-align:left; }
  }
</style>
</head>
<body>
<header>
  <h1>🏡 LỆ SƠN NAM SMART VILLAGE</h1>
  <span class="sub">Quản lý nhân hộ khẩu thông minh · Hòa Tiến, Hòa Vang, Đà Nẵng</span>
  <span class="badge">DEMO – dữ liệu mô phỏng</span>
  <input id="searchBox" placeholder="🔍 Tìm chủ hộ / mã hộ..." autocomplete="off">
  <div id="searchRes"></div>
  <button class="btn" onclick="openTab('an')">🤝 An sinh</button>
  <button class="btn" onclick="openTab('rep')">⚠️ Phản ánh</button>
  <button class="btn" onclick="openTab('bc')">📄 Báo cáo</button>
  <button class="btn" onclick="startDemo()">▶️ Demo 60s</button>
</header>
<div id="top">
  <div id="dash">
    <div class="card"><div class="lbl">Tổng hộ dân</div><div class="val" id="dHos">–</div></div>
    <div class="card ok"><div class="lbl">Nhân khẩu</div><div class="val" id="dMem">–</div></div>
    <div class="card"><div class="lbl">Người cao tuổi</div><div class="val" id="dEld">–</div></div>
    <div class="card"><div class="lbl">Trẻ em</div><div class="val" id="dKid">–</div></div>
    <div class="card warn"><div class="lbl">Hộ chính sách</div><div class="val" id="dPol">–</div></div>
    <div class="card hot"><div class="lbl">Hộ cần hỗ trợ</div><div class="val" id="dSup">–</div></div>
    <div class="card ok"><div class="lbl">VNeID mức 2</div><div class="val" id="dVn">–</div></div>
    <div class="card hot"><div class="lbl">Phản ánh đang xử lý</div><div class="val" id="dRp">–</div></div>
  </div>
  <div id="charts">
    <div class="chartbox"><h4>📊 Dân số theo tổ (người)</h4><div id="barChart"></div></div>
    <div class="chartbox"><h4>👥 Nhóm tuổi</h4><div class="donut" id="donut"></div>
      <div class="donut-l" id="donutL"></div></div>
  </div>
</div>
<div id="wrap">
  <div id="map"></div>
  <div id="filters">
    <button class="red" onclick="tog('sup')">🆘 Cần hỗ trợ</button>
    <button onclick="tog('pol')">🚩 Chính sách</button>
    <button onclick="tog('vneid')">🟦 VNeID</button>
    <button onclick="tog('bhyt')">🟩 BHYT</button>
    <button class="red" onclick="tog('rep')">⚠️ Phản ánh</button>
  </div>
  <div class="legend">
    <i style="background:#16a34a"></i> Nhà ổn định<br>
    <i style="background:#f59e0b"></i> Hộ chính sách<br>
    <i style="background:#dc2626"></i> Hộ cần hỗ trợ<br>
    <i style="background:rgba(30,64,175,.25);border:2px solid #1e40af"></i> Vùng tổ<br>
    <i style="background:#7c3aed;border-radius:50%"></i> Điểm phản ánh
  </div>
  <div id="side">
    <div id="tabs">
      <button class="on" onclick="openTab('chi')">🏠 Chi tiết</button>
      <button onclick="openTab('ho')">📋 Hộ dân</button>
      <button onclick="openTab('an')">🤝 An sinh</button>
      <button onclick="openTab('rep')">⚠️ Phản ánh</button>
      <button onclick="openTab('bc')">📄 Báo cáo</button>
    </div>
    <div id="panel"><div class="empty">👈 Bấm vào một <b>ngôi nhà</b> hoặc <b>vùng tổ</b> trên bản đồ để xem dữ liệu chi tiết.</div></div>
  </div>
</div>
<footer>
  <b>Lệ Sơn Nam Smart Village</b> – demo quản lý cho Trưởng thôn · dữ liệu hộ MÔ PHỎNG (Nghị định 13/2023) · vị trí nhà thật từ bản đồ vẽ tay
</footer>
<div id="reportArea"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = __DATA__;
let houses = DATA.houses.map(h => Object.assign({}, h));
const tos = DATA.tos.map(t => Object.assign({}, t));
let reports = DATA.reports.map(r => Object.assign({}, r));
const LSKEY = 'lsv_demo_v1';
function store() { try { localStorage.setItem(LSKEY, JSON.stringify({houses, reports})); } catch (e) {} }
try { const s = JSON.parse(localStorage.getItem(LSKEY)); if (s && s.houses) { houses = s.houses; reports = s.reports; } } catch (e) {}
function toOf(h) { return DATA.to_of[h.id] || 1; }
function byId(id) { return houses.find(h => h.id === id); }

// ============ MAP ============
const map = L.map('map', {preferCanvas: true}).setView([15.9606, 108.1855], 16);
const googleHybrid = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {maxZoom: 20, subdomains: ['mt0','mt1','mt2','mt3'], attribution: 'Tiles &copy; Google (tham chiếu)'});
googleHybrid.addTo(map);
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19});
L.control.layers({'Google Hybrid': googleHybrid, 'OSM': osm}).addTo(map);

function hColor(h) { return h.support ? '#dc2626' : (h.policy ? '#f59e0b' : '#16a34a'); }
const houseLayer = L.featureGroup().addTo(map);
const repLayer = L.featureGroup().addTo(map);
const toLayer = L.featureGroup().addTo(map);
let addHouseMode = false, addRepMode = false;

function renderHouses() {
  houseLayer.clearLayers();
  houses.forEach(h => {
    const poly = L.polygon(h.geom.map(p => [p[1], p[0]]), {color: hColor(h), weight: 2, fillColor: hColor(h), fillOpacity: .55});
    poly.h = h;
    poly.on('click', () => { openTab('chi'); showHouse(h); });
    poly.bindTooltip(h.id + ' · ' + h.owner, {sticky: true});
    houseLayer.addLayer(poly);
  });
  applyFilter();
}
function renderReps() {
  repLayer.clearLayers();
  reports.forEach(r => {
    const m = L.circleMarker(r.pos, {radius: 7, color: '#fff', weight: 2, fillColor: r.color, fillOpacity: 1});
    m.r = r;
    m.on('click', () => { openTab('rep'); repList(); });
    m.bindPopup('<b>' + r.id + '</b> – ' + r.type + '<br>' + r.desc + '<br>Trạng thái: <b>' + r.status + '</b>');
    repLayer.addLayer(m);
  });
}
function hull(pts) {
  const p = pts.slice().sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const cr = (o, a, b) => (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]);
  const lo = [], up = [];
  p.forEach(q => { while (lo.length >= 2 && cr(lo[lo.length-2], lo[lo.length-1], q) <= 0) lo.pop(); lo.push(q); });
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up[up.length-2], up[up.length-1], q) <= 0) up.pop(); up.push(q); }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
const TO_COLORS = ['#1e40af', '#b45309', '#065f46', '#7c3aed', '#be185d', '#0369a1'];
function renderTos() {
  toLayer.clearLayers();
  tos.forEach((t, i) => {
    const ids = new Set(t.house_ids);
    const pts = houses.filter(h => ids.has(h.id)).map(h => [h.c[0], h.c[1]]);
    if (!pts.length) return;
    let ring;
    if (pts.length >= 3) ring = hull(pts);
    else { const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]); ring = [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)], [Math.min(...xs), Math.max(...ys)]]; }
    const color = TO_COLORS[i % TO_COLORS.length];
    const poly = L.polygon(ring.map(p => [p[1], p[0]]), {color: color, weight: 2.5, fillColor: color, fillOpacity: .12});
    poly.t = t;
    poly.on('click', () => { openTab('chi'); showTo(t); });
    poly.bindTooltip(t.name, {sticky: true});
    toLayer.addLayer(poly);
    const c = poly.getBounds().getCenter();
    L.marker(c, {icon: L.divIcon({className: '', html: '<div style="background:' + color + ';color:#fff;border-radius:8px;padding:2px 8px;font:700 11.5px system-ui;box-shadow:0 2px 6px rgba(0,0,0,.35)">' + t.name + '</div>', iconSize: [0, 0]})}).addTo(toLayer);
  });
}
function aggTo(t) {
  const ids = new Set(t.house_ids);
  const hs = houses.filter(h => ids.has(h.id));
  const a = {n: hs.length, mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, vn: 0, bh: 0};
  hs.forEach(h => { a.mem += h.members; a.eld += h.elderly; a.kid += h.children; if (h.policy) a.pol++; if (h.support) a.sup++; if (h.vneid) a.vn++; if (h.bhyt) a.bh++; });
  return a;
}

// ============ DASHBOARD + BIỂU ĐỒ ============
function renderAll() {
  const tot = {mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, vn: 0, bh: 0};
  houses.forEach(h => { tot.mem += h.members; tot.eld += h.elderly; tot.kid += h.children; if (h.policy) tot.pol++; if (h.support) tot.sup++; if (h.vneid) tot.vn++; if (h.bhyt) tot.bh++; });
  const openRep = reports.filter(r => r.status !== 'Đã xử lý').length;
  document.getElementById('dHos').innerHTML = houses.length + ' <small>hộ</small>';
  document.getElementById('dMem').innerHTML = tot.mem + ' <small>người</small>';
  document.getElementById('dEld').textContent = tot.eld;
  document.getElementById('dKid').textContent = tot.kid;
  document.getElementById('dPol').textContent = tot.pol;
  document.getElementById('dSup').textContent = tot.sup;
  document.getElementById('dVn').innerHTML = Math.round(tot.vn / houses.length * 100) + '<small>%</small>';
  document.getElementById('dRp').textContent = openRep;
  const bd = tos.map((t, i) => ({name: t.name, mem: aggTo(t).mem, color: TO_COLORS[i % TO_COLORS.length]})).sort((a, b) => b.mem - a.mem);
  const max = Math.max(1, ...bd.map(b => b.mem));
  document.getElementById('barChart').innerHTML = bd.map(b =>
    '<div class="hbar"><span class="nm">' + b.name + '</span><span class="tr"><i style="width:' + Math.round(b.mem / max * 100) + '%;background:' + b.color + '"></i></span><span class="vv">' + b.mem + '</span></div>').join('');
  const adults = Math.max(0, tot.mem - tot.eld - tot.kid);
  const pc = x => Math.round(x / Math.max(1, tot.mem) * 100);
  const c1 = pc(tot.kid), c2 = pc(adults), c3 = pc(tot.eld);
  document.getElementById('donut').style.background = 'conic-gradient(#f59e0b 0 ' + c1 + '%, #2563eb ' + c1 + '% ' + (c1 + c2) + '%, #16a34a ' + (c1 + c2) + '% 100%)';
  document.getElementById('donutL').innerHTML =
    '<span><i style="background:#f59e0b"></i>Trẻ em ' + tot.kid + '</span>' +
    '<span><i style="background:#2563eb"></i>Người lớn ' + adults + '</span>' +
    '<span><i style="background:#16a34a"></i>NCT ' + tot.eld + '</span>';
  renderHouses(); renderReps(); renderTos();
}

// ============ PANEL ============
const panel = document.getElementById('panel');
function esc(s) { return String(s == null ? '' : s).replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function bar(pct, color) { return '<div class="bar"><i style="width:' + pct + '%;background:' + color + '"></i></div>'; }
function kv(k, v) { return '<div class="kv"><span>' + k + '</span><b>' + v + '</b></div>'; }
function openTab(t) {
  document.querySelectorAll('#tabs button').forEach(b => b.classList.remove('on'));
  const idx = {chi: 0, ho: 1, an: 2, rep: 3, bc: 4}[t] || 0;
  document.querySelectorAll('#tabs button')[idx].classList.add('on');
  if (t === 'ho') houseList();
  else if (t === 'an') anSinh();
  else if (t === 'rep') repList();
  else if (t === 'bc') baoCao();
  else panel.innerHTML = '<div class="empty">👈 Bấm vào một <b>ngôi nhà</b> hoặc <b>vùng tổ</b> trên bản đồ.</div>';
}
window.openTab = openTab;
function showTo(t) {
  const a = aggTo(t);
  const color = TO_COLORS[(t.id - 1) % TO_COLORS.length];
  const list = houses.filter(h => DATA.to_of[h.id] === t.id);
  panel.innerHTML = '<h2 style="color:' + color + '">🏘 ' + esc(t.name) + ' – Lệ Sơn Nam</h2>' +
    kv('Số hộ', a.n) + kv('Nhân khẩu', a.mem) + kv('Người cao tuổi', a.eld) + kv('Trẻ em', a.kid) +
    kv('Hộ chính sách', a.pol) + kv('Hộ cần hỗ trợ', a.sup) +
    '<div style="margin-top:6px"><b>Tỷ lệ VNeID mức 2:</b> ' + Math.round(a.vn / Math.max(1, a.n) * 100) + '%</div>' + bar(Math.round(a.vn / Math.max(1, a.n) * 100), '#2563eb') +
    '<b>Tỷ lệ BHYT:</b> ' + Math.round(a.bh / Math.max(1, a.n) * 100) + '%' + bar(Math.round(a.bh / Math.max(1, a.n) * 100), '#16a34a') +
    '<h3 style="margin:12px 0 6px">Danh sách hộ (' + list.length + ')</h3>' +
    list.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + ' · ' + h.members + ' người · ' + (h.vneid ? '🟦VNeID' : '⬜') + (h.bhyt ? ' 🟩BHYT' : '') + (h.policy ? ' 🚩' : '') + (h.support ? ' 🆘' : '') + '</div>').join('');
}
window.showHouse = function(h) {
  const near = reports.filter(r => Math.abs(r.pos[0] - h.c[1]) < 0.0012 && Math.abs(r.pos[1] - h.c[0]) < 0.0012);
  panel.innerHTML = '<h2>🏠 ' + esc(h.id) + '</h2>' +
    kv('Chủ hộ (ẩn danh)', esc(h.owner)) + kv('Tổ', 'Tổ ' + toOf(h)) +
    kv('Nhân khẩu', h.members) + kv('Người cao tuổi', h.elderly) + kv('Trẻ em', h.children) +
    kv('Hộ chính sách', h.policy ? 'Có 🚩' : 'Không') + kv('Hộ cần hỗ trợ', h.support ? 'Có 🆘' : 'Không') +
    kv('Thăm hỏi gần nhất', h.lastVisit || 'Chưa ghi nhận') +
    '<div style="margin-top:6px"><b>VNeID mức 2:</b> ' + (h.vneid ? 'Đã định danh' : 'Chưa') + '</div>' + bar(h.vneid ? 100 : 8, '#2563eb') +
    '<b>BHYT:</b> ' + (h.bhyt ? 'Đã có thẻ' : 'Chưa có') + bar(h.bhyt ? 100 : 8, '#16a34a') +
    '<h3 style="margin:12px 0 6px">Phản ánh gần đây</h3>' +
    (near.length ? near.map(r => '<div class="rep">⚠️ ' + r.type + ' · <b>' + r.status + '</b></div>').join('') : '<div class="empty" style="padding:8px">Không có</div>') +
    '<div style="display:flex;gap:6px;margin-top:12px">' +
    '<button class="btn2" onclick="editHouse(\'' + h.id + '\')">✏️ Sửa hộ</button>' +
    '<button class="btn2 gray" onclick="visitHouse(\'' + h.id + '\')">🤝 Thăm hỏi</button>' +
    '<button class="btn2 red" onclick="delHouse(\'' + h.id + '\')">🗑 Xóa</button></div>';
};
window.byId = byId;
window.editHouse = function(id) {
  const h = byId(id); if (!h) return;
  const sel = (v, o) => '<option value="' + o + '"' + (v === (o === '1') ? ' selected' : '') + '>' + (o === '1' ? 'Có' : 'Không') + '</option>';
  panel.innerHTML = '<h2>✏️ Sửa hộ ' + esc(h.id) + '</h2>' +
    '<div class="lbl2">Chủ hộ (ẩn danh)</div><input id="eOwner" value="' + esc(h.owner) + '">' +
    '<div class="lbl2">Nhân khẩu</div><input id="eMem" type="number" min="1" value="' + h.members + '">' +
    '<div class="lbl2">Người cao tuổi</div><input id="eEld" type="number" min="0" value="' + h.elderly + '">' +
    '<div class="lbl2">Trẻ em</div><input id="eKid" type="number" min="0" value="' + h.children + '">' +
    '<div class="lbl2">Hộ chính sách</div><select id="ePol">' + sel(h.policy, 0) + sel(h.policy, 1) + '</select>' +
    '<div class="lbl2">Hộ cần hỗ trợ</div><select id="eSup">' + sel(h.support, 0) + sel(h.support, 1) + '</select>' +
    '<div class="lbl2">VNeID mức 2</div><select id="eVn">' + (h.vneid ? '<option value="1" selected>Đã định danh</option><option value="0">Chưa</option>' : '<option value="0" selected>Chưa</option><option value="1">Đã định danh</option>') + '</select>' +
    '<div class="lbl2">BHYT</div><select id="eBh">' + (h.bhyt ? '<option value="1" selected>Có thẻ</option><option value="0">Chưa</option>' : '<option value="0" selected>Chưa</option><option value="1">Có thẻ</option>') + '</select>' +
    '<div style="display:flex;gap:6px;margin-top:12px"><button class="btn2" onclick="saveHouse(\'' + id + '\')">💾 Lưu</button>' +
    '<button class="btn2 gray" onclick="showHouse(byId(\'' + id + '\'))">Hủy</button></div>';
};
window.saveHouse = function(id) {
  const h = byId(id); if (!h) return;
  h.owner = document.getElementById('eOwner').value.trim() || h.owner;
  h.members = +document.getElementById('eMem').value || 1;
  h.elderly = Math.min(+document.getElementById('eEld').value || 0, h.members);
  h.children = Math.min(+document.getElementById('eKid').value || 0, h.members - h.elderly);
  h.policy = document.getElementById('ePol').value === '1';
  h.support = document.getElementById('eSup').value === '1';
  h.vneid = document.getElementById('eVn').value === '1';
  h.bhyt = document.getElementById('eBh').value === '1';
  store(); renderAll(); showHouse(h);
};
window.delHouse = function(id) {
  if (!confirm('Xóa hộ ' + id + '?')) return;
  houses = houses.filter(h => h.id !== id);
  tos.forEach(t => { t.house_ids = t.house_ids.filter(x => x !== id); });
  store(); renderAll(); openTab('ho');
};
window.visitHouse = function(id) {
  const h = byId(id); if (!h) return;
  h.lastVisit = new Date().toLocaleDateString('vi-VN');
  store(); renderAll(); showHouse(h);
};

// ============ THÊM HỘ / THÊM PHẢN ÁNH (click bản đồ) ============
window.addHouseMode = function() {
  addHouseMode = !addHouseMode; addRepMode = false;
  map.getContainer().style.cursor = addHouseMode ? 'crosshair' : '';
  if (addHouseMode) panel.innerHTML = '<div class="rep">📍 Bấm vào bản đồ để đặt vị trí nhà mới...</div>';
};
window.addRepMode2 = function() {
  addRepMode = !addRepMode; addHouseMode = false;
  map.getContainer().style.cursor = addRepMode ? 'crosshair' : '';
  if (addRepMode) panel.innerHTML = '<div class="rep">📍 Bấm vào bản đồ để ghi vị trí phản ánh...</div>';
};
map.on('click', e => {
  if (addHouseMode) {
    addHouseMode = false; map.getContainer().style.cursor = '';
    const c = e.latlng, d = 0.00009;
    const geom = [[c.lng - d, c.lat - d], [c.lng + d, c.lat - d], [c.lng + d, c.lat + d], [c.lng - d, c.lat + d], [c.lng - d, c.lat - d]];
    const id = 'LSN-H' + String(houses.length + 1).padStart(3, '0');
    const h = {id: id, owner: 'Hộ mới', members: 2, elderly: 0, children: 0, policy: false, support: false, vneid: false, bhyt: false, geom: geom, c: [c.lng, c.lat]};
    houses.push(h);
    let best = tos[0], bd = 1e9;
    tos.forEach(t => { const hs = houses.filter(x => t.house_ids.includes(x.id)); if (hs.length) { const cx = hs.reduce((s, x) => s + x.c[0], 0) / hs.length, cy = hs.reduce((s, x) => s + x.c[1], 0) / hs.length; const d2 = (cx - c.lng) ** 2 + (cy - c.lat) ** 2; if (d2 < bd) { bd = d2; best = t; } } });
    best.house_ids.push(id); DATA.to_of[id] = best.id;
    store(); renderAll(); editHouse(id);
  } else if (addRepMode) {
    addRepMode = false; map.getContainer().style.cursor = '';
    const types = ['Đèn đường hỏng', 'Đường xuống cấp', 'Rác thải tồn đọng', 'Ngập nước', 'An ninh'];
    const colors = ['#f59e0b', '#dc2626', '#16a34a', '#2563eb', '#7c3aed'];
    const t = types[reports.length % types.length];
    reports.push({id: 'PR-' + String(reports.length + 1).padStart(3, '0'), type: t, color: colors[reports.length % colors.length], desc: 'Phản ánh mới: ' + t, pos: [e.latlng.lat, e.latlng.lng], status: 'Mới'});
    store(); renderAll(); openTab('rep');
  }
});

// ============ HỘ DÂN ============
window.houseList = function() {
  const fTo = document.getElementById('fTo') ? document.getElementById('fTo').value : 'all';
  const fStatus = document.getElementById('fStatus') ? document.getElementById('fStatus').value : 'all';
  const list = houses.filter(h => {
    if (fTo !== 'all' && toOf(h) !== +fTo) return false;
    const st = (h.support ? 'sup' : '') + (h.policy ? 'pol' : '') + (!h.vneid ? 'vn' : '') + (!h.bhyt ? 'bh' : '');
    if (fStatus !== 'all' && !st.includes(fStatus)) return false;
    return true;
  });
  panel.innerHTML = '<h2>📋 Hộ dân (' + list.length + ')</h2>' +
    '<div class="lbl2">Lọc theo tổ</div><select id="fTo"><option value="all">Tất cả tổ</option>' + tos.map(t => '<option value="' + t.id + '">' + t.name + '</option>').join('') + '</select>' +
    '<div class="lbl2">Lọc trạng thái</div><select id="fStatus"><option value="all">Tất cả</option><option value="sup">Cần hỗ trợ</option><option value="pol">Chính sách</option><option value="vn">Chưa VNeID</option><option value="bh">Chưa BHYT</option></select>' +
    '<button class="btn2" style="width:100%;margin-top:8px" onclick="addHouseMode()">➕ Thêm hộ (bấm bản đồ)</button>' +
    list.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + ' · ' + h.members + ' người · Tổ ' + toOf(h) + (h.vneid ? ' 🟦' : '') + (h.bhyt ? ' 🟩' : '') + (h.policy ? ' 🚩' : '') + (h.support ? ' 🆘' : '') + '</div>').join('') ||
    '<div class="empty">Không có hộ phù hợp</div>';
  document.getElementById('fTo').onchange = houseList;
  document.getElementById('fStatus').onchange = houseList;
};

// ============ AN SINH ============
window.anSinh = function() {
  const sup = houses.filter(h => h.support);
  const pol = houses.filter(h => h.policy);
  const alone = houses.filter(h => h.members === 1 && h.elderly >= 1);
  const kid2 = houses.filter(h => h.children >= 2);
  panel.innerHTML = '<h2>🤝 An sinh xã hội</h2>' +
    '<h3 style="margin:8px 0 4px">🆘 Hộ cần hỗ trợ (' + sup.length + ')</h3>' +
    (sup.length ? sup.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + ' · ' + h.members + ' người · ' + (h.lastVisit ? 'Thăm: ' + h.lastVisit : 'Chưa thăm') + '</div>').join('') : '<div class="empty">Không có</div>') +
    '<h3 style="margin:12px 0 4px">🚩 Hộ chính sách (' + pol.length + ')</h3>' +
    (pol.length ? pol.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + '</div>').join('') : '<div class="empty">Không có</div>') +
    '<h3 style="margin:12px 0 4px">👴 NCT sống một mình (' + alone.length + ')</h3>' +
    (alone.length ? alone.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + '</div>').join('') : '<div class="empty">Không có</div>') +
    '<h3 style="margin:12px 0 4px">🧒 Gia đình đông trẻ em (' + kid2.length + ')</h3>' +
    (kid2.length ? kid2.map(h => '<div class="row" onclick="showHouse(byId(\'' + h.id + '\'))"><b>' + h.id + '</b> · ' + esc(h.owner) + ' · ' + h.children + ' trẻ</div>').join('') : '<div class="empty">Không có</div>');
};

// ============ PHẢN ÁNH ============
window.repList = function() {
  panel.innerHTML = '<h2>⚠️ Phản ánh hạ tầng (' + reports.filter(r => r.status !== 'Đã xử lý').length + ' đang xử lý)</h2>' +
    '<button class="btn2" style="width:100%;margin-bottom:8px" onclick="addRepMode2()">➕ Thêm phản ánh (bấm bản đồ)</button>' +
    reports.map(r => '<div class="rep" id="rep-' + r.id + '"><b>' + r.id + '</b> · ' + r.type + '<br>' + esc(r.desc) +
      '<br>Trạng thái: <select onchange="setRepStatus(\'' + r.id + '\', this.value)">' +
      ['Mới', 'Đang xử lý', 'Đã xử lý'].map(s => '<option' + (r.status === s ? ' selected' : '') + '>' + s + '</option>').join('') + '</select></div>').join('');
};
window.setRepStatus = function(id, st) {
  const r = reports.find(x => x.id === id); if (r) { r.status = st; store(); renderAll(); }
};

// ============ BÁO CÁO ============
window.baoCao = function() {
  const rows = tos.map(t => { const a = aggTo(t); return '<tr><td>' + t.name + '</td><td>' + a.n + '</td><td>' + a.mem + '</td><td>' + a.eld + '</td><td>' + a.kid + '</td><td>' + a.pol + '</td><td>' + a.sup + '</td><td>' + Math.round(a.vn / Math.max(1, a.n) * 100) + '%</td></tr>'; }).join('');
  const tot = houses.reduce((s, h) => { s.mem += h.members; s.eld += h.elderly; s.kid += h.children; if (h.policy) s.pol++; if (h.support) s.sup++; return s; }, {mem: 0, eld: 0, kid: 0, pol: 0, sup: 0});
  const open = reports.filter(r => r.status !== 'Đã xử lý');
  panel.innerHTML = '<h2>📄 Báo cáo</h2>' +
    '<div class="rep">Số liệu tổng hợp theo tổ, cập nhật ' + new Date().toLocaleDateString('vi-VN') + '</div>' +
    '<table style="width:100%;border-collapse:collapse;font-size:12px;margin:8px 0"><tr style="background:#f9fafb"><th style="text-align:left">Tổ</th><th>Hộ</th><th>Khẩu</th><th>NCT</th><th>Trẻ</th><th>CS</th><th>HT</th><th>VNeID</th></tr>' + rows + '</table>' +
    kv('Tổng hộ', houses.length) + kv('Tổng nhân khẩu', tot.mem) + kv('Hộ chính sách', tot.pol) + kv('Hộ cần hỗ trợ', tot.sup) + kv('Phản ánh đang xử lý', open.length) +
    '<div style="display:flex;gap:6px;margin-top:12px"><button class="btn2" onclick="printReport()">🖨 In báo cáo</button>' +
    '<button class="btn2 gray" onclick="exportCSV()">⬇ Xuất CSV</button></div>';
};
function printReport() {
  const rows = tos.map(t => { const a = aggTo(t); return '<tr><td>' + t.name + '</td><td>' + a.n + '</td><td>' + a.mem + '</td><td>' + a.eld + '</td><td>' + a.kid + '</td><td>' + a.pol + '</td><td>' + a.sup + '</td></tr>'; }).join('');
  const tot = houses.reduce((s, h) => { s.mem += h.members; s.eld += h.elderly; s.kid += h.children; if (h.policy) s.pol++; if (h.support) s.sup++; return s; }, {mem: 0, eld: 0, kid: 0, pol: 0, sup: 0});
  const open = reports.filter(r => r.status !== 'Đã xử lý');
  document.getElementById('reportArea').innerHTML =
    '<h2>ỦY BAN NHÂN DÂN XÃ HÒA TIẾN</h2>' +
    '<h2 style="text-align:center">BÁO CÁO NHÂN HỘ KHẨU – THÔN LỆ SƠN NAM</h2>' +
    '<p>Ngày lập: ' + new Date().toLocaleDateString('vi-VN') + ' · Bản demo dữ liệu mô phỏng (Nghị định 13/2023/NĐ-CP)</p>' +
    '<table><tr><th>Tổ</th><th>Số hộ</th><th>Nhân khẩu</th><th>NCT</th><th>Trẻ em</th><th>Chính sách</th><th>Cần hỗ trợ</th></tr>' + rows + '</table>' +
    '<p><b>Tổng hợp:</b> ' + houses.length + ' hộ · ' + tot.mem + ' nhân khẩu · ' + tot.pol + ' hộ chính sách · ' + tot.sup + ' hộ cần hỗ trợ · ' + open.length + ' phản ánh đang xử lý.</p>' +
    '<p style="margin-top:40px;text-align:right">Trưởng thôn<br><i>(Ký, ghi rõ họ tên)</i></p>';
  window.print();
}
window.printReport = printReport;
window.exportCSV = function() {
  const head = 'Mã hộ,Chủ hộ (ẩn danh),Tổ,Nhân khẩu,NCT,Trẻ em,Chính sách,Cần hỗ trợ,VNeID,BHYT,Thăm hỏi';
  const rows = houses.map(h => [h.id, '"' + h.owner + '"', toOf(h), h.members, h.elderly, h.children, h.policy ? 'Có' : '', h.support ? 'Có' : '', h.vneid ? 'Có' : 'Chưa', h.bhyt ? 'Có' : 'Chưa', h.lastVisit || ''].join(','));
  const blob = new Blob(['\ufeff' + head + '\n' + rows.join('\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'le-son-nam-ho-dan.csv'; a.click();
};

// ============ SEARCH CHỦ HỘ ============
function norm(s) { return String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
const sBox = document.getElementById('searchBox'), sRes = document.getElementById('searchRes');
sBox.addEventListener('input', () => {
  const q = norm(sBox.value.trim());
  if (!q) { sRes.style.display = 'none'; return; }
  const hits = houses.filter(h => norm(h.owner + ' ' + h.id).includes(q)).slice(0, 10);
  sRes.innerHTML = hits.length ? hits.map(h => '<div class="r" onclick="searchGo(\'' + h.id + '\')">🏠 <b>' + esc(h.id) + '</b> · ' + esc(h.owner) + ' · ' + h.members + ' người · Tổ ' + toOf(h) + '</div>').join('') : '<div class="r" style="color:#888">Không tìm thấy</div>';
  sRes.style.display = 'block';
});
window.searchGo = function(id) {
  sRes.style.display = 'none'; sBox.value = '';
  const h = byId(id); if (!h) return;
  map.flyTo([h.c[1], h.c[0]], 19);
  openTab('chi'); showHouse(h);
  houseLayer.eachLayer(l => { if (l.h && l.h.id === id) l.openPopup(); });
};

// ============ BỘ LỌC ============
let fSup = false, fPol = false, fVn = false, fBh = false, fRep = false;
function applyFilter() {
  houseLayer.eachLayer(l => {
    const h = l.h;
    const on = (!fSup || h.support) && (!fPol || h.policy) && (!fVn || h.vneid) && (!fBh || h.bhyt);
    l.setStyle({fillOpacity: on ? .55 : .06, opacity: on ? 1 : .35, weight: on ? 2 : 1});
  });
  repLayer.eachLayer(m => m.setStyle({fillOpacity: fRep ? 1 : .18, opacity: fRep ? 1 : .5}));
}
function tog(k) {
  const btns = document.querySelectorAll('#filters button');
  if (k === 'sup') { fSup = !fSup; btns[0].classList.toggle('active', fSup); }
  if (k === 'pol') { fPol = !fPol; btns[1].classList.toggle('active', fPol); }
  if (k === 'vneid') { fVn = !fVn; btns[2].classList.toggle('active', fVn); }
  if (k === 'bhyt') { fBh = !fBh; btns[3].classList.toggle('active', fBh); }
  if (k === 'rep') { fRep = !fRep; btns[4].classList.toggle('active', fRep); }
  applyFilter();
}

// ============ DEMO 60S ============
let demoRunning = false;
window.startDemo = function() {
  if (demoRunning) return; demoRunning = true;
  const steps = [];
  tos.forEach((t, i) => steps.push(() => { openTab('chi'); showTo(t); }));
  steps.push(() => { openTab('an'); anSinh(); });
  steps.push(() => { openTab('rep'); repList(); });
  steps.push(() => { openTab('bc'); baoCao(); });
  let k = 0;
  const tick = () => { if (k < steps.length) { steps[k++](); setTimeout(tick, 1700); } else demoRunning = false; };
  map.flyTo([15.9606, 108.1855], 16);
  setTimeout(tick, 700);
};

// ============ KHỞI TẠO ============
renderAll();
</script>
</body>
</html>
"""

PAGE = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))

with open("smart-village.html", "w") as f:
    f.write(PAGE)
print("WROTE smart-village.html", len(PAGE), "bytes |", N, "nhà,", len(tos), "tổ,", len(reports), "phản ánh")
