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
<title>Lệ Sơn Nam Smart Village – Bản đồ số</title>
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
  #map { position:absolute; inset:0; width:100%; height:100%; transition:width .24s ease; }
  body.detail-open #map { width:calc(100% - 380px); }
  body.detail-open #brandBar { right:540px; }
  body.detail-open #tools { max-width:calc(100% - 452px); flex-wrap:nowrap; overflow-x:auto; overflow-y:hidden; scrollbar-width:none; }
  body.detail-open #tools::-webkit-scrollbar { display:none; }
  body.detail-open #tools button, body.detail-open #tools .sep { flex:none; }
  #brandBar { position:absolute; z-index:1000; top:12px; left:56px; right:160px; min-height:46px;
              display:flex; align-items:center; gap:10px; padding:7px 12px; border:1px solid rgba(229,231,235,.95);
              border-radius:14px; background:rgba(255,255,255,.94); box-shadow:var(--shadow); backdrop-filter:blur(10px); }
  #brandBar .mark { width:32px; height:32px; display:grid; place-items:center; flex:none; border-radius:10px;
                    background:linear-gradient(135deg,#166534,#16a34a); color:#fff; font:800 10px/1 system-ui; letter-spacing:.5px; }
  #brandBar .title { min-width:178px; }
  #brandBar .title strong { display:block; font-size:13px; letter-spacing:.1px; }
  #brandBar .title span { display:block; color:var(--muted); font-size:10.5px; margin-top:2px; }
  #quickStats { display:flex; align-items:center; gap:6px; margin-left:auto; }
  #quickStats .kpi { min-width:66px; padding:4px 8px; border-left:1px solid var(--line); }
  #quickStats .kpi b { display:block; color:#166534; font-size:15px; line-height:1.1; }
  #quickStats .kpi span { color:var(--muted); font-size:10px; white-space:nowrap; }
  #seedStatus { color:#166534; background:#ecfdf5; border:1px solid #bbf7d0; border-radius:999px; padding:4px 8px; font-size:10.5px; white-space:nowrap; }
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
  #tools { position:absolute; z-index:1000; top:70px; left:56px; display:flex; align-items:center;
           gap:2px; flex-wrap:wrap; max-width:calc(100% - 72px);
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
  #searchBox { position:absolute; z-index:1000; top:126px; left:56px; width:320px;
               font:13px system-ui; padding:9px 12px; border:1px solid var(--line); border-radius:12px;
               box-shadow:var(--shadow); outline:none; transition:border .15s; }
  #searchBox:focus { border-color:var(--primary); }
  #searchResults { position:absolute; z-index:1100; top:164px; left:56px; width:320px; max-height:280px; overflow:auto;
                  display:none; background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); }
  #searchResults .result { padding:9px 12px; border-bottom:1px solid #f3f4f6; cursor:pointer; font-size:12.5px; }
  #searchResults .result:last-child { border-bottom:0; }
  #searchResults .result:hover { background:#f0fdf4; }
  #searchResults .result b { color:#166534; }
  #searchResults .result small { display:block; color:var(--muted); margin-top:2px; }
  /* bảng danh sách + thống kê */
  #listPanel, #statsPanel { position:absolute; z-index:1000; top:198px; left:56px; width:360px; max-height:62%;
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
  /* panel dữ liệu theo vùng được chọn */
  #detailPanel { position:fixed; z-index:1200; top:0; right:0; bottom:0; width:380px;
                 display:none; flex-direction:column; background:#fff; border-left:1px solid var(--line);
                 box-shadow:-10px 0 30px rgba(17,24,39,.16); overflow:hidden; }
  #detailPanel.open { display:flex; }
  #detailHeader { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding:20px 18px 16px;
                  background:linear-gradient(135deg,#f0fdf4,#ffffff 62%); border-bottom:1px solid var(--line); }
  #detailHeader .eyebrow { display:block; color:#15803d; font-size:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
  #detailHeader h2 { margin:3px 0 2px; font-size:18px; line-height:1.2; }
  #detailHeader .subtitle { display:block; color:var(--muted); font-size:11px; }
  #detailClose { width:30px; height:30px; flex:none; border:1px solid var(--line); border-radius:9px; background:#fff;
                 color:var(--muted); font-size:20px; line-height:1; cursor:pointer; }
  #detailClose:hover { color:var(--text); background:#f3f4f6; }
  #detailBody { overflow:auto; padding:14px 16px 16px; }
  .detailBadge { display:inline-flex; align-items:center; min-height:22px; padding:3px 8px; border-radius:999px;
                 background:#dcfce7; color:#166534; font-size:10px; font-weight:800; }
  .detailId { display:block; margin-top:7px; color:#7c3aed; font:11px ui-monospace,Menlo,monospace; }
  .detailStats { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin:12px 0 16px; }
  .detailStat { padding:9px 8px; border:1px solid #dcfce7; border-radius:10px; background:#f0fdf4; text-align:center; }
  .detailStat b { display:block; color:#166534; font-size:18px; line-height:1.15; }
  .detailStat span { display:block; margin-top:3px; color:var(--muted); font-size:10px; }
  .detailSection { margin-top:14px; }
  .detailSection h3 { margin:0 0 7px; font-size:12px; color:var(--text); }
  .detailRows { display:grid; grid-template-columns:96px 1fr; gap:6px 10px; margin:0; font-size:12px; }
  .detailRows dt { color:var(--muted); }
  .detailRows dd { margin:0; font-weight:600; text-align:right; overflow-wrap:anywhere; }
  .detailMember { padding:8px 0; border-top:1px dashed #e5e7eb; font-size:12px; }
  .detailMember:first-of-type { border-top:0; }
  .detailMember b { display:block; }
  .detailMember small { color:var(--muted); }
  .detailActions { display:flex; flex-wrap:wrap; gap:7px; margin-top:17px; }
  .detailActions button { border:1px solid #d1d5db; border-radius:9px; background:#fff; color:var(--text); padding:7px 10px;
                          font:600 12px system-ui; cursor:pointer; }
  .detailActions button:hover { background:#f3f4f6; }
  .detailActions button.primary { border-color:var(--primary); background:var(--primary); color:#fff; }
  .detailActions button.primary:hover { background:#15803d; }
  .detailForm label { display:block; margin:0 0 10px; color:var(--muted); font-size:11px; font-weight:700; }
  .detailForm input, .detailForm textarea { display:block; width:100%; margin-top:5px; border:1px solid #d1d5db;
                                             border-radius:9px; padding:9px 10px; color:var(--text); background:#fff; font:13px system-ui; outline:none; }
  .detailForm textarea { min-height:128px; resize:vertical; font:12px/1.45 ui-monospace,Menlo,monospace; }
  .detailForm input:focus, .detailForm textarea:focus { border-color:var(--primary); box-shadow:0 0 0 3px rgba(22,163,74,.12); }
  .detailForm .helper { margin:-3px 0 13px; color:var(--muted); font-size:10.5px; line-height:1.45; }
  .detailConfirm { padding:11px; border:1px solid #fecaca; border-radius:10px; background:#fef2f2; color:#991b1b; font-size:12px; }
  /* chú giải */
  .legend { position:absolute; z-index:1000; bottom:44px; right:12px; background:rgba(255,255,255,.94);
            padding:10px 14px; font:12.5px system-ui; border-radius:var(--radius); box-shadow:var(--shadow);
            border:1px solid var(--line); line-height:1.9; }
  .legend i { display:inline-block; width:13px; height:13px; margin-right:7px; vertical-align:-2px;
              border-radius:3px; }
  .btn2 { padding:7px 14px; border:none; border-radius:9px; cursor:pointer; font:600 13px system-ui; background:var(--primary); color:#fff; }
  .btn2.gray { background:#f3f4f6; color:var(--text); }
  ::-webkit-scrollbar { width:9px; height:9px; }
  ::-webkit-scrollbar-thumb { background:#d1d5db; border-radius:8px; }
  ::-webkit-scrollbar-thumb:hover { background:#9ca3af; }
  @media (max-width:980px) {
    #quickStats .kpi:nth-child(n+3) { display:none; }
    #brandBar { right:148px; }
    #brandBar .title { min-width:150px; }
  }
  @media (max-width:760px) {
    #brandBar { top:8px; left:10px; right:10px; padding:6px 8px; }
    #brandBar .title { min-width:0; }
    #brandBar .title strong { font-size:12px; }
    #brandBar .title span { display:none; }
    #quickStats { display:none; }
    #seedStatus { margin-left:auto; font-size:9.5px; }
    #tools { top:64px; left:10px; right:10px; max-width:none; padding:4px; max-height:none; overflow-x:auto; overflow-y:hidden; flex-wrap:nowrap; scrollbar-width:none; }
    #tools::-webkit-scrollbar { display:none; }
    #tools button, #tools .sep { flex:none; }
    #tools button { padding:6px 8px; font-size:11.5px; }
    #searchBox { top:148px; left:10px; width:calc(100% - 20px); }
    #searchResults { top:186px; left:10px; width:calc(100% - 20px); }
    #listPanel, #statsPanel { top:208px; left:10px; width:calc(100% - 20px); max-height:55%; }
    #statsPanel { left:10px; }
    body.detail-open #map { width:100%; }
    body.detail-open #brandBar { right:10px; }
    body.detail-open #tools { max-width:none; }
    #detailPanel { top:auto; left:0; right:0; bottom:65px; width:100%; height:min(58vh,500px); max-height:none;
                   border-left:0; border-top:1px solid var(--line); border-radius:18px 18px 0 0; }
    #exportBtn { top:auto; bottom:76px; right:10px; padding:8px 10px; font-size:11.5px; }
    .legend { bottom:76px; left:10px; right:auto; max-width:240px; font-size:10.5px; padding:7px 9px; }
  }
</style>
</head>
<body>
<div id="map"></div>
<div id="brandBar" aria-label="Tổng quan dữ liệu thôn">
  <div class="mark">LSN</div>
  <div class="title"><strong>Lệ Sơn Nam Smart Village</strong><span>Quản lý nhân hộ khẩu trên bản đồ số</span></div>
  <div id="quickStats">
    <div class="kpi"><b id="quickHouses">–</b><span>hộ dân</span></div>
    <div class="kpi"><b id="quickPeople">–</b><span>khẩu đã nhập</span></div>
    <div class="kpi"><b id="quickFilled">–</b><span>hồ sơ đủ</span></div>
    <div class="kpi"><b id="quickTos">–</b><span>tổ dân cư</span></div>
  </div>
  <span id="seedStatus">Đang tải dữ liệu…</span>
</div>
<div id="tools">
  <button id="btnMode" title="Xoay vòng chế độ vẽ: nhà → tổ → ranh giới thôn">🏘 Vẽ nhà</button>
  <span class="sep"></span>
  <button id="btnList" title="Hiện/ẩn danh sách">📋 Danh sách</button>
  <button id="btnStats" title="Bảng thống kê theo tổ">📊 Thống kê</button>
  <span class="sep"></span>
  <button id="btnMoc" title="Đặt mốc">📌 Đặt mốc</button>
  <button id="btnImport" title="Nạp file GeoJSON">📂 Import</button>
  <button id="btnSaveSrv" title="Lưu toàn bộ dữ liệu (nhà + tổ + ranh giới thôn) về máy">💾 Lưu về máy</button>
  <button id="btnDelTo" class="danger" title="Xóa toàn bộ ranh giới tổ (giữ nhà + mốc)">🗑 Xóa tổ</button>
  <button id="btnClear" class="danger" title="Xóa toàn bộ dữ liệu">🗑 Xóa hết</button>
  <button id="btnHelp">❓ Hướng dẫn</button>
</div>
<input type="file" id="fileImport" accept=".geojson,.json" style="display:none">
<input id="searchBox" placeholder="🔍 Tìm chủ hộ, thành viên hoặc địa danh…" autocomplete="off">
<div id="searchResults" role="listbox"></div>
<div id="listPanel"><h3>📋 Danh sách tổ & nhà</h3><div id="listBody"></div></div>
<div id="statsPanel"><h3>📊 Thống kê theo tổ</h3><div id="statsBody"></div></div>
<aside id="detailPanel" aria-live="polite" aria-label="Dữ liệu vùng được chọn">
  <div id="detailHeader">
    <div><span id="detailEyebrow" class="eyebrow">Dữ liệu vùng</span><h2 id="detailTitle">Chưa chọn vùng</h2><span id="detailSubtitle" class="subtitle">Nhấp vào nhà, tổ hoặc ranh giới thôn</span></div>
    <button id="detailClose" title="Đóng bảng dữ liệu" aria-label="Đóng bảng dữ liệu">×</button>
  </div>
  <div id="detailBody"></div>
</aside>
<div id="bar"><b>Quản lý nhà & tổ dân cư – Thôn Lệ Sơn Nam</b> · Hòa Tiến, Hòa Vang, Đà Nẵng ·
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
  .addTo(map);
const kiet12 = L.circleMarker([15.9627, 108.1793], {radius: 9, color: '#ff4d4d', weight: 2.5, fillColor: '#fff', fillOpacity: 1})
  .addTo(map);
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
const SERVER_BACKUP_URL = 'backups/latest-drawn.json';
const SEED_DATA_URL = 'backups/le-son-nam-2026-08-09-69nha-6fill.json';
function featureId(f) {
  const p = f && f.properties || {};
  if (p.type === 'to' || p.type === 'thon' || (f && f.geometry && f.geometry.type === 'Point')) return '';
  return String(p.fid || (f && f.id) || '').trim().toUpperCase();
}
function featureScore(f) {
  const p = f && f.properties || {};
  return (Array.isArray(p.members_list) ? p.members_list.length * 10 : 0) +
    (p.name ? 3 : 0) + (p.members != null ? 1 : 0) + (p.note ? 1 : 0);
}
function geometryKey(f) { return featureId(f) + '|' + JSON.stringify(f && f.geometry || null); }
function mergeFeatureSources(primary, fallback) {
  const result = (primary || []).map(f => f);
  const positions = new Map();
  result.forEach((f, i) => { if (f && f.geometry) positions.set(geometryKey(f), i); });
  (fallback || []).forEach(f => {
    if (!f || !f.geometry) return;
    const key = geometryKey(f);
    const index = positions.get(key);
    if (index === undefined) {
      positions.set(key, result.length);
      result.push(f);
      return;
    }
    const current = result[index];
    const currentProps = current.properties || {};
    const fallbackProps = f.properties || {};
    if (featureScore(f) > featureScore(current)) {
      result[index] = Object.assign({}, f, {properties: Object.assign({}, fallbackProps, currentProps)});
    } else if (!Array.isArray(currentProps.members_list) && Array.isArray(fallbackProps.members_list)) {
      current.properties = Object.assign({}, currentProps, {
        members_list: fallbackProps.members_list,
        members: fallbackProps.members,
        elderly: fallbackProps.elderly,
        children: fallbackProps.children
      });
    }
  });
  return result;
}
async function fetchFeatureFile(url) {
  try {
    const res = await fetch(url, {cache: 'no-store'});
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (Array.isArray(data.features) ? data.features : []);
  } catch (e) { return []; }
}
function dedupeFeatures(features) {
  const result = [], positions = new Map(), signatures = new Map();
  let nextId = 0;
  (features || []).forEach(f => {
    const match = featureId(f).match(/^LSN-H(\d+)$/);
    if (match) nextId = Math.max(nextId, Number(match[1]));
  });
  (features || []).forEach(f => {
    if (!f || !f.geometry) return;
    let id = featureId(f);
    const signature = JSON.stringify(f.geometry);
    const geometryIndex = signatures.get(signature);
    if (geometryIndex !== undefined) {
      result[geometryIndex] = mergeFeatureRecords(result[geometryIndex], f);
      return;
    }
    if (!id) {
      signatures.set(signature, result.length);
      result.push(f);
      return;
    }
    if (!positions.has(id)) {
      positions.set(id, result.length);
      signatures.set(signature, result.length);
      result.push(f);
      return;
    }
    do { nextId++; id = 'LSN-H' + String(nextId).padStart(3, '0'); } while (positions.has(id));
    f = Object.assign({}, f, {id: id, properties: Object.assign({}, f.properties || {}, {fid: id})});
    positions.set(id, result.length);
    signatures.set(signature, result.length);
    result.push(f);
  });
  return result;
}
function noteHouseId(f) {
  const id = featureId(f);
  const match = id.match(/^LSN-H(\d+)$/);
  if (match) houseSeq = Math.max(houseSeq, Number(match[1]));
}
function mergeFeatureRecords(current, incoming) {
  const currentProps = current.properties || {};
  const incomingProps = incoming.properties || {};
  const richerIncoming = featureScore(incoming) > featureScore(current);
  const properties = richerIncoming ?
    Object.assign({}, currentProps, incomingProps) :
    Object.assign({}, incomingProps, currentProps);
  if (!Array.isArray(currentProps.members_list) && Array.isArray(incomingProps.members_list)) {
    properties.members_list = incomingProps.members_list;
    properties.members = incomingProps.members;
    properties.elderly = incomingProps.elderly;
    properties.children = incomingProps.children;
  }
  return Object.assign({}, current, {properties: properties});
}
function setSeedStatus(text, ok) {
  const el = document.getElementById('seedStatus');
  if (!el) return;
  el.textContent = text;
  el.style.color = ok ? '#166534' : '#92400e';
  el.style.background = ok ? '#ecfdf5' : '#fffbeb';
  el.style.borderColor = ok ? '#bbf7d0' : '#fde68a';
}

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

// ================= KHU VỰC & THỐNG KÊ =================
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
// ================= RANH GIỚI THÔN =================
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
// ================= PANEL DỮ LIỆU THEO VÙNG =================
let detailLayer = null;
let detailKind = '';
const detailPanel = document.getElementById('detailPanel');
const detailBody = document.getElementById('detailBody');
function detailStat(value, label) {
  return '<div class="detailStat"><b>' + esc(value) + '</b><span>' + esc(label) + '</span></div>';
}
function regionKind(l) {
  const type = props(l).type;
  return type === 'to' ? 'to' : (type === 'thon' ? 'thon' : 'house');
}
function mocDetailMarkup(m) {
  const p = props(m);
  const ll = m.getLatLng();
  return '<span class="detailBadge" style="background:#ffedd5;color:#9a3412">MỐC THAM CHIẾU</span>' +
    '<section class="detailSection"><h3>Thông tin mốc</h3><dl class="detailRows">' +
    '<dt>Tọa độ</dt><dd>' + ll.lat.toFixed(6) + ', ' + ll.lng.toFixed(6) + '</dd>' +
    '<dt>Ghi chú</dt><dd>' + esc(p.note || '—') + '</dd></dl></section>' +
    '<div class="detailActions"><button class="primary" data-detail-action="edit-moc">✏️ Sửa mốc</button><button data-detail-action="delete-moc">🗑 Xóa mốc</button></div>';
}
function thonStats(l) {
  const ring = l.getLatLngs()[0];
  const result = {houses: 0, people: 0, filled: 0, tos: totLayer.getLayers().length};
  drawn.eachLayer(h => {
    if (!pointInRing(h.getBounds().getCenter(), ring)) return;
    const p = props(h);
    result.houses++;
    result.people += num(p.members);
    if (Array.isArray(p.members_list) && p.members_list.length) result.filled++;
  });
  return result;
}
function houseDetailMarkup(l) {
  const p = props(l);
  const members = Array.isArray(p.members_list) ? p.members_list : [];
  const memberMarkup = members.length ? members.map(m =>
    '<div class="detailMember"><b>' + (m.head ? '👑 ' : '') + esc(m.name || 'Chưa rõ tên') + '</b>' +
    (m.head ? '<small>Chủ hộ</small><br>' : '') +
    '<small>' + [m.dob, m.gender].filter(Boolean).map(esc).join(' · ') + '</small></div>').join('') :
    '<div style="color:#6b7280;font-size:12px">Chưa có danh sách thành viên chi tiết.</div>';
  return '<span class="detailBadge">HỘ DÂN</span>' +
    '<span class="detailId">' + esc(p.fid || 'Chưa có ID') + '</span>' +
    '<div class="detailStats">' + detailStat(p.members || '—', 'khẩu') + detailStat(p.elderly || '—', 'NCT') + detailStat(p.children || '—', 'trẻ em') + '</div>' +
    '<section class="detailSection"><h3>Thông tin hộ</h3><dl class="detailRows">' +
    '<dt>Chủ hộ</dt><dd>' + esc(p.name || 'Chưa có dữ liệu') + '</dd>' +
    '<dt>Số nhà</dt><dd>' + esc(p['addr:housenumber'] || '—') + '</dd>' +
    '<dt>Ghi chú</dt><dd>' + esc(p.note || '—') + '</dd></dl></section>' +
    '<section class="detailSection"><h3>Thành viên (' + members.length + ')</h3>' + memberMarkup + '</section>' +
    '<div class="detailActions"><button class="primary" data-detail-action="edit-house">✏️ Sửa thông tin</button><button data-detail-action="delete-house">🗑 Xóa nhà</button></div>';
}
function toDetailMarkup(l) {
  const p = props(l);
  const s = totStats(l);
  return '<span class="detailBadge" style="background:#fef3c7;color:#92400e">TỔ DÂN CƯ</span>' +
    '<div class="detailStats">' + detailStat(s.to, 'hộ dân') + detailStat(s.mem, 'khẩu') + detailStat(s.kid, 'trẻ em') + '</div>' +
    '<section class="detailSection"><h3>Tổng hợp trong vùng</h3><dl class="detailRows">' +
    '<dt>Người cao tuổi</dt><dd>' + s.eld + '</dd><dt>Ghi chú</dt><dd>' + esc(p.note || '—') + '</dd></dl></section>' +
    '<div class="detailActions"><button class="primary" data-detail-action="edit-to">✏️ Sửa tổ</button><button data-detail-action="delete-to">🗑 Xóa tổ</button></div>';
}
function thonDetailMarkup(l) {
  const p = props(l);
  const s = thonStats(l);
  const ring = l.getLatLngs()[0];
  const center = l.getBounds().getCenter();
  return '<span class="detailBadge" style="background:#fee2e2;color:#991b1b">RANH GIỚI THÔN</span>' +
    '<div class="detailStats">' + detailStat(s.houses, 'hộ trong vùng') + detailStat(s.people, 'khẩu đã nhập') + detailStat(s.filled, 'hồ sơ đủ') + '</div>' +
    '<section class="detailSection"><h3>Thông tin vùng</h3><dl class="detailRows">' +
    '<dt>Diện tích</dt><dd>' + polyAreaM2(ring).toFixed(0) + ' m²</dd><dt>Tâm vùng</dt><dd>' + center.lat.toFixed(6) + ', ' + center.lng.toFixed(6) + '</dd></dl></section>' +
    '<div class="detailActions"><button class="primary" data-detail-action="edit-thon">✏️ Sửa ranh giới</button><button data-detail-action="delete-thon">🗑 Xóa ranh giới</button></div>';
}
function memberEditText(l) {
  const p = props(l);
  const members = Array.isArray(p.members_list) ? p.members_list : [];
  const headName = (members.find(m => m.head) || {}).name || p.name || '';
  const address = members[0] && members[0].address ? members[0].address : (p.note || '');
  return members.map(m => [m.name || '', m.dob || '', m.gender || '', headName, address].join(' | ')).join('\\n');
}
function parseMemberText(raw) {
  const members = [];
  String(raw || '').split(/\\r?\\n/).forEach(line => {
    line = line.trim();
    if (!line || /ID\s*GeoJSON/i.test(line) || line.startsWith('🆔')) return;
    const parts = line.split('|').map(s => s.trim());
    if (parts.length < 2) return;
    members.push({name: parts[0], dob: parts[1], gender: parts[2] || '', headName: parts[3] || '',
      address: parts.slice(4).join(' · '), head: false});
  });
  return members;
}
function applyMemberText(l, raw) {
  const members = parseMemberText(raw);
  const p = props(l);
  if (!members.length) {
    delete p.members_list;
    p.members = '';
    p.elderly = '';
    p.children = '';
    return;
  }
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
}
function showDetailEditor(kind, l) {
  if (!l) return;
  detailLayer = l;
  detailKind = kind || regionKind(l);
  document.getElementById('listPanel').style.display = 'none';
  document.getElementById('statsPanel').style.display = 'none';
  const p = props(l);
  document.getElementById('detailEyebrow').textContent = kind === 'house' ? 'Chỉnh sửa hộ dân' : (kind === 'to' ? 'Chỉnh sửa tổ dân cư' : (kind === 'thon' ? 'Chỉnh sửa địa bàn' : 'Chỉnh sửa mốc'));
  document.getElementById('detailTitle').textContent = p.name || (kind === 'house' ? 'Hộ dân mới' : kind === 'to' ? 'Tổ mới' : kind === 'thon' ? 'Ranh giới thôn' : 'Mốc mới');
  document.getElementById('detailSubtitle').textContent = kind === 'house' ? (p.fid || 'Nhà chưa có ID') : 'Thay đổi sẽ được lưu ngay vào dữ liệu';
  if (kind === 'moc') {
    detailBody.innerHTML = '<form class="detailForm" onsubmit="return false">' +
      '<label>Tên mốc<input data-field="name" value="' + esc(p.name || '') + '"></label>' +
      '<label>Ghi chú<textarea data-field="note" style="min-height:90px">' + esc(p.note || '') + '</textarea></label>' +
      '<div class="detailActions"><button class="primary" data-detail-action="save-moc">💾 Lưu thay đổi</button><button data-detail-action="cancel-edit">Hủy</button><button data-detail-action="delete-moc">🗑 Xóa mốc</button></div></form>';
  } else if (kind === 'house') {
    detailBody.innerHTML = '<form class="detailForm" onsubmit="return false">' +
      '<label>Chủ hộ<input data-field="name" value="' + esc(p.name || '') + '"></label>' +
      '<label>Số nhà<input data-field="housenumber" value="' + esc(p['addr:housenumber'] || '') + '"></label>' +
      '<label>Ghi chú<input data-field="note" value="' + esc(p.note || '') + '"></label>' +
      '<label>Danh sách thành viên<textarea data-field="members" placeholder="Tên | Ngày sinh | Giới tính | Tên chủ hộ | Địa chỉ">' + esc(memberEditText(l)) + '</textarea></label>' +
      '<p class="helper">Mỗi người một dòng. Cột 4 là tên chủ hộ; cột 5 là địa chỉ. Để trống nếu muốn xóa danh sách thành viên chi tiết.</p>' +
      '<div class="detailActions"><button class="primary" data-detail-action="save-house">💾 Lưu thay đổi</button><button data-detail-action="cancel-edit">Hủy</button><button data-detail-action="delete-house">🗑 Xóa nhà</button></div></form>';
  } else {
    detailBody.innerHTML = '<form class="detailForm" onsubmit="return false">' +
      '<label>' + (kind === 'to' ? 'Tên tổ' : 'Tên ranh giới') + '<input data-field="name" value="' + esc(p.name || '') + '"></label>' +
      '<label>Ghi chú<textarea data-field="note" style="min-height:90px">' + esc(p.note || '') + '</textarea></label>' +
      '<div class="detailActions"><button class="primary" data-detail-action="save-' + kind + '">💾 Lưu thay đổi</button><button data-detail-action="cancel-edit">Hủy</button><button data-detail-action="delete-' + kind + '">🗑 Xóa</button></div></form>';
  }
  detailPanel.classList.add('open');
  document.body.classList.add('detail-open');
  setTimeout(() => map.invalidateSize({pan: false}), 260);
}
function askDelete(kind, l) {
  const label = kind === 'house' ? 'nhà này' : kind === 'to' ? 'tổ này' : kind === 'thon' ? 'ranh giới thôn này' : 'mốc này';
  detailBody.insertAdjacentHTML('beforeend', '<div class="detailConfirm"><b>Xóa ' + label + '?</b><br><span>Thao tác này sẽ cập nhật dữ liệu ngay.</span><div class="detailActions"><button class="primary" data-detail-action="confirm-delete-' + kind + '">Xác nhận xóa</button><button data-detail-action="cancel-delete">Hủy</button></div></div>');
  detailBody.querySelector('.detailConfirm').scrollIntoView({block: 'nearest'});
}
function showMocDetail(m) {
  if (!m) return;
  detailLayer = m;
  detailKind = 'moc';
  document.getElementById('listPanel').style.display = 'none';
  document.getElementById('statsPanel').style.display = 'none';
  const p = props(m);
  const ll = m.getLatLng();
  document.getElementById('detailEyebrow').textContent = 'MỐC THAM CHIẾU';
  document.getElementById('detailTitle').textContent = p.name || m.name || 'Mốc tham chiếu';
  document.getElementById('detailSubtitle').textContent = ll.lat.toFixed(6) + ', ' + ll.lng.toFixed(6);
  detailBody.innerHTML = mocDetailMarkup(m);
  detailPanel.classList.add('open');
  document.body.classList.add('detail-open');
  setTimeout(() => map.invalidateSize({pan: false}), 260);
}
function showDetail(kind, l) {
  if (!l) return;
  if (kind === 'moc') { showMocDetail(l); return; }
  detailLayer = l;
  detailKind = kind || regionKind(l);
  document.getElementById('listPanel').style.display = 'none';
  document.getElementById('statsPanel').style.display = 'none';
  const p = props(l);
  const titles = {house: ['Nhà & hộ dân', p.name || 'Chưa có chủ hộ'], to: ['Tổ dân cư', p.name || 'Tổ'], thon: ['Địa bàn', p.name || 'Ranh giới thôn']};
  const title = titles[detailKind] || titles.house;
  document.getElementById('detailEyebrow').textContent = title[0];
  document.getElementById('detailTitle').textContent = title[1];
  document.getElementById('detailSubtitle').textContent = detailKind === 'house' ? (p.fid || 'Nhà chưa có ID') : 'Nhấp vùng khác để chuyển dữ liệu';
  detailBody.innerHTML = detailKind === 'house' ? houseDetailMarkup(l) : (detailKind === 'to' ? toDetailMarkup(l) : thonDetailMarkup(l));
  detailPanel.classList.add('open');
  document.body.classList.add('detail-open');
  setTimeout(() => map.invalidateSize({pan: false}), 260);
  if (l.bringToFront) l.bringToFront();
}
function closeDetail() {
  detailPanel.classList.remove('open');
  document.body.classList.remove('detail-open');
  detailLayer = null;
  detailKind = '';
  setTimeout(() => map.invalidateSize({pan: false}), 260);
}
function bindRegionClick(l) {
  if (!l || l._detailBound) return;
  l._detailBound = true;
  l.on('click', e => {
    if (e.originalEvent) L.DomEvent.stopPropagation(e.originalEvent);
    showDetail(regionKind(l), l);
  });
}
function bindMocClick(m) {
  if (!m || m._detailBound) return;
  m._detailBound = true;
  m.on('click', e => {
    if (e.originalEvent) L.DomEvent.stopPropagation(e.originalEvent);
    showMocDetail(m);
  });
}
document.getElementById('detailClose').onclick = closeDetail;
detailBody.addEventListener('click', ev => {
  const button = ev.target.closest('[data-detail-action]');
  const l = detailLayer;
  if (!button || !l) return;
  const action = button.dataset.detailAction;
  if (action === 'edit-moc') {
    showDetailEditor('moc', l);
  } else if (action === 'save-moc') {
    const p = props(l);
    p.name = detailBody.querySelector('[data-field="name"]').value.trim() || 'Mốc tham chiếu';
    p.note = detailBody.querySelector('[data-field="note"]').value.trim();
    l.name = p.name;
    saveState();
    showMocDetail(l);
  } else if (action === 'edit-house') {
    showDetailEditor('house', l);
  } else if (action === 'save-house') {
    const p = props(l);
    p.name = detailBody.querySelector('[data-field="name"]').value.trim();
    p['addr:housenumber'] = detailBody.querySelector('[data-field="housenumber"]').value.trim();
    p.note = detailBody.querySelector('[data-field="note"]').value.trim();
    applyMemberText(l, detailBody.querySelector('[data-field="members"]').value);
    saveState();
    showDetail('house', l);
  } else if (action === 'edit-to') {
    showDetailEditor('to', l);
  } else if (action === 'edit-thon') {
    showDetailEditor('thon', l);
  } else if (action === 'save-to') {
    const p = props(l);
    p.name = detailBody.querySelector('[data-field="name"]').value.trim() || 'Tổ';
    p.note = detailBody.querySelector('[data-field="note"]').value.trim();
    saveState();
    showDetail('to', l);
  } else if (action === 'save-thon') {
    const p = props(l);
    p.name = detailBody.querySelector('[data-field="name"]').value.trim() || 'Ranh giới thôn';
    p.note = detailBody.querySelector('[data-field="note"]').value.trim();
    saveState();
    showDetail('thon', l);
  } else if (action === 'cancel-edit') {
    if (detailKind === 'moc') showMocDetail(l); else showDetail(detailKind, l);
  } else if (action === 'delete-house' || action === 'delete-to' || action === 'delete-thon' || action === 'delete-moc') {
    askDelete(action.replace('delete-', ''), l);
  } else if (action === 'confirm-delete-house') {
    drawn.removeLayer(l);
    closeDetail();
    saveState();
  } else if (action === 'confirm-delete-to') {
    totLayer.removeLayer(l);
    closeDetail();
    saveState();
  } else if (action === 'confirm-delete-thon') {
    thonLayer.removeLayer(l);
    closeDetail();
    saveState();
  } else if (action === 'confirm-delete-moc') {
    mocLayer.removeLayer(l);
    closeDetail();
    saveState();
  } else if (action === 'cancel-delete') {
    if (detailKind === 'moc') showMocDetail(l); else showDetail(detailKind, l);
  }
});
document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape' && detailPanel.classList.contains('open')) closeDetail();
});
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
    thonLayer.addLayer(layer);
    bindRegionClick(layer);
    showDetailEditor('thon', layer);
  } else if (drawMode === 'to') {
    const color = nextToColor();
    layer.feature = {type: 'Feature', properties: {name: 'Tổ ' + (totLayer.getLayers().length + 1), type: 'to', note: '', color: color}};
    layer.uid = uid++;
    layer.setStyle({color: color, weight: 2.5, fillColor: color, fillOpacity: .3});
    totLayer.addLayer(layer);    // thêm sau => vẽ đè lên tổ cũ (ranh giới trùng nhìn rõ)
    bindRegionClick(layer);
    showDetailEditor('to', layer);
  } else {
    layer.feature = {type: 'Feature', properties: {name: '', 'addr:housenumber': '',
      members: '', elderly: '', children: '', note: '', fid: 'LSN-H' + String(++houseSeq).padStart(3, '0')}};
    layer.uid = uid++;
    drawn.addLayer(layer);
    bindRegionClick(layer);
    showDetailEditor('house', layer);
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
  if (!f || !f.geometry) return;
  if (f.geometry.type === 'Point') {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
      .addTo(mocLayer);
    m.feature = {type: 'Feature', properties: f.properties, geometry: null};
    m.name = (f.properties && f.properties.name) || 'Mốc';
    m.uid = uid++;
    bindMocClick(m);
    return;
  }
  // Tạo polygon tường minh từ tọa độ (không phụ thuộc L.geoJSON)
  const ring = f.geometry.coordinates[0].map(c => [c[1], c[0]]);
  const l = L.polygon(ring);
  l.feature = f;
  l.uid = uid++;
  bindRegionClick(l);
  noteHouseId(f);
  if (f.properties && f.properties.type === 'to') {
    // Giữ màu đã lưu nếu chưa ai dùng; trùng thì đổi màu mới (tự sửa dữ liệu cũ)
    let color = f.properties.color;
    let dup = false;
    totLayer.eachLayer(t => { if (t !== l && props(t).color === color) dup = true; });
    if (!color || dup) color = nextToColor();
    f.properties.color = color;
    l.setStyle({color: color, weight: 2.5, fillColor: color, fillOpacity: .3});
    totLayer.addLayer(l);
  } else if (f.properties && f.properties.type === 'thon') {
    l.setStyle({color: '#b91c1c', weight: 3.5, fillColor: '#fca5a5', fillOpacity: .12, dashArray: '8 4'});
    thonLayer.addLayer(l);
  } else {
    if (!f.properties.fid) f.properties.fid = 'LSN-H' + String(++houseSeq).padStart(3, '0');
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
    const p = props(m);
    features.push({type: 'Feature',
      properties: {name: m.name || p.name || 'Mốc', marker: p.marker || 'Mốc tham chiếu', note: p.note || 'Mốc tham chiếu'},
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
async function restoreState() {
  let features = [];
  let source = 'trống';
  const storageKeys = [STORE_KEY, 'lesonnam_household_v2', 'lesonnam_household'];
  for (const key of storageKeys) {
    try {
      const stored = JSON.parse(localStorage.getItem(key));
      const candidate = Array.isArray(stored) ? stored : (stored && Array.isArray(stored.features) ? stored.features : []);
      if (candidate.length) { features = candidate; source = 'workspace'; break; }
    } catch (e) { /* thử bản lưu kế tiếp */ }
  }
  const serverFeatures = await fetchFeatureFile(SERVER_BACKUP_URL);
  const seedFeatures = await fetchFeatureFile(SEED_DATA_URL);
  if (features.length) {
    if (serverFeatures.length) features = mergeFeatureSources(features, serverFeatures);
    if (seedFeatures.length) features = mergeFeatureSources(features, seedFeatures);
    source = serverFeatures.length ? 'workspace + backup' : source;
  } else if (serverFeatures.length) {
    features = serverFeatures;
    source = 'server backup';
  } else if (seedFeatures.length) {
    features = seedFeatures;
    source = 'demo backup';
  }
  const normalizedFeatures = dedupeFeatures(features);
  normalizedFeatures.forEach(addFeature);
  if (normalizedFeatures.length) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(collectAll())); } catch (e) { /* vẫn hiển thị được dữ liệu đã khôi phục */ }
  }
  const status = source === 'server backup' ? 'Đã khôi phục bản lưu máy chủ' :
    source === 'workspace + backup' ? 'Đã hợp nhất bản lưu' :
    source === 'demo backup' ? 'Dữ liệu mẫu 2026-08-09' :
    (features.length ? 'Dữ liệu đã lưu' : 'Chưa có dữ liệu');
  setSeedStatus(status, !!features.length);
}

// ================= DANH SÁCH =================
function refreshList() {
  const body = document.getElementById('listBody');
  const rows = [];
  thonLayer.eachLayer(t => {
    const p = props(t);
    rows.push({uid: t.uid, kind: 'thon', label: '🗺 ' + (p.name || 'Ranh giới thôn'), detail: ''});
  });
  mocLayer.eachLayer(m => {
    const p = props(m);
    rows.push({uid: m.uid, kind: 'moc', label: '📍 ' + (p.name || m.name || 'Mốc tham chiếu'), detail: ''});
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
  thonLayer.eachLayer(t => { if (t.uid === uid) { map.flyTo(t.getBounds().getCenter(), 16); showDetail('thon', t); } });
  totLayer.eachLayer(t => { if (t.uid === uid) { map.flyTo(t.getBounds().getCenter(), 16); showDetail('to', t); } });
  drawn.eachLayer(l => { if (l.uid === uid) { map.flyTo(l.getBounds().getCenter(), 19); showDetail('house', l); } });
  mocLayer.eachLayer(m => { if (m.uid === uid) { map.flyTo(m.getLatLng(), 19); showMocDetail(m); } });
};
document.getElementById('btnList').onclick = () => {
  const p = document.getElementById('listPanel');
  p.style.display = getComputedStyle(p).display === 'none' ? 'block' : 'none';
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
  const complete = drawn.getLayers().filter(l => Array.isArray(props(l).members_list) && props(l).members_list.length).length;
  document.getElementById('quickHouses').textContent = drawn.getLayers().length;
  document.getElementById('quickPeople').textContent = tot.mem;
  document.getElementById('quickFilled').textContent = complete;
  document.getElementById('quickTos').textContent = totLayer.getLayers().length;

  const tr = r => '<tr><td>' + r.name + '</td><td>' + r.to + '</td><td>' + r.mem + '</td><td>' + r.eld + '</td><td>' + r.kid + '</td></tr>';
  document.getElementById('statsBody').innerHTML =
    '<table><tr><th>Tổ</th><th>Số hộ</th><th>Nhân khẩu</th><th>NCT</th><th>Trẻ em</th></tr>' +
    rows.map(tr).join('') +
    '<tr class="total">' + tr(tot).replace('<tr>', '').replace('</tr>', '') + '</tr></table>';
}
document.getElementById('btnStats').onclick = () => {
  const p = document.getElementById('statsPanel');
  p.style.display = getComputedStyle(p).display === 'none' ? 'block' : 'none';
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
map.on('click', e => {
  if (!mocMode) { closeDetail(); return; }
  closeDetail();
  const m = L.circleMarker(e.latlng, {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
    .addTo(mocLayer);
  m.feature = {type: 'Feature', properties: {name: 'Mốc mới', marker: 'Mốc tham chiếu', note: ''}, geometry: null};
  m.name = 'Mốc mới';
  m.uid = uid++;
  bindMocClick(m);
  saveState();
  mocMode = false;
  btnMoc.classList.remove('active');
  btnMoc.textContent = '📌 Đặt mốc';
  map.getContainer().style.cursor = '';
  showDetailEditor('moc', m);
});

// Tính tuổi từ dd/mm/yyyy
function ageFromDob(dob) {
  const m = String(dob || '').match(/(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/);
  if (!m) return null;
  const d = new Date(+m[3], +m[2] - 1, +m[1]);
  if (isNaN(d)) return null;
  return Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000));
}
// ================= TÌM KIẾM =================
function normalizeText(s) {
  return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}
function searchableHouseText(l) {
  const p = props(l);
  return [p.fid, p.name, p.note].concat((p.members_list || []).map(m => m.name)).join(' ');
}
function localHouseMatches(query) {
  const q = normalizeText(query.trim());
  if (!q) return [];
  const matches = [];
  drawn.eachLayer(l => { if (normalizeText(searchableHouseText(l)).includes(q)) matches.push(l); });
  return matches.slice(0, 8);
}
function focusHouse(l) {
  if (!l) return;
  searchBox.value = '';
  searchResults.innerHTML = '';
  searchResults.style.display = 'none';
  map.flyTo(l.getBounds().getCenter(), 19, {duration: .7});
  showDetail('house', l);
  document.getElementById('savedMsg').textContent = '📍 ' + (props(l).fid || 'Nhà');
}
const searchBox = document.getElementById('searchBox');
const searchResults = document.getElementById('searchResults');
searchBox.addEventListener('input', ev => {
  const hits = localHouseMatches(ev.target.value);
  if (!ev.target.value.trim()) { searchResults.style.display = 'none'; return; }
  searchResults.innerHTML = hits.length ? hits.map(l => {
    const p = props(l);
    return '<div class="result" data-uid="' + l.uid + '" role="option"><b>🏠 ' + esc(p.fid || 'Nhà') + '</b> · ' + esc(p.name || 'Chưa có chủ hộ') +
      '<small>' + (p.members_list && p.members_list.length ? p.members_list.length + ' thành viên có hồ sơ' : (p.members || 0) + ' nhân khẩu') + '</small></div>';
  }).join('') : '<div class="result" style="color:#6b7280">Không có hồ sơ nội bộ · nhấn Enter để tìm địa danh</div>';
  searchResults.querySelectorAll('.result[data-uid]').forEach(row => {
    row.onclick = () => { const l = [...drawn.getLayers()].find(x => String(x.uid) === row.dataset.uid); focusHouse(l); };
  });
  searchResults.style.display = 'block';
});
searchBox.addEventListener('keydown', ev => {
  if (ev.key === 'Escape') { searchResults.style.display = 'none'; return; }
  if (ev.key !== 'Enter') return;
  const local = localHouseMatches(ev.target.value);
  if (local.length) { focusHouse(local[0]); return; }
  const q = ev.target.value.trim();
  if (!q) return;
  fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(q + ' Hòa Tiến Hòa Vang Đà Nẵng'), {headers: {Accept: 'application/json'}})
    .then(r => r.json())
    .then(res => {
      if (!res.length) { alert('Không tìm thấy địa danh.'); return; }
      map.flyTo([parseFloat(res[0].lat), parseFloat(res[0].lon)], 17);
      document.getElementById('savedMsg').textContent = '📍 ' + esc(res[0].display_name);
      searchResults.style.display = 'none';
    })
    .catch(() => alert('Không thể tìm địa danh lúc này.'));
});
document.addEventListener('click', ev => {
  if (ev.target !== searchBox && !searchResults.contains(ev.target)) searchResults.style.display = 'none';
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
      dedupeFeatures(feats).forEach(f => {
        const id = featureId(f);
        if (id) drawn.eachLayer(l => { if (featureId(l.feature) === id) drawn.removeLayer(l); });
        addFeature(f);
      });
      saveState();
      alert('Đã import ' + dedupeFeatures(feats).length + ' đối tượng, tự hợp nhất các ID trùng.');
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
restoreState().then(() => {
  refreshList();
  refreshStats();
}).catch(() => {
  setSeedStatus('Chưa có dữ liệu', false);
  refreshList();
  refreshStats();
});
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
