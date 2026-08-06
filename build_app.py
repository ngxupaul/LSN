#!/usr/bin/env python3
"""Generate a self-contained Leaflet app — Quản lý nhà / hộ khẩu Thôn Lệ Sơn Nam.

- Nền: OSM / Esri vệ tinh / Google vệ tinh (tham chiếu)
- Vẽ nhà tay trên ảnh vệ tinh; nhấp vào nhà để xem/sửa thông tin hộ
  (tên chủ hộ, số nhà, số thành viên, ghi chú)
- Lưu localStorage (không mất khi reload), xuất GeoJSON, import GeoJSON
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
    "1) Lớp nền: chọn \"Google Vệ tinh\" / \"Google Hybrid\" ở góc phải trên để thấy rõ từng mái nhà.\n"
    "2) VẼ NHÀ: chọn công cụ ▢ (hình chữ nhật) hoặc đa giác ở cột trái, khoanh theo mái nhà trên ảnh.\n"
    "   Sau khi vẽ xong, hộp thoại hiện ra → điền thông tin hộ (chủ hộ, số nhà, thành viên, ghi chú) → Lưu.\n"
    "3) XEM/SỬA: nhấp vào nhà đã vẽ → hiện thông tin hộ; bấm ✏️ Sửa để đổi, 🗑 Xóa để bỏ.\n"
    "4) 📋 Danh sách nhà: bấm nút để xem bảng tổng hợp, nhấp hàng để nhảy tới nhà đó.\n"
    "5) Đặt mốc: 📌 Đặt mốc → nhấp bản đồ → gõ tên (vd: Nhà Văn Hóa Thôn Lệ Sơn Nam).\n"
    "6) Xong bấm ⬇ Xuất GeoJSON để tải dữ liệu (JOSM / iD / app riêng).\n\n"
    "Mọi thay đổi tự lưu vào trình duyệt — reload không mất dữ liệu."
)

PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quản lý nhà – Thôn Lệ Sơn Nam (Hòa Tiến, Đà Nẵng)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"/>
<style>
  html, body, #map { height: 100%; margin: 0; }
  #bar { position: absolute; z-index: 1000; bottom: 0; left: 0; right: 0;
         background: rgba(0,0,0,.78); color: #fff; font: 12px/1.6 monospace; padding: 4px 10px; }
  #bar b { color: #ffd75e; }
  #bar .c { color: #9be89b; }
  #exportBtn { position: absolute; z-index: 1000; top: 10px; right: 10px; }
  .legend { position:absolute; z-index:1000; bottom:34px; right:10px; background:rgba(255,255,255,.92);
            padding:8px 10px; font:12px sans-serif; border-radius:4px; box-shadow:0 1px 5px rgba(0,0,0,.4);}
  .legend i { display:inline-block; width:12px; height:12px; margin-right:6px; vertical-align:-1px; }
  #tools { position:absolute; z-index:1000; top:10px; left:52px; display:flex; gap:6px; flex-wrap:wrap; }
  #tools button { background:#fff; border:1px solid #ccc; border-radius:4px; padding:6px 10px;
                  font:13px sans-serif; cursor:pointer; box-shadow:0 1px 5px rgba(0,0,0,.4); }
  #tools button.active { background:#ffd75e; border-color:#e67e22; }
  #searchBox { position:absolute; z-index:1000; top:44px; left:52px; width:280px;
               font:13px sans-serif; padding:6px 8px; border:1px solid #ccc; border-radius:4px;
               box-shadow:0 1px 5px rgba(0,0,0,.4); }
  #listPanel { position:absolute; z-index:1000; top:80px; left:52px; width:320px; max-height:60%;
               background:#fff; border:1px solid #ccc; border-radius:6px; box-shadow:0 2px 10px rgba(0,0,0,.35);
               display:none; overflow-y:auto; font:13px sans-serif; }
  #listPanel h3 { margin:0; padding:8px 10px; background:#f5f5f5; border-bottom:1px solid #ddd; font-size:14px; }
  #listPanel .row { padding:7px 10px; border-bottom:1px solid #eee; cursor:pointer; }
  #listPanel .row:hover { background:#fff7d6; }
  #listPanel .row b { color:#0b6e2f; }
  #listPanel .cnt { color:#888; font-size:12px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="tools">
  <button id="btnList" title="Hiện/ẩn danh sách nhà đã vẽ">📋 Danh sách</button>
  <button id="btnMoc" title="Bấm để bật/tắt: nhấp vào bản đồ đặt mốc">📌 Đặt mốc</button>
  <button id="btnImport" title="Nạp file GeoJSON đã xuất trước đó">📂 Import</button>
  <button id="btnClear" title="Xóa toàn bộ nhà + mốc đã vẽ">🗑 Xóa hết</button>
  <button id="btnHelp">❓ Hướng dẫn</button>
</div>
<input type="file" id="fileImport" accept=".geojson,.json" style="display:none">
<input id="searchBox" placeholder="🔍 Tìm kiếm (vd: nhà văn hóa, ĐH409...) — Enter">
<div id="listPanel"><h3>🏠 Danh sách nhà</h3><div id="listBody"></div></div>
<div id="bar"><b>Quản lý nhà – Thôn Lệ Sơn Nam + Lệ Sơn Bắc</b> · Hòa Tiến, Hòa Vang, Đà Nẵng ·
  con trỏ: <span class="c" id="coord">–</span></div>
<div class="legend">
  <i style="background:#00a651"></i> Nhà đã vẽ (màu xanh)<br>
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
  {'Đường OSM': roadLayer,
   'Phạm vi ước tính': extentLayer, 'Mốc thôn': L.layerGroup([kiet1, kiet12])}
).addTo(map);

// ================= VẼ NHÀ + THÔNG TIN HỘ =================
const STORE_KEY = 'lesonnam_houses_v2';
const drawn = L.featureGroup().addTo(map);
const drawControl = new L.Control.Draw({
  edit: {featureGroup: drawn},
  draw: {polygon: {allowIntersection: false, shapeOptions: {color: '#00a651'}}, rectangle: true,
         polyline: false, circle: false, circlemarker: false, marker: false}
});
map.addControl(drawControl);
let uid = 1;

function props(l) { return (l.feature && l.feature.properties) || {}; }
function esc(s) { return String(s == null ? '' : s).replace(/</g, '&lt;').replace(/"/g, '&quot;'); }

// Hiển thị chi tiết hộ khi nhấp vào nhà
function houseInfo(l) {
  const p = props(l);
  const c = l.getBounds().getCenter();
  return '<div style="min-width:230px">' +
    '<b>🏠 ' + (esc(p['addr:housenumber']) ? 'Số ' + esc(p['addr:housenumber']) + ' — ' : '') +
      (esc(p.name) || 'Nhà chưa có tên') + '</b><br>' +
    '<table style="border-collapse:collapse;font-size:13px">' +
    '<tr><td style="padding:2px 8px 2px 0;color:#666">Chủ hộ</td><td><b>' + (esc(p.name) || '—') + '</b></td></tr>' +
    '<tr><td style="padding:2px 8px 2px 0;color:#666">Số nhà</td><td>' + (esc(p['addr:housenumber']) || '—') + '</td></tr>' +
    '<tr><td style="padding:2px 8px 2px 0;color:#666">Số thành viên</td><td>' + (esc(p.members) || '—') + '</td></tr>' +
    '<tr><td style="padding:2px 8px 2px 0;color:#666">Ghi chú</td><td>' + (esc(p.note) || '—') + '</td></tr>' +
    '<tr><td style="padding:2px 8px 2px 0;color:#666">Tọa độ</td><td>' + c.lat.toFixed(6) + ', ' + c.lng.toFixed(6) + '</td></tr>' +
    '</table>' +
    '<button onclick="editHouse(this)" style="margin-top:6px">✏️ Sửa</button> ' +
    '<button onclick="deleteHouse(this)">🗑 Xóa</button></div>';
}

// Form nhập / sửa thông tin hộ
function houseForm(l) {
  const p = props(l);
  return '<div style="min-width:240px"><b>✏️ Thông tin hộ</b><br>' +
    'Chủ hộ: <input id="fName" value="' + esc(p.name) + '" style="width:190px;margin:3px 0"><br>' +
    'Số nhà: <input id="fNum" value="' + esc(p['addr:housenumber']) + '" style="width:190px;margin:3px 0"><br>' +
    'Số thành viên: <input id="fMem" type="number" min="0" value="' + esc(p.members) + '" style="width:190px;margin:3px 0"><br>' +
    'Ghi chú: <input id="fNote" value="' + esc(p.note) + '" style="width:190px;margin:3px 0"><br>' +
    '<button onclick="saveHouse(this)">💾 Lưu</button> ' +
    '<button onclick="cancelEdit(this)">Hủy</button></div>';
}

function findLayer(el) {
  const pop = el.closest('.leaflet-popup');
  let layer = null;
  drawn.eachLayer(l => { if (l.getPopup() && l.getPopup().getElement() === pop) layer = l; });
  return layer;
}

window.editHouse = function(btn) {
  const l = findLayer(btn);
  if (l) l.setPopupContent(houseForm(l));
};
window.cancelEdit = function(btn) {
  const l = findLayer(btn);
  if (l) l.setPopupContent(houseInfo(l));
};
window.deleteHouse = function(btn) {
  const l = findLayer(btn);
  if (l && confirm('Xóa nhà này?')) {
    drawn.removeLayer(l);
    saveState();
  }
};
window.saveHouse = function(btn) {
  const l = findLayer(btn);
  if (!l) return;
  const p = props(l);
  p.name = document.getElementById('fName').value.trim();
  p['addr:housenumber'] = document.getElementById('fNum').value.trim();
  p.members = document.getElementById('fMem').value.trim();
  p.note = document.getElementById('fNote').value.trim();
  l.setPopupContent(houseInfo(l));
  saveState();
};

map.on(L.Draw.Event.CREATED, e => {
  const layer = e.layer;
  layer.feature = {type: 'Feature', properties: {building: 'house', name: '', 'addr:housenumber': '', members: '', note: ''}};
  layer.uid = uid++;
  layer.bindPopup(function(l) { return houseInfo(l); });
  drawn.addLayer(layer);
  layer.openPopup();
  saveState();
});
map.on(L.Draw.Event.EDITED, saveState);
map.on(L.Draw.Event.DELETED, saveState);

// ================= LƯU / KHÔI PHỤC (localStorage) =================
function addFeature(f) {
  if (f.geometry.type === 'Point') {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], {radius: 12, color: '#e67e22', weight: 3, fillColor: '#ffe08a', fillOpacity: .9})
      .addTo(mocLayer).bindPopup(mocPopup);
    m.feature = {type: 'Feature', properties: f.properties, geometry: null};
    m.name = (f.properties && f.properties.name) || 'Mốc';
  } else {
    const l = L.geoJSON(f).getLayers()[0];
    l.feature = f;
    l.uid = uid++;
    l.bindPopup(function(l) { return houseInfo(l); });
    drawn.addLayer(l);
  }
}
function collectAll() {
  const features = [];
  drawn.eachLayer(l => {
    const g = l.toGeoJSON();
    const p = props(l);
    g.properties = Object.assign({}, g.properties, {
      building: 'house',
      name: p.name || undefined,
      'addr:housenumber': p['addr:housenumber'] || undefined,
      members: p.members || undefined,
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
}
function restoreState() {
  let features = [];
  try { features = JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { features = []; }
  features.forEach(addFeature);
}

// ================= DANH SÁCH NHÀ =================
function refreshList() {
  const body = document.getElementById('listBody');
  const rows = [];
  drawn.eachLayer(l => {
    const p = props(l);
    const num = p['addr:housenumber'] || '';
    const name = p.name || '(chưa có tên)';
    const mem = p.members ? ' · ' + p.members + ' người' : '';
    rows.push({uid: l.uid, num: num, name: name, mem: mem});
  });
  rows.sort((a, b) => (a.num || 'ZZZ').localeCompare(b.num || 'ZZZ', 'vi'));
  body.innerHTML = rows.map(r =>
    '<div class="row" onclick="gotoHouse(' + r.uid + ')">' +
    '<b>' + (r.num ? 'Số ' + r.num : 'Nhà') + '</b> — ' + r.name +
    '<span class="cnt">' + r.mem + '</span></div>').join('') ||
    '<div class="row" style="color:#888">Chưa có nhà nào. Vẽ nhà bằng công cụ ▢ / polygon ở cột trái.</div>';
  document.getElementById('btnList').textContent = '📋 Danh sách (' + rows.length + ')';
}
window.gotoHouse = function(uid) {
  drawn.eachLayer(l => {
    if (l.uid === uid) {
      map.flyTo(l.getBounds().getCenter(), 19);
      l.openPopup();
    }
  });
};
document.getElementById('btnList').onclick = () => {
  const p = document.getElementById('listPanel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
  refreshList();
};

// ================= ĐẶT MỐC =================
const mocLayer = L.featureGroup().addTo(map);
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
      if (!res.length) { alert('Không tìm thấy. Thử từ khóa khác (vd: ĐH409, nhà thuốc...).'); return; }
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
  if (!features.length) { alert('Chưa có gì để xuất (vẽ nhà hoặc đặt mốc trước).'); return; }
  const fc = {type: 'FeatureCollection', features: features};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(fc, null, 2)], {type: 'application/geo+json'}));
  a.download = 'le-son-nam-houses.geojson';
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

// ================= XÓA HẾT =================
document.getElementById('btnClear').onclick = () => {
  if (!confirm('Xóa toàn bộ nhà + mốc đã vẽ? (không thể hoàn tác)')) return;
  drawn.clearLayers();
  mocLayer.clearLayers();
  saveState();
};

// ================= KHỞI TẠO =================
restoreState();
refreshList();
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
