#!/usr/bin/env python3
"""Generate a self-contained Leaflet app — Quản lý nhà / hộ khẩu / tổ dân cư Thôn Lệ Sơn Nam.

- Nền: OSM / Esri / Google vệ tinh (tham chiếu)
- Vẽ nhà tay (footprint) + vẽ ranh giới tổ/khu dân cư
- Mỗi hộ: chủ hộ, số nhà, nhân khẩu, NCT, trẻ em, hộ chính sách, hộ cần hỗ trợ, loại nhà
- Click tổ → tổng hợp: số hộ, nhân khẩu, NCT, trẻ em, hộ chính sách, hộ cần hỗ trợ
- Bộ lọc: hộ cần hỗ trợ / hộ chính sách / công trình
- Lưu localStorage, xuất/import GeoJSON
"""
import json

def inline(path):
    try:
        with open(path) as f:
            return json.dumps(json.load(f), ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({"type": "FeatureCollection", "features": []}, ensure_ascii=False)

ROADS = inline("data/zone_roads.geojson")
EXTENT = inline("data/zone_extent.geojson")

HELP_TEXT = (
    "1) Lớp nền: chọn \"Google Vệ tinh\" / \"Google Hybrid\" để thấy rõ mái nhà.\n"
    "2) VẼ NHÀ: bấm 🏘 Vẽ nhà → chọn ▢/đa giác ở cột trái → khoanh mái nhà → điền thông tin hộ → Lưu.\n"
    "3) VẼ TỔ: bấm 🏘 Vẽ tổ → vẽ ranh giới tổ/khu dân cư → gõ tên (Tổ 1, Tổ 2...).\n"
    "   Click vào tổ → hiện bảng tổng hợp: số hộ, nhân khẩu, NCT, trẻ em, hộ chính sách, hộ cần hỗ trợ.\n"
    "4) CLICK NHÀ: hiện chi tiết hộ → ✏️ Sửa / 🗑 Xóa.\n"
    "5) 📊 Thống kê: bảng tổng hợp toàn thôn theo tổ.\n"
    "6) BỘ LỌC: bấm các nút lọc (Cần hỗ trợ / Chính sách / Công trình) để tô màu nổi bật hộ tương ứng.\n"
    "7) 📋 Danh sách: xem tổ + nhà, nhấp để nhảy tới.\n"
    "8) ⬇ Xuất GeoJSON để tải dữ liệu (JOSM / iD / app riêng).\n\n"
    "Mọi thay đổi tự lưu — reload không mất dữ liệu."
)

PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quản lý nhà & tổ dân cư – Thôn Lệ Sơn Nam</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"/>
<style>
  :root {
    --primary:#16a34a; --accent:#f59e0b; --danger:#dc2626; --blue:#2563eb;
    --purple:#7c3aed; --text:#1f2937; --muted:#6b7280; --line:#e5e7eb;
    --card:#ffffff; --shadow:0 6px 24px rgba(17,24,39,.14);
    --radius:14px;
  }
  * { box-sizing: border-box; }
  html, body { height:100%; margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; color:var(--text); }
  #map { height:100%; }
  /* thanh trạng thái */
  #bar { position:absolute; z-index:1000; bottom:0; left:0; right:0;
         background:linear-gradient(90deg,#14532d,#166534 55%,#15803d);
         color:#eafff1; font:12px/1.7 system-ui; padding:5px 14px; display:flex; gap:14px;
         box-shadow:0 -2px 10px rgba(0,0,0,.2); align-items:center; flex-wrap:wrap; }
  #bar b { color:#fde68a; }
  #bar .c { color:#bbf7d0; font-family:ui-monospace,Menlo,monospace; }
  #bar .chip { background:rgba(255,255,255,.14); border-radius:999px; padding:1px 10px; font-size:11px; }
  /* nút xuất */
  #exportBtn { position:absolute; z-index:1000; top:12px; right:12px;
               background:linear-gradient(135deg,#16a34a,#15803d); color:#fff; border:none;
               border-radius:10px; padding:9px 14px; font:600 13px system-ui; cursor:pointer;
               box-shadow:0 4px 12px rgba(22,163,74,.35); transition:transform .12s; }
  #exportBtn:hover { transform:translateY(-1px); }
  /* thanh công cụ */
  #tools { position:absolute; z-index:1000; top:12px; left:56px; display:flex; align-items:center;
           gap:2px; flex-wrap:wrap; max-width:700px;
           background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:var(--radius);
           padding:5px 6px; box-shadow:var(--shadow); backdrop-filter:blur(8px); }
  #tools .sep { width:1px; height:22px; background:var(--line); margin:0 4px; }
  #tools button { border:none; background:transparent; padding:7px 11px; border-radius:9px;
                  font:600 13px system-ui; color:var(--text); cursor:pointer; white-space:nowrap;
                  transition:background .15s,color .15s; }
  #tools button:hover { background:#f0fdf4; }
  #tools button.active { background:#dcfce7; color:#166534; box-shadow:inset 0 0 0 1px #86efac; }
  #tools button.danger:hover { background:#fef2f2; color:var(--danger); }
  /* bộ lọc */
  #filters { position:absolute; z-index:1000; top:66px; left:56px; display:flex; gap:8px;
             background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:999px;
             padding:5px 8px; box-shadow:var(--shadow); backdrop-filter:blur(8px); }
  #filters button { border:1.5px solid var(--line); background:#fff; border-radius:999px; padding:4px 12px;
                    font:600 12.5px system-ui; cursor:pointer; transition:all .15s; }
  #filters button:hover { border-color:#fca5a5; }
  #filters button.active { background:#fee2e2; border-color:var(--danger); color:#991b1b; }
  #filters button.active.blue { background:#dbeafe; border-color:var(--blue); color:#1e40af; }
  #filters button.active.purple { background:#f3e8ff; border-color:var(--purple); color:#6b21a8; }
  /* ô tìm kiếm */
  #searchBox { position:absolute; z-index:1000; top:108px; left:56px; width:300px;
               font:13px system-ui; padding:9px 12px; border:1px solid var(--line); border-radius:12px;
               box-shadow:var(--shadow); outline:none; transition:border .15s; }
  #searchBox:focus { border-color:var(--primary); }
  /* bảng danh sách + thống kê */
  #listPanel, #statsPanel { position:absolute; z-index:1000; top:150px; left:56px; width:360px; max-height:62%;
               background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
               box-shadow:var(--shadow); display:none; overflow-y:auto; font:13px system-ui; }
  #statsPanel { left:428px; }
  #listPanel h3, #statsPanel h3 { position:sticky; top:0; margin:0; padding:10px 14px;
               background:#f9fafb; border-bottom:1px solid var(--line); font-size:14px; font-weight:700; }
  #listPanel .row { padding:8px 14px; border-bottom:1px solid #f3f4f6; cursor:pointer;
                    display:flex; justify-content:space-between; gap:8px; transition:background .12s; }
  #listPanel .row:hover { background:#f0fdf4; }
  #listPanel .row b { color:var(--primary); font-weight:600; }
  #listPanel .cnt { color:var(--muted); font-size:12px; white-space:nowrap; }
  #listPanel .row.to { background:#fffbeb; }
  #listPanel .row.to b { color:#b45309; }
  #listPanel .row.to:hover { background:#fef3c7; }
  #statsPanel table { width:100%; border-collapse:collapse; font-size:12.5px; }
  #statsPanel th { position:sticky; top:39px; background:#f9fafb; }
  #statsPanel th, #statsPanel td { padding:5px 6px; border-bottom:1px solid #f3f4f6; text-align:right; }
  #statsPanel td:first-child, #statsPanel th:first-child { text-align:left; font-weight:600; }
  #statsPanel tr.total td { font-weight:800; background:#fef3c7; }
  #statsPanel tr:hover td { background:#f9fafb; }
  /* chú giải */
  .legend { position:absolute; z-index:1000; bottom:44px; right:12px; background:rgba(255,255,255,.94);
            padding:10px 14px; font:12.5px system-ui; border-radius:var(--radius); box-shadow:var(--shadow);
            border:1px solid var(--line); line-height:1.9; }
  .legend i { display:inline-block; width:13px; height:13px; margin-right:7px; vertical-align:-2px;
              border-radius:3px; }
  /* popup */
  .leaflet-popup-content-wrapper { border-radius:12px; box-shadow:var(--shadow); }
  .leaflet-popup-content { font:13px system-ui; color:var(--text); margin:12px 14px; }
  .leaflet-popup-content b { color:var(--text); }
  .leaflet-popup-content .pt { font-weight:800; font-size:14px; display:block; margin-bottom:6px; }
  .info-table { border-collapse:collapse; font-size:13px; margin:4px 0 8px; width:100%; }
  .info-table td { padding:3px 14px 3px 0; color:var(--muted); }
  .info-table td:last-child { color:var(--text); font-weight:600; text-align:right; }
  .leaflet-popup-content button { background:#f3f4f6; border:1px solid #d1d5db; border-radius:8px;
                  padding:5px 12px; margin:6px 4px 0 0; cursor:pointer; font:600 12.5px system-ui;
                  color:var(--text); transition:background .15s; }
  .leaflet-popup-content button:hover { background:#e5e7eb; }
  .leaflet-popup-content button.primary { background:var(--primary); color:#fff; border-color:var(--primary); }
  .leaflet-popup-content button.primary:hover { background:#15803d; }
  .leaflet-popup-content input, .leaflet-popup-content select {
                  border:1px solid #d1d5db; border-radius:7px; padding:5px 7px; font:13px system-ui;
                  outline:none; margin:2px 0; }
  .leaflet-popup-content input:focus, .leaflet-popup-content select:focus { border-color:var(--primary); }
  ::-webkit-scrollbar { width:9px; height:9px; }
  ::-webkit-scrollbar-thumb { background:#d1d5db; border-radius:8px; }
  ::-webkit-scrollbar-thumb:hover { background:#9ca3af; }
</style>
</head>
<body>
<div id="map"></div>
<div id="tools">
  <button id="btnMode" title="Chuyển chế độ vẽ: nhà ↔ tổ">🏘 Vẽ nhà</button>
  <span class="sep"></span>
  <button id="btnList" title="Hiện/ẩn danh sách">📋 Danh sách</button>
  <button id="btnStats" title="Bảng thống kê theo tổ">📊 Thống kê</button>
  <span class="sep"></span>
  <button id="btnMoc" title="Đặt mốc">📌 Đặt mốc</button>
  <button id="btnImport" title="Nạp file GeoJSON">📂 Import</button>
  <button id="btnClear" class="danger" title="Xóa toàn bộ dữ liệu">🗑 Xóa hết</button>
  <button id="btnHelp">❓ Hướng dẫn</button>
</div>
<div id="filters">
  <button id="fltSupport" title="Tô nổi hộ cần hỗ trợ">🆘 Cần hỗ trợ</button>
  <button id="fltPolicy" class="blue" title="Tô nổi hộ chính sách">🚩 Chính sách</button>
  <button id="fltCT" class="purple" title="Tô nổi công trình">🏗 Công trình</button>
</div>
<input type="file" id="fileImport" accept=".geojson,.json" style="display:none">
<input id="searchBox" placeholder="🔍 Tìm kiếm (vd: nhà văn hóa, ĐH409...) — Enter">
<div id="listPanel"><h3>📋 Danh sách tổ & nhà</h3><div id="listBody"></div></div>
<div id="statsPanel"><h3>📊 Thống kê theo tổ</h3><div id="statsBody"></div></div>
<div id="bar"><b>Quản lý nhà & tổ dân cư – Thôn Lệ Sơn Nam + Lệ Sơn Bắc</b> · Hòa Tiến, Hòa Vang, Đà Nẵng ·
  con trỏ: <span class="c" id="coord">–</span></div>
<div class="legend">
  <i style="background:#00a651"></i> Nhà ở<br>
  <i style="background:#e74c3c"></i> Hộ cần hỗ trợ<br>
  <i style="background:#2980b9"></i> Hộ chính sách<br>
  <i style="background:#8e44ad"></i> Công trình<br>
  <i style="background:#ffeaa7;border:1px solid #b7791f"></i> Ranh giới tổ<br>
  <i style="background:#ff4d4d;border-radius:50%"></i> Mốc thôn (Kiệt 1 / Kiệt 12)
</div>
<button id="exportBtn" class="leaflet-bar">⬇ Xuất GeoJSON</button>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
<script>
const roads = __ROADS__;
const extent = __EXTENT__;

const map = L.map('map', {preferCanvas: true}).setView([15.9606, 108.1855], 16);

// ---- Base layers ----
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 19, attribution: '&copy; OpenStreetMap'});
const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {maxZoom: 19, attribution: 'Tiles &copy; Esri'});
const esriHybrid = L.layerGroup([
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19}),
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, opacity: .9})
]);
const gAttrib = 'Tiles &copy; Google (truy cập không chính thức, dễ bị chặn)';
const googleRoad = L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
  {maxZoom: 20, subdomains: ['mt0','mt1','mt2','mt3'], attribution: gAttrib});
