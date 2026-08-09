#!/usr/bin/env python3
"""Generate a self-contained Leaflet app — Quản lý nhà / hộ khẩu / tổ dân cư Thôn Lệ Sơn Nam.

- Nền: OSM / Esri / Google vệ tinh (tham chiếu)
- Vẽ nhà tay (footprint) + vẽ ranh giới tổ/khu dân cư
- Mỗi hộ: chủ hộ, số nhà, nhân khẩu, NCT, trẻ em, ghi chú
- Click tổ → tổng hợp: số hộ, nhân khẩu, NCT, trẻ em
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

HELP_TEXT = (
    "1) Lớp nền: chọn \"Google Vệ tinh\" / \"Google Hybrid\" để thấy rõ mái nhà.\n"
    "2) VẼ NHÀ: bấm 🏘 Vẽ nhà → chọn ▢/đa giác ở cột trái → khoanh mái nhà → điền thông tin hộ → Lưu.\n"
    "3) VẼ TỔ: bấm 🏘 Vẽ tổ → vẽ ranh giới tổ/khu dân cư → gõ tên (Tổ 1, Tổ 2...).\n"
    "   Click vào tổ → hiện bảng tổng hợp: số hộ, nhân khẩu, NCT, trẻ em.\n"
    "4) CLICK NHÀ: hiện chi tiết hộ → ✏️ Sửa / 🗑 Xóa.\n"
    "5) 📊 Thống kê: bảng tổng hợp toàn thôn theo tổ.\n"
    "6) Click nhà bất kỳ để xem/sửa thông tin hộ.\n"
    "7) 📋 Danh sách: xem tổ + nhà, nhấp để nhảy tới.\n"
    "9) PHÍM TẮT: bấm D để bật ngay công cụ vẽ polygon (theo chế độ hiện tại).\n"
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
  /* ô tìm kiếm */
  #searchBox { position:absolute; z-index:1000; top:108px; left:56px; width:300px;
               font:13px system-ui; padding:9px 12px; border:1px solid var(--line); border-radius:12px;
               box-shadow:var(--shadow); outline:none; transition:border .15s; }
  #searchBox:focus { border-color:var(--primary); }
  #idBox { position:absolute; z-index:1000; top:146px; left:56px; width:300px;
           font:13px system-ui; padding:9px 12px; border:1px solid var(--line); border-radius:12px;
           box-shadow:var(--shadow); outline:none; }
  #idBox:focus { border-color:#7c3aed; }
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
  .btn2 { padding:7px 14px; border:none; border-radius:9px; cursor:pointer; font:600 13px system-ui; background:var(--primary); color:#fff; }
  .btn2.gray { background:#f3f4f6; color:var(--text); }
  #fillModal .btn2 { margin-right:6px; }
  ::-webkit-scrollbar { width:9px; height:9px; }
  ::-webkit-scrollbar-thumb { background:#d1d5db; border-radius:8px; }
  ::-webkit-scrollbar-thumb:hover { background:#9ca3af; }
</style>
</head>
<body>
<div id="map"></div>
<div id="tools">
  <button id="btnMode" title="Xoay vòng chế độ vẽ: nhà → tổ → ranh giới thôn">🏘 Vẽ nhà</button>
  <span class="sep"></span>
  <button id="btnList" title="Hiện/ẩn danh sách">📋 Danh sách</button>
  <button id="btnStats" title="Bảng thống kê theo tổ">📊 Thống kê</button>
  <span class="sep"></span>
  <button id="btnMoc" title="Đặt mốc">📌 Đặt mốc</button>
  <button id="btnImport" title="Nạp file GeoJSON">📂 Import</button>
  <button id="btnFill" title="Dán dữ liệu thành viên theo ID nhà (lấy từ Click nhà)">📥 Đổ dữ liệu theo ID</button>
  <button id="btnSaveSrv" title="Lưu toàn bộ dữ liệu (nhà + tổ + ranh giới thôn) về máy">💾 Lưu về máy</button>
  <button id="btnDelTo" class="danger" title="Xóa toàn bộ ranh giới tổ (giữ nhà + mốc)">🗑 Xóa tổ</button>
  <button id="btnClear" class="danger" title="Xóa toàn bộ dữ liệu">🗑 Xóa hết</button>
  <button id="btnHelp">❓ Hướng dẫn</button>
</div>
<div id="fillModal" style="display:none;position:fixed;z-index:3000;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:14px;padding:18px;width:560px;max-width:94%;max-height:86%;overflow-y:auto;box-shadow:0 10px 40px rgba(0,0,0,.3)">
    <h3 style="margin:0 0 6px">📥 Đổ dữ liệu thành viên theo ID nhà</h3>
    <div style="font-size:12.5px;color:#6b7280;margin-bottom:10px">
      <b>Cách dùng:</b> 1) Click nhà trên bản đồ để lấy ID (hoặc gõ ID dưới đây) · 2) Dán danh sách thành viên (kèm dòng ID nếu có) · 3) Bấm <b>Nạp dữ liệu</b>.<br>
      <b>Định dạng nhận dạng:</b> dòng chứa <code>ID GeoJSON: LSN-Hxxx</code> và các dòng <code>Tên | Ngày sinh | Giới tính | Tên chủ hộ | Địa chỉ</code> — <b>cột 4 = tên chủ hộ</b> (app tự tìm thành viên trùng tên để đánh dấu 👑).
    </div>
    <input id="fillId" placeholder="ID nhà (vd: LSN-H067) — nếu trong dữ liệu dán có dòng ID thì để trống" style="width:100%;margin-bottom:8px">
    <textarea id="fillData" rows="10" placeholder="Dán danh sách thành viên ở đây, ví dụ:
Nguyễn Đức Hùng | 27/09/1977 | Nam | Tổ 3, Thôn Lệ Sơn Nam...
Phạm Thị Ngọc Ánh | 11/05/1982 | Nữ | Tổ 3, ...
...
🆔 ID GeoJSON: LSN-H067" style="width:100%;border:1px solid #d1d5db;border-radius:8px;padding:8px;font:12.5px ui-monospace,Menlo,monospace"></textarea>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button class="btn2" onclick="applyFill()">💾 Nạp dữ liệu</button>
      <button class="btn2 gray" onclick="closeFill()">Đóng</button>
    </div>
    <div id="fillResult" style="margin-top:8px;font-size:12.5px"></div>
  </div>
</div>
<input type="file" id="fileImport" accept=".geojson,.json" style="display:none">
<input id="searchBox" placeholder="🔍 Tìm kiếm (vd: nhà văn hóa, ĐH409...) — Enter">
<input id="idBox" placeholder="🆔 Nhập ID nhà (vd: LSN-H023) → Enter" style="top:146px">
<div id="listPanel"><h3>📋 Danh sách tổ & nhà</h3><div id="listBody"></div></div>
<div id="statsPanel"><h3>📊 Thống kê theo tổ</h3><div id="statsBody"></div></div>
<div id="bar"><b>Quản lý nhà & tổ dân cư – Thôn Lệ Sơn Nam + Lệ Sơn Bắc</b> · Hòa Tiến, Hòa Vang, Đà Nẵng ·
  con trỏ: <span class="c" id="coord">–</span> · <span class="c" id="savedMsg"></span></div>
<div class="legend">
  <i style="background:#00a651"></i> Nhà ở<br>
  <i style="background:linear-gradient(90deg,#e67e22,#2980b9,#27ae60,#8e44ad,#c0392b);border:1px solid #555"></i> Ranh giới tổ (mỗi tổ 1 màu)<br>
  <i style="background:transparent;border:2px dashed #b91c1c"></i> Ranh giới thôn<br>
  <i style="background:#ff4d4d;border-radius:50%"></i> Mốc thôn (Kiệt 1 / Kiệt 12)
</div>
<button id="exportBtn" class="leaflet-bar">⬇ Xuất GeoJSON</button>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
<script>
const roads = __ROADS__;

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
googleHybrid.addTo(map);   // lớp nền mặc định: Google Hybrid

// ---- Đường (tắt mặc định — bật lại qua nút lớp góc phải trên) ----
const roadLayer = L.geoJSON(roads, {
  style: f => ({
    color: f.properties.highway === 'primary' ? '#e67e22' :
           f.properties.highway === 'secondary' ? '#f0a020' : '#7fb2d6',
    weight: f.properties.highway === 'service' ? 1.5 : 3, opacity: .9
  }),
  onEachFeature: (f, l) => { if (f.properties.name) l.bindTooltip(f.properties.name, {sticky: true}); }
});

// ---- Mốc thôn ----
const kiet1 = L.circleMarker([15.9610, 108.1827], {radius: 9, color: '#ff4d4d', weight: 2.5, fillColor: '#fff', fillOpacity: 1})
  .addTo(map).bindPopup('<b>Kiệt 1 Đường ĐH409</b><br>Thôn Lệ Sơn Nam<br>(15.96100, 108.18270)');
const kiet12 = L.circleMarker([15.9627, 108.1793], {radius: 9, color: '#ff4d4d', weight: 2.5, fillColor: '#fff', fillOpacity: 1})
  .addTo(map).bindPopup('<b>Kiệt 12 Đường ĐH409</b><br>Thôn Lệ Sơn Bắc<br>(15.96269, 108.17934)');
const thonLayer = L.featureGroup().addTo(map);  // ranh giới thôn (khai báo trước L.control.layers)
L.control.layers(
  {'Bản đồ OSM': osm, 'Vệ tinh (Esri)': esriSat, 'Vệ tinh + tên đường (Esri)': esriHybrid,
   'Google Maps (road)': googleRoad, 'Google Vệ tinh': googleSat, 'Google Hybrid': googleHybrid},
  {'Đường OSM': roadLayer, 'Ranh giới thôn': thonLayer, 'Mốc thôn': L.layerGroup([kiet1, kiet12])}
).addTo(map);

// ================= DỮ LIỆU =================
const STORE_KEY = 'lesonnam_household_v3';
const drawn = L.featureGroup().addTo(map);      // nhà
const totLayer = L.featureGroup().addTo(map);   // tổ
// Bảng màu cho từng tổ (mỗi tổ 1 màu riêng, lặp lại khi quá 12 tổ)
const TO_COLORS = ['#e67e22', '#2980b9', '#27ae60', '#8e44ad', '#c0392b', '#16a085',
                   '#d35400', '#2c3e50', '#7d6608', '#5dade2', '#e84393', '#00b894'];
// Chọn màu CHƯA có tổ nào đang dùng (tránh trùng khi xóa tổ giữa chừng)
function nextToColor() {
  const used = new Set();
  totLayer.eachLayer(t => { const c = props(t).color; if (c) used.add(c); });
  for (const c of TO_COLORS) { if (!used.has(c)) return c; }
  return TO_COLORS[totLayer.getLayers().length % TO_COLORS.length];
}
function toColor(n) { return TO_COLORS[n % TO_COLORS.length]; }
const mocLayer = L.featureGroup().addTo(map);   // mốc
let uid = 1;
let houseSeq = 0;   // bộ đếm ID nhà (LSN-H001...)

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
const thonDrawControl = new L.Control.Draw({
  edit: {featureGroup: thonLayer},
  draw: {polygon: {allowIntersection: false, shapeOptions: {color: '#b91c1c'}}, rectangle: true,
         polyline: false, circle: false, circlemarker: false, marker: false}
});
let drawMode = 'house';
let activeControl = houseDrawControl;   // control đang hiển thị trên bản đồ
map.addControl(houseDrawControl);
const btnMode = document.getElementById('btnMode');
function activateMode(mode) {
  drawMode = mode;
  // chỉ gỡ control đang dùng (tránh onRemove trên control chưa thêm -> crash)
  map.removeControl(activeControl);
  if (mode === 'to') { map.addControl(toDrawControl); activeControl = toDrawControl; }
  else if (mode === 'thon') { map.addControl(thonDrawControl); activeControl = thonDrawControl; }
  else { map.addControl(houseDrawControl); activeControl = houseDrawControl; }
  if (mode === 'to') { btnMode.textContent = '🏘 Vẽ tổ'; }
  else if (mode === 'thon') { btnMode.textContent = '🗺 Vẽ ranh thôn'; }
  else { btnMode.textContent = '🏘 Vẽ nhà'; }
  btnMode.classList.toggle('active', mode !== 'house');
}
// 1 nút xoay vòng: Vẽ nhà → Vẽ tổ → Vẽ ranh thôn → Vẽ nhà ...
btnMode.onclick = () => activateMode(drawMode === 'house' ? 'to' : (drawMode === 'to' ? 'thon' : 'house'));

// ---- Phím D: bật ngay công cụ vẽ polygon theo chế độ hiện tại ----
let drawBusy = false;
map.on(L.Draw.Event.DRAWSTART, () => { drawBusy = true; });
map.on(L.Draw.Event.DRAWSTOP, () => { drawBusy = false; });
document.addEventListener('keydown', ev => {
  if (ev.key.toLowerCase() !== 'd' || ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (ev.target && (ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA' || ev.target.tagName === 'SELECT')) return;
  if (drawBusy) return;   // đang vẽ dở thì không khởi động lại
  const opts = drawMode === 'to' ? toDrawControl.options.draw.polygon :
               drawMode === 'thon' ? thonDrawControl.options.draw.polygon :
               houseDrawControl.options.draw.polygon;
  new L.Draw.Polygon(map, opts).enable();
});

// ================= POPUP: NHÀ =================
function houseInfo(l) {
  const p = props(l);
  return '<div style="min-width:240px">' +
    '<span class="pt">🏠 ' + (esc(p['addr:housenumber']) ? 'Số ' + esc(p['addr:housenumber']) + ' — ' : '') +
      (esc(p.name) || 'Chưa có tên') + '</span>' +
    '<div style="background:#f3e8ff;border:1px solid #d8b4fe;border-radius:8px;padding:4px 8px;margin-bottom:6px;font-weight:700;color:#6b21a8">🆔 ID GeoJSON: ' + esc(p.fid || '—') + '</div>' +
    '<table class="info-table">' +
    '<tr><td>Chủ hộ</td><td><b>' + (esc(p.name) || '—') + '</b></td></tr>' +
    '<tr><td>Số nhà</td><td>' + (esc(p['addr:housenumber']) || '—') + '</td></tr>' +
    '<tr><td>Nhân khẩu</td><td>' + (esc(p.members) || '—') + '</td></tr>' +
    '<tr><td>Người cao tuổi</td><td>' + (esc(p.elderly) || '—') + '</td></tr>' +
    '<tr><td>Trẻ em</td><td>' + (esc(p.children) || '—') + '</td></tr>' +
    '<tr><td>Ghi chú</td><td>' + (esc(p.note) || '—') + '</td></tr>' +
    '</table>' +
    (Array.isArray(p.members_list) && p.members_list.length ?
      '<div style="margin-top:6px"><b>👥 Thành viên (' + p.members_list.length + ')</b></div>' +
      p.members_list.map(m => '<div style="font-size:12.5px;padding:2px 0;border-bottom:1px dashed #eee">' +
        (m.head ? '<b>👑</b> ' : '') + esc(m.name) + (m.head ? ' <span style="color:#b45309;font-size:11px">(Chủ hộ)</span>' : '') +
        (m.dob ? ' · <span style="color:#6b7280">' + esc(m.dob) + '</span>' : '') +
        (m.gender ? ' · ' + esc(m.gender) : '') + '</div>').join('')
      : '') +
    '<button class="primary" onclick="editHouse(this)">✏️ Sửa</button> ' +
    '<button onclick="deleteHouse(this)">🗑 Xóa</button></div>';
}
function houseForm(l) {
  const p = props(l);
  return '<div style="min-width:250px"><b>✏️ Thông tin hộ</b><br>' +
    'Chủ hộ: <input id="fName" value="' + esc(p.name) + '" style="width:200px;margin:3px 0"><br>' +
    'Số nhà: <input id="fNum" value="' + esc(p['addr:housenumber']) + '" style="width:200px;margin:3px 0"><br>' +
    'Nhân khẩu: <input id="fMem" type="number" min="0" value="' + esc(p.members) + '" style="width:200px;margin:3px 0"><br>' +
    'Người cao tuổi: <input id="fEld" type="number" min="0" value="' + esc(p.elderly) + '" style="width:200px;margin:3px 0"><br>' +
    'Trẻ em: <input id="fKid" type="number" min="0" value="' + esc(p.children) + '" style="width:200px;margin:3px 0"><br>' +
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
  const s = {to: 0, mem: 0, eld: 0, kid: 0};
  drawn.eachLayer(h => {
    if (!pointInRing(h.getBounds().getCenter(), ring)) return;
    const p = props(h);
    s.to++; s.mem += num(p.members); s.eld += num(p.elderly); s.kid += num(p.children);
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
    '</table>' +
    '<button class="primary" onclick="renameTo(this)">✏️ Đổi tên</button> ' +
    '<button onclick="deleteTo(this)">🗑 Xóa tổ</button></div>';
}

// ================= POPUP: RANH GIỚI THÔN =================
function polyAreaM2(ring) {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    a += (ring[j].lng * ring[i].lat - ring[i].lng * ring[j].lat);
  }
  a = Math.abs(a / 2);
  const mLat = 111320;
  const mLng = 111320 * Math.cos(ring[0].lat * Math.PI / 180);
  return a * mLat * mLng;
}
function thonInfo(l) {
  const p = props(l);
  const ring = l.getLatLngs()[0];
  const c = l.getBounds().getCenter();
  const ha = (polyAreaM2(ring) / 10000).toFixed(2);
  return '<div style="min-width:230px">' +
    '<span class="pt">🗺 ' + esc(p.name || 'Ranh giới thôn') + '</span>' +
    '<table class="info-table">' +
    '<tr><td>Diện tích</td><td><b>' + ha + ' ha</b></td></tr>' +
    '<tr><td>Tâm</td><td>' + c.lat.toFixed(6) + ', ' + c.lng.toFixed(6) + '</td></tr>' +
    '</table>' +
    '<button class="primary" onclick="renameThon(this)">✏️ Đổi tên</button> ' +
    '<button onclick="deleteThon(this)">🗑 Xóa</button></div>';
}
function findThonLayer(el) {
  const pop = el.closest('.leaflet-popup');
  let l = null;
  thonLayer.eachLayer(t => { if (t.getPopup() && t.getPopup().getElement() === pop) l = t; });
  return l;
}
window.renameThon = function(btn) {
  const l = findThonLayer(btn);
  if (!l) return;
  const name = prompt('Tên ranh giới thôn:', props(l).name || 'Ranh giới thôn');
  if (name === null) return;
  props(l).name = name;
  l.setPopupContent(thonInfo(l));
  saveState();
};
window.deleteThon = function(btn) {
  const l = findThonLayer(btn);
  if (l && confirm('Xóa ranh giới thôn?')) { thonLayer.removeLayer(l); saveState(); }
};

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
  if (drawMode === 'thon') {
    // chỉ giữ 1 ranh giới thôn: vẽ mới thay thế ranh giới cũ
    const old = thonLayer.getLayers()[0];
    if (old) thonLayer.removeLayer(old);
    layer.feature = {type: 'Feature', properties: {name: 'Ranh giới thôn', type: 'thon', note: ''}};
    layer.uid = uid++;
    layer.setStyle({color: '#b91c1c', weight: 3.5, fillColor: '#fca5a5', fillOpacity: .12, dashArray: '8 4'});
    layer.bindPopup(function(l) { return thonInfo(l); });
    thonLayer.addLayer(layer);
    layer.openPopup();
  } else if (drawMode === 'to') {
    const name = prompt('Tên tổ (vd: Tổ 1, Tổ 2, Khu dân cư...):', 'Tổ ' + (totLayer.getLayers().length + 1));
    const color = nextToColor();
    layer.feature = {type: 'Feature', properties: {name: (name || 'Tổ'), type: 'to', note: '', color: color}};
    layer.uid = uid++;
    layer.setStyle({color: color, weight: 2.5, fillColor: color, fillOpacity: .3});
    layer.bindPopup(function(l) { return toInfo(l); });
    totLayer.addLayer(layer);    // thêm sau => vẽ đè lên tổ cũ (ranh giới trùng nhìn rõ)
    layer.openPopup();           // mở ngay bảng thống kê tổ
  } else {
    layer.feature = {type: 'Feature', properties: {name: '', 'addr:housenumber': '',
      members: '', elderly: '', children: '', note: '', fid: 'LSN-H' + String(++houseSeq).padStart(3, '0')}};
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

// ================= LƯU / KHÔI PHỤC =================
// ---- LƯU / KHÔI PHỤC (bảo đảm với mọi loại hình vẽ: polygon, rectangle) ----
// Lấy vòng ngoài của polygon (xử lý cả _latlngs lồng lẫn phẳng)
function ringCoords(l) {
  const ll = l.getLatLngs();
  const ring = (Array.isArray(ll[0]) && ll[0].length && ll[0][0].lat !== undefined) ? ll[0] : ll;
  return ring.map(p => [p.lng, p.lat]);
}
function addFeature(f) {
  if (f.geometry.type === 'Point') {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
      .addTo(mocLayer).bindPopup(mocPopup);
    m.feature = {type: 'Feature', properties: f.properties, geometry: null};
    m.name = (f.properties && f.properties.name) || 'Mốc';
    return;
  }
  // Tạo polygon tường minh từ tọa độ (không phụ thuộc L.geoJSON)
  const ring = f.geometry.coordinates[0].map(c => [c[1], c[0]]);
  const l = L.polygon(ring);
  l.feature = f;
  l.uid = uid++;
  if (f.properties && f.properties.type === 'to') {
    // Giữ màu đã lưu nếu chưa ai dùng; trùng thì đổi màu mới (tự sửa dữ liệu cũ)
    let color = f.properties.color;
    let dup = false;
    totLayer.eachLayer(t => { if (t !== l && props(t).color === color) dup = true; });
    if (!color || dup) color = nextToColor();
    f.properties.color = color;
    l.setStyle({color: color, weight: 2.5, fillColor: color, fillOpacity: .3});
    l.bindPopup(function(l) { return toInfo(l); });
    totLayer.addLayer(l);
  } else if (f.properties && f.properties.type === 'thon') {
    l.setStyle({color: '#b91c1c', weight: 3.5, fillColor: '#fca5a5', fillOpacity: .12, dashArray: '8 4'});
    l.bindPopup(function(l) { return thonInfo(l); });
    thonLayer.addLayer(l);
  } else {
    if (!f.properties.fid) f.properties.fid = 'LSN-H' + String(++houseSeq).padStart(3, '0');
    l.bindPopup(function(l) { return houseInfo(l); });
    drawn.addLayer(l);
  }
}
function collectAll() {
  const features = [];
  thonLayer.eachLayer(t => {
    const p = props(t);
    features.push({type: 'Feature',
      properties: {type: 'thon', name: p.name || 'Ranh giới thôn', note: p.note || 'Ranh giới thôn (vẽ tay)'},
      geometry: {type: 'Polygon', coordinates: [ringCoords(t)]}});
  });
  totLayer.eachLayer(t => {
    const p = props(t);
    features.push({type: 'Feature',
      properties: {type: 'to', name: p.name || 'Tổ', note: p.note || 'Ranh giới tổ dân cư (vẽ tay)', color: p.color},
      geometry: {type: 'Polygon', coordinates: [ringCoords(t)]}});
  });
  drawn.eachLayer(l => {
    const p = props(l);
    features.push({type: 'Feature',
      id: p.fid || undefined,
      properties: {
        fid: p.fid || undefined,
        members_list: p.members_list || undefined,
        name: p.name || undefined,
        'addr:housenumber': p['addr:housenumber'] || undefined,
        members: p.members || undefined,
        elderly: p.elderly || undefined,
        children: p.children || undefined,
        note: p.note || undefined,
        source: 'vẽ tay từ ảnh vệ tinh – thôn Lệ Sơn Nam'
      },
      geometry: {type: 'Polygon', coordinates: [ringCoords(l)]}});
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
  let ok = false;
  try { localStorage.setItem(STORE_KEY, JSON.stringify(collectAll())); ok = true; } catch (e) { console.error('Lưu thất bại:', e); }
  const sm = document.getElementById('savedMsg');
  if (sm) sm.textContent = ok ? ('💾 Đã lưu ' + new Date().toLocaleTimeString('vi-VN')) : '⚠️ Lưu thất bại';
  refreshList();
  refreshStats();
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
  thonLayer.eachLayer(t => {
    const p = props(t);
    rows.push({uid: t.uid, kind: 'thon', label: '🗺 ' + (p.name || 'Ranh giới thôn'), detail: ''});
  });
  totLayer.eachLayer(t => {
    const p = props(t);
    rows.push({uid: t.uid, kind: 'to', label: '🏘 ' + (p.name || 'Tổ'), detail: ''});
  });
  drawn.eachLayer(l => {
    const p = props(l);
    const numS = p['addr:housenumber'] ? 'Số ' + p['addr:housenumber'] + ' — ' : '';
    rows.push({uid: l.uid, kind: 'house', label: '🆔' + (p.fid || '?') + ' · ' + numS + (p.name || 'Nhà'),
      detail: p.members ? ' · ' + p.members + ' người' : ''});
  });
  body.innerHTML = rows.map(r =>
    '<div class="row ' + (r.kind === 'to' ? 'to' : '') + '" onclick="gotoItem(' + r.uid + ')">' +
    '<b>' + r.label + '</b><span class="cnt">' + r.detail + '</span></div>').join('') ||
    '<div class="row" style="color:#888">Chưa có dữ liệu. Vẽ nhà / vẽ tổ trên bản đồ.</div>';
  document.getElementById('btnList').textContent = '📋 Danh sách (' + rows.length + ')';
}
window.gotoItem = function(uid) {
  thonLayer.eachLayer(t => { if (t.uid === uid) { map.flyTo(t.getBounds().getCenter(), 16); t.openPopup(); } });
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
  const tot = {name: 'Tổng toàn thôn', to: 0, mem: 0, eld: 0, kid: 0};
  totLayer.eachLayer(t => {
    const s = totStats(t);
    rows.push({name: props(t).name || 'Tổ', to: s.to, mem: s.mem, eld: s.eld, kid: s.kid});
    tot.to += s.to; tot.mem += s.mem; tot.eld += s.eld; tot.kid += s.kid;
  });
  // nhà ngoài tổ
  const out = {to: 0, mem: 0, eld: 0, kid: 0};
  drawn.eachLayer(h => {
    const c = h.getBounds().getCenter();
    let inTo = false;
    totLayer.eachLayer(t => { if (pointInRing(c, t.getLatLngs()[0])) inTo = true; });
    if (inTo) return;
    const p = props(h);
    out.to++; out.mem += num(p.members); out.eld += num(p.elderly); out.kid += num(p.children);
  });
  if (out.to > 0) rows.push({name: 'Chưa phân tổ', to: out.to, mem: out.mem, eld: out.eld, kid: out.kid});
  tot.to += out.to; tot.mem += out.mem; tot.eld += out.eld; tot.kid += out.kid;

  const tr = r => '<tr><td>' + r.name + '</td><td>' + r.to + '</td><td>' + r.mem + '</td><td>' + r.eld + '</td><td>' + r.kid + '</td></tr>';
  document.getElementById('statsBody').innerHTML =
    '<table><tr><th>Tổ</th><th>Số hộ</th><th>Nhân khẩu</th><th>NCT</th><th>Trẻ em</th></tr>' +
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

// ================= ĐỔ DỮ LIỆU THEO ID =================
document.getElementById('btnFill').onclick = () => {
  document.getElementById('fillModal').style.display = 'flex';
  document.getElementById('fillId').value = document.getElementById('idBox').value.trim() || '';
  document.getElementById('fillData').value = '';
  document.getElementById('fillResult').innerHTML = '';
};
window.closeFill = function() { document.getElementById('fillModal').style.display = 'none'; };

// Tính tuổi từ dd/mm/yyyy
function ageFromDob(dob) {
  const m = String(dob || '').match(/(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/);
  if (!m) return null;
  const d = new Date(+m[3], +m[2] - 1, +m[1]);
  if (isNaN(d)) return null;
  return Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000));
}
window.applyFill = function() {
  const res = document.getElementById('fillResult');
  const raw = document.getElementById('fillData').value;
  let id = document.getElementById('fillId').value.trim().toUpperCase();
  if (!id) {
    const mId = raw.match(/LSN-H\d{3,}/i);
    if (mId) id = mId[0].toUpperCase();
  }
  let layer = null;
  drawn.eachLayer(l => { const p = props(l); if (p.fid && p.fid.toUpperCase() === id) layer = l; });
  if (!id) { res.innerHTML = '<b style="color:#dc2626">⚠️ Thiếu ID nhà.</b> Gõ ID ở ô trên hoặc kèm dòng "ID GeoJSON: LSN-Hxxx" trong dữ liệu dán.'; return; }
  if (!layer) { res.innerHTML = '<b style="color:#dc2626">⚠️ Không tìm thấy nhà có ID ' + id + '.</b> Bấm vào nhà trên bản đồ để xem ID thật.'; return; }

  const members = [];
  raw.split(/\\r?\\n/).forEach(line => {
    line = line.trim();
    if (!line || /ID\\s*GeoJSON/i.test(line) || line.startsWith('🆔')) return;
    const parts = line.split('|').map(s => s.trim());
    if (parts.length < 2) return;
    // Cột 4 (index 3) = TÊN CHỦ HỘ (giống nhau ở mọi dòng); cột 5+ = địa chỉ
    members.push({name: parts[0], dob: parts[1], gender: parts[2] || '',
      headName: parts[3] || '', address: parts.slice(4).join(' · '), head: false});
  });
  if (!members.length) { res.innerHTML = '<b style="color:#dc2626">⚠️ Không tìm thấy dòng thành viên nào.</b> Mỗi thành viên 1 dòng: Tên | Ngày sinh | Giới tính | Tên chủ hộ | Địa chỉ.'; return; }

  const p = props(layer);
  // Chủ hộ = cột 4 (headName) — tìm thành viên trùng tên để đánh dấu 👑
  const headName = members[0].headName || members[0].name;
  let head = null;
  members.forEach(m => { if (m.name.toUpperCase() === headName.toUpperCase()) { m.head = true; head = m; } });
  if (!head) { members[0].head = true; head = members[0]; }
  p.members_list = members;
  p.members = members.length;
  p.name = head.name;
  p.elderly = members.filter(m => { const a = ageFromDob(m.dob); return a !== null && a >= 60; }).length;
  p.children = members.filter(m => { const a = ageFromDob(m.dob); return a !== null && a < 16; }).length;
  p.note = members[0].address || p.note || '';
  saveState();
  map.flyTo(layer.getBounds().getCenter(), 19);
  layer.setPopupContent(houseInfo(layer));
  layer.openPopup();
  res.innerHTML = '<b style="color:#16a34a">✅ Đã nạp vào ' + id + ':</b> ' + members.length + ' thành viên · ' +
    p.elderly + ' NCT · ' + p.children + ' trẻ em · Chủ hộ: ' + p.name +
    '<br><span style="color:#888">Xem chi tiết trong popup nhà; bấm 💾 Lưu về máy để ghi ra file.</span>';
};

// ================= TÌM THEO ID GEOJSON =================
document.getElementById('idBox').addEventListener('keydown', ev => {
  if (ev.key !== 'Enter') return;
  const q = ev.target.value.trim().toUpperCase();
  if (!q) return;
  let found = null;
  drawn.eachLayer(l => { const p = props(l); if (p.fid && p.fid.toUpperCase() === q) found = l; });
  if (found) {
    map.flyTo(found.getBounds().getCenter(), 19);
    found.setPopupContent(houseInfo(found));
    found.openPopup();
    document.getElementById('savedMsg').textContent = '🆔 ' + q;
  } else {
    alert('Không tìm thấy nhà có ID ' + q + '. Bấm vào nhà trên bản đồ để xem ID.');
  }
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
      feats.forEach(addFeature);
      saveState();
      alert('Đã import ' + feats.length + ' đối tượng.');
    } catch (e) { alert('File GeoJSON không hợp lệ: ' + e.message); }
  };
  reader.readAsText(file);
  ev.target.value = '';
});

// ================= XÓA TỔ / XÓA HẾT =================
document.getElementById('btnSaveSrv').onclick = async () => {
  const feats = collectAll();
  if (!feats.length) { alert('Chưa có dữ liệu.'); return; }
  const payload = {type: 'FeatureCollection', features: feats,
    savedAt: new Date().toISOString(), meta: 'Lệ Sơn Nam - nhà + tổ + ranh giới thôn'};
  try {
    const res = await fetch('/api/save', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const j = await res.json();
    if (j.ok) {
      const nTo = feats.filter(f => f.properties && f.properties.type === 'to').length;
      const nThon = feats.filter(f => f.properties && f.properties.type === 'thon').length;
      const nNha = feats.filter(f => f.geometry.type === 'Polygon' && !(f.properties && (f.properties.type === 'to' || f.properties.type === 'thon'))).length;
      alert('✅ Đã lưu về máy: ' + nNha + ' nhà · ' + nTo + ' tổ · ' + nThon + ' ranh giới thôn');
    } else { alert('Lỗi server: ' + (j.error || '')); }
  } catch (e) { alert('Không kết nối được máy chủ (chạy server.py trước).'); }
};
document.getElementById('btnDelTo').onclick = () => {
  if (!totLayer.getLayers().length) { alert('Chưa có ranh giới tổ nào.'); return; }
  if (!confirm('Xóa toàn bộ ranh giới tổ đã vẽ? (giữ nguyên nhà + mốc)')) return;
  totLayer.clearLayers();
  saveState();
};
document.getElementById('btnClear').onclick = () => {
  if (!confirm('Xóa toàn bộ nhà + tổ + mốc? (không thể hoàn tác)')) return;
  drawn.clearLayers();
  totLayer.clearLayers();
  thonLayer.clearLayers();
  mocLayer.clearLayers();
  saveState();
};

// ================= KHỞI TẠO =================
restoreState();
refreshList();
refreshStats();
map.on('mousemove', e => {
  document.getElementById('coord').textContent = e.latlng.lat.toFixed(6) + ', ' + e.latlng.lng.toFixed(6);
});
</script>
</body>
</html>
"""

PAGE = (PAGE.replace("__ROADS__", ROADS)
           .replace("__HELP__", json.dumps(HELP_TEXT, ensure_ascii=False)))

with open("index.html", "w") as f:
    f.write(PAGE)
print("index.html written:", len(PAGE), "bytes")
