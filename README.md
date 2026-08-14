# Quản lý nhà & tổ dân cư – Thôn Lệ Sơn Nam (Hòa Tiến, Hòa Vang, Đà Nẵng)

Ứng dụng bản đồ web (Leaflet) để **vẽ tay từng nhà + ranh giới tổ** trên ảnh vệ tinh,
nhập **thông tin hộ gia đình** (chủ hộ, số nhà, nhân khẩu, người cao tuổi, trẻ em)
và **thống kê theo tổ** — dữ liệu tự lưu trong trình duyệt, xuất được GeoJSON.

## Tính năng

- 🏘 **Vẽ nhà** (hình chữ nhật / đa giác) theo mái nhà trên ảnh vệ tinh — vẽ xong mở thẳng form nhập hộ
- 🗺 **Vẽ ranh giới tổ / khu dân cư** — click tổ → bảng tổng hợp: số hộ, nhân khẩu, NCT, trẻ em
- 🏠 **Click nhà** → xem/sửa/xóa thông tin hộ (chủ hộ, số nhà, nhân khẩu, NCT, trẻ em, ghi chú)
- 📋 **Danh sách** tổ & nhà — nhấp để nhảy tới đối tượng
- 📊 **Thống kê** toàn thôn theo tổ (+ hàng "Chưa phân tổ" và "Tổng toàn thôn")
- 📌 Đặt mốc tham chiếu (vd: Nhà Văn Hóa Thôn Lệ Sơn Nam)
- 💾 **Tự lưu vào localStorage** — reload không mất dữ liệu
- ⬇ Xuất / 📂 Import GeoJSON (kèm members, elderly, children, addr:housenumber, note)
- 🔍 Tìm kiếm địa danh (Nominatim)

## Yêu cầu

- **Python 3** (>= 3.7) — chỉ cần cho máy chủ tĩnh / build
- Trình duyệt hiện đại (Chrome, Firefox, Edge, Safari) — không cần cài thêm gì

## Cách chạy (2 bước)

```bash
cd ~/le-son-nam
python3 -m http.server 8899 --bind 127.0.0.1
```

Mở trình duyệt: **http://127.0.0.1:8899/**

> Mẹo: mở thẳng file `index.html` cũng dùng được phần lớn tính năng, nhưng nên
> dùng `http.server` để tìm kiếm Nominatim và một số thao tác hoạt động ổn định nhất.

## Cấu trúc dự án

```
le-son-nam/
├── index.html            # App Leaflet tự chứa (chạy được ngay) — file được sinh ra
├── build_app.py          # Script build lại index.html (nhúng dữ liệu vào HTML)
├── data/
│   ├── zone_roads.geojson      # Đường OSM trong vùng thôn
│   ├── zone_buildings.geojson  # Nhà OSM (dữ liệu tham chiếu)
│   ├── zone_pois.geojson       # Trạm xe buýt, nhà thuốc...
│   └── ...
├── filter_village.py     # Lọc dữ liệu OSM theo thôn (Overpass → GeoJSON)
├── prepare_zone.py       # Chuẩn bị dữ liệu vùng cho app
└── ai/                   # (Tùy chọn) pipeline AI SAM — không bắt buộc để chạy app
```

## Build lại app sau khi sửa dữ liệu

```bash
cd ~/le-son-nam
python3 build_app.py
```

Script đọc các file trong `data/`, nhúng vào `index.html` rồi ghi đè — mở lại trang là thấy thay đổi.

## Dashboard EDA + chatbot DeepSeek

Dashboard của `smart-village.html` đọc số liệu nhân khẩu từ workbook Excel và giữ dữ liệu bản đồ độc lập:

```bash
/Users/paul/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 generate_dashboard_data.py
python3 server.py
```

Pipeline tạo dashboard tách hộ theo từng khối dòng liên tiếp trong file import, thay vì chỉ gom theo tên chủ hộ. Cách này tránh gộp nhầm các hộ khác nhau nhưng trùng tên; bản dữ liệu hiện có 569 hộ và 2.150 nhân khẩu.

Để bật trả lời bằng DeepSeek, cấu hình khóa trong biến môi trường (không ghi khóa vào mã nguồn):

```bash
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python3 server.py
```

Không có `DEEPSEEK_API_KEY`, chatbot vẫn trả lời các câu hỏi tổng hợp, theo tổ và chi tiết thành viên của từng hộ bằng chế độ offline. Endpoint proxy là `POST /api/chat`; khóa API chỉ được dùng ở server.

## Xuất / Import dữ liệu

- **⬇ Xuất GeoJSON**: bấm nút phải trên — tải file `le-son-nam-data.geojson`
  (nhà kèm `name`, `addr:housenumber`, `members`, `elderly`, `children`, `note`;
  tổ đánh dấu `type: "to"`; mốc dạng Point)
- **📂 Import**: nạp lại file đã xuất (hoặc file GeoJSON khác) — dữ liệu cộng dồn vào bản đồ
- Dữ liệu có thể mở bằng **JOSM / iD / QGIS** để tiếp tục chỉnh sửa

## Lưu ý

- **Lớp nền Google** (Vệ tinh / Hybrid / Road) là dữ liệu không chính thức — chỉ dùng để
  tham chiếu khi vẽ, **không copy thẳng vào OpenStreetMap**. Lớp nền OSM / Esri là nguồn hợp lệ.
- Dữ liệu đã vẽ nằm trong **localStorage của trình duyệt** — nếu đổi máy/trình duyệt, hãy
  ⬇ Xuất GeoJSON trước rồi 📂 Import trên máy mới.
- Nút **🗑 Xóa tổ** xóa toàn bộ ranh giới tổ; **🗑 Xóa hết** xóa nhà + tổ + mốc (có xác nhận).

## (Tùy chọn) Pipeline AI — SAM

Thư mục `ai/` chứa script trích xuất nhà tự động bằng Segment-Anything (đã ngừng dùng trong app):

```bash
pip3 install --user --find-links=ai/wheels torch torchvision
pip3 install --user segment-anything shapely scikit-image pillow
python3 ai/extract.py          # chạy SAM trên ảnh vệ tinh → data/ai_buildings.geojson
```

Cần checkpoint `ai/sam_vit_b_01ec64.pth` (đã bỏ khỏi git do >100MB — tải riêng).