const googleSat = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
  {maxZoom: 20, subdomains: ['mt0','mt1','mt2','mt3'], attribution: gAttrib});
const googleHybrid = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
  {maxZoom: 20, subdomains: ['mt0','mt1','mt2','mt3'], attribution: gAttrib});
esriSat.addTo(map);

// ---- Đường ----
const roadLayer = L.geoJSON(roads, {
  style: f => ({
    color: f.properties.highway === 'primary' ? '#e67e22' :
           f.properties.highway === 'secondary' ? '#f0a020' : '#7fb2d6',
    weight: f.properties.highway === 'service' ? 1.5 : 3, opacity: .9
  }),
  onEachFeature: (f, l) => { if (f.properties.name) l.bindTooltip(f.properties.name, {sticky: true}); }
}).addTo(map);

// ---- Mốc thôn ----
const kiet1 = L.circleMarker([15.9610, 108.1827], {radius: 9, color: '#ff4d4d', weight: 2.5, fillColor: '#fff', fillOpacity: 1})
  .addTo(map).bindPopup('<b>Kiệt 1 Đường ĐH409</b><br>Thôn Lệ Sơn Nam<br>(15.96100, 108.18270)');
const kiet12 = L.circleMarker([15.9627, 108.1793], {radius: 9, color: '#ff4d4d', weight: 2.5, fillColor: '#fff', fillOpacity: 1})
  .addTo(map).bindPopup('<b>Kiệt 12 Đường ĐH409</b><br>Thôn Lệ Sơn Bắc<br>(15.96269, 108.17934)');
const extentLayer = L.geoJSON(extent, {style: {color: '#e67e22', weight: 2, dashArray: '6 4', fill: false}}).addTo(map);

L.control.layers(
  {'Bản đồ OSM': osm, 'Vệ tinh (Esri)': esriSat, 'Vệ tinh + tên đường (Esri)': esriHybrid,
   'Google Maps (road)': googleRoad, 'Google Vệ tinh': googleSat, 'Google Hybrid': googleHybrid},
  {'Đường OSM': roadLayer, 'Phạm vi ước tính': extentLayer, 'Mốc thôn': L.layerGroup([kiet1, kiet12])}
).addTo(map);

// ================= DỮ LIỆU =================
const STORE_KEY = 'lesonnam_household_v3';
const drawn = L.featureGroup().addTo(map);      // nhà
const totLayer = L.featureGroup().addTo(map);   // tổ
const mocLayer = L.featureGroup().addTo(map);   // mốc
let uid = 1;

function props(l) { return (l.feature && l.feature.properties) || {}; }
function esc(s) { return String(s == null ? '' : s).replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function num(v) { const n = parseInt(v, 10); return isNaN(n) ? 0 : n; }

// ================= VẼ (nhà ↔ tổ) =================
const houseDrawControl = new L.Control.Draw({
  edit: {featureGroup: drawn},
  draw: {polygon: {allowIntersection: false, shapeOptions: {color: '#00a651'}}, rectangle: true,
         polyline: false, circle: false, circlemarker: false, marker: false}
});
const toDrawControl = new L.Control.Draw({
  edit: {featureGroup: totLayer},
  draw: {polygon: {allowIntersection: false, shapeOptions: {color: '#b7791f'}}, rectangle: true,
         polyline: false, circle: false, circlemarker: false, marker: false}
});
let drawMode = 'house';
map.addControl(houseDrawControl);
const btnMode = document.getElementById('btnMode');
btnMode.onclick = () => {
  drawMode = (drawMode === 'house') ? 'to' : 'house';
  map.removeControl(drawMode === 'house' ? toDrawControl : houseDrawControl);
  map.addControl(drawMode === 'house' ? houseDrawControl : toDrawControl);
  btnMode.textContent = drawMode === 'house' ? '🏘 Vẽ nhà' : '🏘 Vẽ tổ';
  btnMode.classList.toggle('active', drawMode === 'to');
};

// ================= POPUP: NHÀ =================
function houseInfo(l) {
  const p = props(l);
  const flag = p.support === 'Có' ? ' 🆘' : (p.policy === 'Có' ? ' 🚩' : '');
  return '<div style="min-width:240px">' +
    '<span class="pt">🏠 ' + (esc(p['addr:housenumber']) ? 'Số ' + esc(p['addr:housenumber']) + ' — ' : '') +
      (esc(p.name) || 'Chưa có tên') + flag + '</span>' +
    '<table class="info-table">' +
    '<tr><td>Chủ hộ</td><td><b>' + (esc(p.name) || '—') + '</b></td></tr>' +
    '<tr><td>Số nhà</td><td>' + (esc(p['addr:housenumber']) || '—') + '</td></tr>' +
    '<tr><td>Nhân khẩu</td><td>' + (esc(p.members) || '—') + '</td></tr>' +
    '<tr><td>Người cao tuổi</td><td>' + (esc(p.elderly) || '—') + '</td></tr>' +
    '<tr><td>Trẻ em</td><td>' + (esc(p.children) || '—') + '</td></tr>' +
    '<tr><td>Hộ chính sách</td><td>' + (esc(p.policy) || '—') + '</td></tr>' +
    '<tr><td>Cần hỗ trợ</td><td>' + (esc(p.support) || '—') + '</td></tr>' +
    '<tr><td>Loại</td><td>' + typeName(p.building) + '</td></tr>' +
    '<tr><td>Ghi chú</td><td>' + (esc(p.note) || '—') + '</td></tr>' +
    '</table>' +
    '<button class="primary" onclick="editHouse(this)">✏️ Sửa</button> ' +
    '<button onclick="deleteHouse(this)">🗑 Xóa</button></div>';
}
function typeName(b) {
  if (!b || b === 'house') return 'Nhà ở';
  if (b === 'community_centre') return 'Nhà văn hóa';
  if (b === 'school') return 'Trường học';
  if (b === 'religious') return 'Đình/chùa/miếu';
  return 'Công trình';
}
function houseForm(l) {
  const p = props(l);
  const sel = (v, o) => '<option value="' + o + '"' + (p[v] === o ? ' selected' : '') + '>' + o + '</option>';
  return '<div style="min-width:250px"><b>✏️ Thông tin hộ</b><br>' +
    'Chủ hộ: <input id="fName" value="' + esc(p.name) + '" style="width:200px;margin:3px 0"><br>' +
    'Số nhà: <input id="fNum" value="' + esc(p['addr:housenumber']) + '" style="width:200px;margin:3px 0"><br>' +
    'Nhân khẩu: <input id="fMem" type="number" min="0" value="' + esc(p.members) + '" style="width:200px;margin:3px 0"><br>' +
    'Người cao tuổi: <input id="fEld" type="number" min="0" value="' + esc(p.elderly) + '" style="width:200px;margin:3px 0"><br>' +
    'Trẻ em: <input id="fKid" type="number" min="0" value="' + esc(p.children) + '" style="width:200px;margin:3px 0"><br>' +
    'Hộ chính sách: <select id="fPol" style="width:200px;margin:3px 0">' + sel('policy', 'Không') + sel('policy', 'Có') + '</select><br>' +
    'Cần hỗ trợ: <select id="fSup" style="width:200px;margin:3px 0">' + sel('support', 'Không') + sel('support', 'Có') + '</select><br>' +
    'Loại nhà: <select id="fType" style="width:200px;margin:3px 0">' +
    '<option value="house"' + ((!p.building || p.building === 'house') ? ' selected' : '') + '>Nhà ở</option>' +
    '<option value="community_centre"' + (p.building === 'community_centre' ? ' selected' : '') + '>Nhà văn hóa</option>' +
    '<option value="school"' + (p.building === 'school' ? ' selected' : '') + '>Trường học</option>' +
    '<option value="religious"' + (p.building === 'religious' ? ' selected' : '') + '>Đình/chùa/miếu</option>' +
    '<option value="yes"' + (p.building === 'yes' ? ' selected' : '') + '>Công trình khác</option></select><br>' +
    'Ghi chú: <input id="fNote" value="' + esc(p.note) + '" style="width:200px;margin:3px 0"><br>' +
    '<button class="primary" onclick="saveHouse(this)">💾 Lưu</button> ' +
    '<button onclick="cancelEdit(this)">Hủy</button></div>';
}

// ================= POPUP: TỔ (tổng hợp) =================
function pointInRing(p, ring) {
  const x = p.lat, y = p.lng;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i].lat, yi = ring[i].lng;
    const xj = ring[j].lat, yj = ring[j].lng;
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
function totStats(l) {
  const ring = l.getLatLngs()[0];
  const s = {to: 0, mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, ct: 0};
  drawn.eachLayer(h => {
    if (!pointInRing(h.getBounds().getCenter(), ring)) return;
    const p = props(h);
    s.to++; s.mem += num(p.members); s.eld += num(p.elderly); s.kid += num(p.children);
    if (p.policy === 'Có') s.pol++;
    if (p.support === 'Có') s.sup++;
    if (p.building && p.building !== 'house') s.ct++;
  });
  return s;
}
function toInfo(l) {
  const p = props(l);
  const s = totStats(l);
  return '<div style="min-width:230px">' +
    '<span class="pt">🏘 ' + esc(p.name || 'Tổ') + '</span>' +
    '<table class="info-table">' +
    '<tr><td>Số hộ</td><td><b>' + s.to + '</b></td></tr>' +
    '<tr><td>Nhân khẩu</td><td><b>' + s.mem + '</b></td></tr>' +
    '<tr><td>Người cao tuổi</td><td>' + s.eld + '</td></tr>' +
    '<tr><td>Trẻ em</td><td>' + s.kid + '</td></tr>' +
    '<tr><td>Hộ chính sách</td><td>' + s.pol + '</td></tr>' +
    '<tr><td>Hộ cần hỗ trợ</td><td>' + s.sup + '</td></tr>' +
    '<tr><td>Công trình</td><td>' + s.ct + '</td></tr>' +
    '</table>' +
    '<button class="primary" onclick="renameTo(this)">✏️ Đổi tên</button> ' +
    '<button onclick="deleteTo(this)">🗑 Xóa tổ</button></div>';
}

// ================= THAO TÁC =================
function findLayer(el) {
  const pop = el.closest('.leaflet-popup');
  let layer = null;
  drawn.eachLayer(l => { if (l.getPopup() && l.getPopup().getElement() === pop) layer = l; });
  return layer;
}
window.editHouse = function(btn) { const l = findLayer(btn); if (l) l.setPopupContent(houseForm(l)); };
window.cancelEdit = function(btn) { const l = findLayer(btn); if (l) l.setPopupContent(houseInfo(l)); };
window.deleteHouse = function(btn) {
  const l = findLayer(btn);
  if (l && confirm('Xóa nhà này?')) { drawn.removeLayer(l); saveState(); }
};
window.saveHouse = function(btn) {
  const l = findLayer(btn);
  if (!l) return;
  const p = props(l);
  p.name = document.getElementById('fName').value.trim();
  p['addr:housenumber'] = document.getElementById('fNum').value.trim();
  p.members = document.getElementById('fMem').value.trim();
  p.elderly = document.getElementById('fEld').value.trim();
  p.children = document.getElementById('fKid').value.trim();
  p.policy = document.getElementById('fPol').value;
  p.support = document.getElementById('fSup').value;
  p.building = document.getElementById('fType').value;
  p.note = document.getElementById('fNote').value.trim();
  l.setPopupContent(houseInfo(l));
  saveState();
};
function findToLayer(el) {
  const pop = el.closest('.leaflet-popup');
  let l = null;
  totLayer.eachLayer(t => { if (t.getPopup() && t.getPopup().getElement() === pop) l = t; });
  return l;
}
window.renameTo = function(btn) {
  const l = findToLayer(btn);
  if (!l) return;
  const name = prompt('Tên tổ:', props(l).name || 'Tổ');
  if (name === null) return;
  props(l).name = name;
  l.setPopupContent(toInfo(l));
  saveState();
};
window.deleteTo = function(btn) {
  const l = findToLayer(btn);
  if (l && confirm('Xóa ranh giới tổ này?')) { totLayer.removeLayer(l); saveState(); }
};

// ---- Sự kiện vẽ ----
map.on(L.Draw.Event.CREATED, e => {
  const layer = e.layer;
  if (drawMode === 'to') {
    const name = prompt('Tên tổ (vd: Tổ 1, Tổ 2, Khu dân cư...):', 'Tổ ' + (totLayer.getLayers().length + 1));
    layer.feature = {type: 'Feature', properties: {name: (name || 'Tổ'), type: 'to', note: ''}};
    layer.uid = uid++;
    layer.setStyle({color: '#b7791f', weight: 2, fillColor: '#ffeaa7', fillOpacity: .25});
    layer.bindPopup(function(l) { return toInfo(l); });
    totLayer.addLayer(layer);
    layer.openPopup();           // mở ngay bảng thống kê tổ
  } else {
    layer.feature = {type: 'Feature', properties: {building: 'house', name: '', 'addr:housenumber': '',
      members: '', elderly: '', children: '', policy: 'Không', support: 'Không', note: ''}};
    layer.uid = uid++;
    layer.bindPopup(function(l) { return houseInfo(l); });
    drawn.addLayer(layer);
    layer.setPopupContent(houseForm(layer));  // mở thẳng form nhập khi vẽ xong
    layer.openPopup();
  }
  saveState();
});
map.on(L.Draw.Event.EDITED, saveState);
map.on(L.Draw.Event.DELETED, saveState);

// ================= BỘ LỌC =================
let fSup = false, fPol = false, fCT = false;
function applyFilters() {
  drawn.eachLayer(l => {
    const p = props(l);
    const isCT = !!(p.building && p.building !== 'house');
    const isSup = p.support === 'Có';
    const isPol = p.policy === 'Có';
    let color = isCT ? '#8e44ad' : (isSup ? '#e74c3c' : (isPol ? '#2980b9' : '#00a651'));
    let dim = false;
    if (fSup && !isSup) dim = true;
    if (fPol && !isPol) dim = true;
    if (fCT && !isCT) dim = true;
    l.setStyle({color: color, weight: dim ? 1 : 2, fillColor: color, fillOpacity: dim ? .06 : .5, opacity: dim ? .35 : 1});
  });
}
document.getElementById('fltSupport').onclick = function() { fSup = !fSup; this.classList.toggle('active', fSup); applyFilters(); };
document.getElementById('fltPolicy').onclick = function() { fPol = !fPol; this.classList.toggle('active', fPol); applyFilters(); };
document.getElementById('fltCT').onclick = function() { fCT = !fCT; this.classList.toggle('active', fCT); applyFilters(); };

// ================= LƯU / KHÔI PHỤC =================
function addFeature(f) {
  if (f.geometry.type === 'Point') {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
      .addTo(mocLayer).bindPopup(mocPopup);
    m.feature = {type: 'Feature', properties: f.properties, geometry: null};
    m.name = (f.properties && f.properties.name) || 'Mốc';
    return;
  }
  const l = L.geoJSON(f).getLayers()[0];
  l.feature = f;
  l.uid = uid++;
  if (f.properties && f.properties.type === 'to') {
    l.setStyle({color: '#b7791f', weight: 2, fillColor: '#ffeaa7', fillOpacity: .25});
    l.bindPopup(function(l) { return toInfo(l); });
    totLayer.addLayer(l);
  } else {
    l.bindPopup(function(l) { return houseInfo(l); });
    drawn.addLayer(l);
  }
}
function collectAll() {
  const features = [];
  totLayer.eachLayer(t => {
    const g = t.toGeoJSON();
    const p = props(t);
    g.properties = Object.assign({}, g.properties, {type: 'to', name: p.name || 'Tổ', note: p.note || 'Ranh giới tổ dân cư (vẽ tay)'});
    features.push(g);
  });
  drawn.eachLayer(l => {
    const g = l.toGeoJSON();
    const p = props(l);
    g.properties = Object.assign({}, g.properties, {
      building: p.building || 'house',
      name: p.name || undefined,
      'addr:housenumber': p['addr:housenumber'] || undefined,
      members: p.members || undefined,
      elderly: p.elderly || undefined,
      children: p.children || undefined,
      policy: p.policy === 'Có' ? 'yes' : 'no',
      support: p.support === 'Có' ? 'yes' : 'no',
      note: p.note || undefined,
      source: 'vẽ tay từ ảnh vệ tinh – thôn Lệ Sơn Nam'
    });
    features.push(g);
  });
  mocLayer.eachLayer(m => {
    const ll = m.getLatLng();
    features.push({type: 'Feature',
      properties: {name: m.name || 'Mốc', marker: 'Mốc tham chiếu', note: 'Mốc tham chiếu'},
      geometry: {type: 'Point', coordinates: [ll.lng, ll.lat]}});
  });
  return features;
}
function saveState() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(collectAll())); } catch (e) {}
  refreshList();
  refreshStats();
  applyFilters();
}
function restoreState() {
  let features = [];
  try { features = JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { features = []; }
  features.forEach(addFeature);
}

// ================= DANH SÁCH =================
function refreshList() {
  const body = document.getElementById('listBody');
  const rows = [];
  totLayer.eachLayer(t => {
    const p = props(t);
    rows.push({uid: t.uid, kind: 'to', label: '🏘 ' + (p.name || 'Tổ'), detail: ''});
  });
  drawn.eachLayer(l => {
    const p = props(l);
    const flag = p.support === 'Có' ? ' 🆘' : (p.policy === 'Có' ? ' 🚩' : '');
    const numS = p['addr:housenumber'] ? 'Số ' + p['addr:housenumber'] + ' — ' : '';
    rows.push({uid: l.uid, kind: 'house', label: numS + (p.name || 'Nhà') + flag,
      detail: p.members ? ' · ' + p.members + ' người' : ''});
  });
  body.innerHTML = rows.map(r =>
    '<div class="row ' + (r.kind === 'to' ? 'to' : '') + '" onclick="gotoItem(' + r.uid + ')">' +
    '<b>' + r.label + '</b><span class="cnt">' + r.detail + '</span></div>').join('') ||
    '<div class="row" style="color:#888">Chưa có dữ liệu. Vẽ nhà / vẽ tổ trên bản đồ.</div>';
  document.getElementById('btnList').textContent = '📋 Danh sách (' + rows.length + ')';
}
window.gotoItem = function(uid) {
  totLayer.eachLayer(t => { if (t.uid === uid) { map.flyTo(t.getBounds().getCenter(), 16); t.openPopup(); } });
  drawn.eachLayer(l => { if (l.uid === uid) { map.flyTo(l.getBounds().getCenter(), 19); l.openPopup(); } });
};
document.getElementById('btnList').onclick = () => {
  const p = document.getElementById('listPanel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
  refreshList();
};

// ================= THỐNG KÊ =================
function refreshStats() {
  const rows = [];
  const tot = {name: 'Tổng toàn thôn', to: 0, mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, ct: 0};
  totLayer.eachLayer(t => {
    const s = totStats(t);
    rows.push({name: props(t).name || 'Tổ', to: s.to, mem: s.mem, eld: s.eld, kid: s.kid, pol: s.pol, sup: s.sup, ct: s.ct});
    tot.to += s.to; tot.mem += s.mem; tot.eld += s.eld; tot.kid += s.kid;
    tot.pol += s.pol; tot.sup += s.sup; tot.ct += s.ct;
  });
  // nhà ngoài tổ
  const out = {to: 0, mem: 0, eld: 0, kid: 0, pol: 0, sup: 0, ct: 0};
  drawn.eachLayer(h => {
    const c = h.getBounds().getCenter();
    let inTo = false;
    totLayer.eachLayer(t => { if (pointInRing(c, t.getLatLngs()[0])) inTo = true; });
    if (inTo) return;
    const p = props(h);
    out.to++; out.mem += num(p.members); out.eld += num(p.elderly); out.kid += num(p.children);
    if (p.policy === 'Có') out.pol++;
    if (p.support === 'Có') out.sup++;
    if (p.building && p.building !== 'house') out.ct++;
  });
  if (out.to > 0) rows.push({name: 'Chưa phân tổ', to: out.to, mem: out.mem, eld: out.eld, kid: out.kid, pol: out.pol, sup: out.sup, ct: out.ct});
  tot.to += out.to; tot.mem += out.mem; tot.eld += out.eld; tot.kid += out.kid;
  tot.pol += out.pol; tot.sup += out.sup; tot.ct += out.ct;

  const tr = r => '<tr><td>' + r.name + '</td><td>' + r.to + '</td><td>' + r.mem + '</td><td>' + r.eld + '</td><td>' + r.kid + '</td><td>' + r.pol + '</td><td>' + r.sup + '</td><td>' + r.ct + '</td></tr>';
  document.getElementById('statsBody').innerHTML =
    '<table><tr><th>Tổ</th><th>Số hộ</th><th>Nhân khẩu</th><th>NCT</th><th>Trẻ em</th><th>Chính sách</th><th>Cần hỗ trợ</th><th>Công trình</th></tr>' +
    rows.map(tr).join('') +
    '<tr class="total">' + tr(tot).replace('<tr>', '').replace('</tr>', '') + '</tr></table>';
}
document.getElementById('btnStats').onclick = () => {
  const p = document.getElementById('statsPanel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
  refreshStats();
};

// ================= ĐẶT MỐC =================
let mocMode = false;
const btnMoc = document.getElementById('btnMoc');
btnMoc.onclick = () => {
  mocMode = !mocMode;
  btnMoc.classList.toggle('active', mocMode);
  btnMoc.textContent = mocMode ? '📌 Đang đặt mốc — nhấp vào bản đồ' : '📌 Đặt mốc';
  map.getContainer().style.cursor = mocMode ? 'crosshair' : '';
};
function mocPopup(m) {
  const ll = m.getLatLng();
  return '<b>' + (m.name || 'Mốc') + '</b><br>' + ll.lat.toFixed(6) + ', ' + ll.lng.toFixed(6) +
    '<br><button onclick="this.parentNode.remove(); saveState();">Xóa mốc</button>';
}
map.on('click', e => {
  if (!mocMode) return;
  const name = prompt('Tên mốc (mặc định: Nhà Văn Hóa Thôn Lệ Sơn Nam):', 'Nhà Văn Hóa Thôn Lệ Sơn Nam');
  if (name === null) return;
  const m = L.circleMarker(e.latlng, {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
    .addTo(mocLayer).bindPopup(mocPopup);
  m.feature = {type: 'Feature', properties: {name: name, marker: 'Mốc'}, geometry: null};
  m.name = name;
  saveState();
  mocMode = false;
  btnMoc.classList.remove('active');
  btnMoc.textContent = '📌 Đặt mốc';
  map.getContainer().style.cursor = '';
});

// ================= TÌM KIẾM =================
document.getElementById('searchBox').addEventListener('keydown', ev => {
  if (ev.key !== 'Enter') return;
  const q = ev.target.value.trim();
  if (!q) return;
  fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(q + ' Hòa Tiến Hòa Vang Đà Nẵng'), {headers: {Accept: 'application/json'}})
    .then(r => r.json())
    .then(res => {
      if (!res.length) { alert('Không tìm thấy.'); return; }
      map.flyTo([parseFloat(res[0].lat), parseFloat(res[0].lon)], 17);
      L.popup().setLatLng([res[0].lat, res[0].lon]).setContent('<b>' + res[0].display_name + '</b>').openOn(map);
    })
    .catch(() => alert('Lỗi kết nối tìm kiếm.'));
});

// ================= HƯỚNG DẪN =================
document.getElementById('btnHelp').onclick = () => alert(__HELP__);

// ================= XUẤT =================
document.getElementById('exportBtn').onclick = () => {
  const features = collectAll();
  if (!features.length) { alert('Chưa có gì để xuất.'); return; }
  const fc = {type: 'FeatureCollection', features: features};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(fc, null, 2)], {type: 'application/geo+json'}));
  a.download = 'le-son-nam-data.geojson';
  a.click();
};

// ================= IMPORT =================
document.getElementById('btnImport').onclick = () => document.getElementById('fileImport').click();
document.getElementById('fileImport').addEventListener('change', ev => {
  const file = ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      const feats = data.features || (data.type === 'Feature' ? [data] : []);
      if (!feats.length) { alert('File không có đối tượng nào.'); return; }
      feats.forEach(f => {
        if (f.properties) {
          if (f.properties.policy === 'yes') f.properties.policy = 'Có';
          if (f.properties.support === 'yes') f.properties.support = 'Có';
        }
        addFeature(f);
      });
      saveState();
      alert('Đã import ' + feats.length + ' đối tượng.');
    } catch (e) { alert('File GeoJSON không hợp lệ: ' + e.message); }
  };
  reader.readAsText(file);
  ev.target.value = '';
});

// ================= XÓA HẾT =================
document.getElementById('btnClear').onclick = () => {
  if (!confirm('Xóa toàn bộ nhà + tổ + mốc? (không thể hoàn tác)')) return;
  drawn.clearLayers();
  totLayer.clearLayers();
  mocLayer.clearLayers();
  saveState();
};

// ================= KHỞI TẠO =================
restoreState();
refreshList();
refreshStats();
applyFilters();
map.on('mousemove', e => {
  document.getElementById('coord').textContent = e.latlng.lat.toFixed(6) + ', ' + e.latlng.lng.toFixed(6);
});
</script>
</body>
</html>
"""

PAGE = (PAGE.replace("__ROADS__", ROADS)
           .replace("__EXTENT__", EXTENT)
           .replace("__HELP__", json.dumps(HELP_TEXT, ensure_ascii=False)))

with open("index.html", "w") as f:
    f.write(PAGE)
print("index.html written:", len(PAGE), "bytes")
