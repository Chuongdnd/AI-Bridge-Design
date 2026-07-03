# CHƯƠNG 2: XÂY DỰNG QUY TRÌNH VÀ THUẬT TOÁN TỰ ĐỘNG HÓA THIẾT KẾ

## 2.1. Kiến trúc tổng thể hệ thống

### 2.1.1. Tổng quan kiến trúc

Hệ thống tự động hóa thiết kế cầu (AI-Bridge-Design) được xây dựng theo mô hình
**ứng dụng web đơn khối – phân lớp theo mô-đun** (modular monolith), phát triển
hoàn toàn bằng ngôn ngữ Python trên nền tảng **Streamlit** và triển khai trên
hạ tầng đám mây (Streamlit Community Cloud). Lựa chọn kiến trúc này xuất phát
từ ba yêu cầu đặc thù của bài toán thiết kế cầu ở bước thiết kế cơ sở:
(i) người dùng là kỹ sư thiết kế, cần truy cập qua trình duyệt mà không phải
cài đặt phần mềm; (ii) khối lượng tính toán mỗi phiên làm việc ở mức vừa phải
nhưng đòi hỏi tính **nhất quán tuyệt đối** giữa các sản phẩm đầu ra (mô hình
3D, bản vẽ 2D, bảng khối lượng, hồ sơ xuất); (iii) hệ thống phải kết hợp đồng
thời nhiều lớp "trí tuệ" khác nhau — mô hình học máy, luật thiết kế theo tiêu
chuẩn Việt Nam, và mô hình ngôn ngữ lớn (LLM) — trong cùng một quy trình.

Về mặt tổ chức, toàn bộ hệ thống được phân rã thành **sáu lớp chức năng**
xếp chồng, trao đổi dữ liệu với nhau thông qua một cấu trúc dữ liệu thiết kế
trung tâm (`design_data`) lưu trong phiên làm việc:

**a) Lớp giao diện và tương tác (Presentation Layer)**

Lớp giao diện được hiện thực trong mô-đun trung tâm `00-Interface.py`, đóng
vai trò "vỏ" của toàn hệ thống. Giao diện tổ chức theo dạng **thanh ribbon**
gồm các không gian làm việc chính: *Thuyết minh* (kết quả tính toán tổng hợp),
*Phương án 1 / 2 / 3* (bản vẽ 2D–3D của từng phương án kết cấu), *So sánh
phương án* và *Thư viện* (quản lý cấu kiện: dầm, trụ, mố, móng, lan can).
Việc khai báo số liệu đầu vào được gom vào một hộp thoại OPTIONS chia thành
ba bước (thông tin dự án – thủy văn/tĩnh không – địa hình/địa chất), sau đó
người dùng chỉ cần một thao tác "OK – Áp dụng cấu hình" để kích hoạt toàn bộ
chuỗi tính toán. Mọi biểu đồ và bản vẽ được dựng bằng thư viện **Plotly**
(2D và 3D tương tác), có bọc lớp cấu hình cảm ứng để thao tác được trên
thiết bị di động (một ngón trượt để pan, hai ngón chụm để zoom). Lớp này còn
bao gồm phân hệ xác thực người dùng (`00-Auth.py`, băm SHA-256 kèm salt, phân
quyền admin/user) và hệ thống trang phụ (`pages/`) cho các nghiệp vụ chuyên
sâu: nhập địa chất, dự toán, so sánh phương án, trợ lý AI, xuất thuyết minh
TKCS và vẽ chi tiết dầm.

**b) Lớp điều phối quy trình (Orchestration Layer)**

Trái tim của quá trình tự động hóa là **pipeline 9 bước** được định nghĩa
tường minh trong `00-Interface.py` (hằng `PIPELINE_STEPS`) và giám sát bởi
lớp `PipelineTracker`. Chín bước lần lượt là: (1) kiểm tra dữ liệu địa hình –
địa chất; (2) tra cứu tĩnh không thông thuyền theo TCVN 8818:2022; (3) tính
yếu tố hình học — mặt cắt ngang, bề rộng cầu, độ dốc dọc/ngang; (4) AI dự báo
kết cấu nhịp (loại dầm, số nhịp, chiều dài, chiều cao); (5) AI dự báo mố –
trụ; (6) tư vấn móng cọc; (7) tư vấn lớp phủ mặt cầu theo TCVN 8819:2011;
(8) sinh bản vẽ kết cấu; (9) sinh và đánh giá đồng thời **ba phương án** kết
cấu nhịp. Mỗi bước có trọng số tiến độ riêng, có cơ chế bắt lỗi cục bộ để một
bước gặp sự cố không làm sụp đổ toàn chuỗi. Kết quả của pipeline được ghi
ngược vào `design_data` (bao gồm khối `kcn_3_pa` chứa ba phương án), từ đó
mọi lớp phía sau chỉ đọc một nguồn dữ liệu duy nhất.

**c) Lớp lõi tính toán và trí tuệ nhân tạo (AI/Computation Core)**

Lớp này gồm các mô-đun tính toán độc lập, đánh số theo trình tự nghiệp vụ:
`01-Tinh_khong` (tĩnh không), `02-Yeuto_Hinhhoc` (yếu tố hình học),
`06-AI_KetCauNhip`, `07-AI_MoTru`, `08-AI_Mong` và `10-LopPhu_MatCau`.
Đặc trưng kiến trúc quan trọng ở đây là **mô hình lai hai tầng
(AI + rule-based)**: các mô-đun AI sử dụng học máy có giám sát
(RandomForest, GradientBoosting của scikit-learn) huấn luyện trên bộ dữ liệu
công trình thực tế `Bridge_Train_Dataset_v3.xlsx`, đồng thời luôn duy trì
một nhánh dự phòng bằng **luật thiết kế** tra theo catalog định hình và tiêu
chuẩn Việt Nam (TCVN 11823:2017, TCVN 10304:2014...). Ba phương án được sinh
theo ba chiến lược khác nhau: PA1 — luật tối ưu chi phí (ít trụ, nhịp dài);
PA2 — luật tối ưu mỹ quan (mỗi khoang thông thuyền một nhịp); PA3 — dự báo
thuần AI kết hợp tra catalog. Nhờ đó hệ thống vẫn cho kết quả hợp lệ ngay cả
khi thiếu dữ liệu huấn luyện, và người dùng có căn cứ so sánh giữa "kinh
nghiệm luật hóa" và "dự báo học máy".

**d) Lớp mô hình hình học và sinh bản vẽ (Geometry & Drawing Engine)**

Đây là lớp có khối lượng mã lớn nhất, gồm `11-BanVe_KetCau.py` (động cơ bản
vẽ 2D/3D), `17-BeamBuilder` + `17-BeamBuilderUI` (dựng dầm tham số từ mặt
cắt thư viện, kể cả đầu dầm khấc), `19-PierBuilder` (dựng trụ lắp ghép từ ba
bộ phận xà mũ – thân – bệ) và các tiện ích `00-Drawing_Utils`,
`00-Terrain_Viewer`. Nguyên tắc kiến trúc chi phối toàn lớp là **"một nguồn
sự thật hình học"** (single source of truth): tuyến đường đỏ được khai báo
một lần bằng hàm `make_red_line()` (đường cong đứng bán kính R + dốc dọc,
đỉnh tại tim tĩnh không) và dùng chung cho trắc dọc, mặt cắt ngang, mặt bằng
và mô hình 3D; trụ cầu được dựng **một lần duy nhất** thành lưới 3D
(`build_pier_mesh_traces`), sau đó các bản vẽ chi tiết được suy ra bằng phép
**cắt lưới thật** (`cut_mesh_traces` — mặt cắt ngang tại lý trình) hoặc phép
**chiếu bóng lưới** (`project_mesh_traces` — mặt đứng), thay vì vẽ độc lập
từng hình. Cách tổ chức này bảo đảm về mặt cấu trúc rằng mọi hình chiếu 2D
luôn khớp tuyệt đối với mô hình 3D — sai lệch giữa các bản vẽ bị loại trừ
từ gốc chứ không phải xử lý bằng hiệu chỉnh thủ công.

**e) Lớp dữ liệu và tri thức (Data & Knowledge Layer)**

Lớp dữ liệu gồm bốn nhóm: (1) **thư viện cấu kiện** dạng JSON tại
`Data/Library/` (dầm, xà mũ, thân trụ, bệ trụ, trụ tổng, mố, móng, lan can)
quản lý qua mô-đun thuần Python `utils/component_library.py`, cho phép người
dùng bổ sung cấu kiện từ file DXF và tái sử dụng cho cả ba phương án;
(2) **bộ dữ liệu huấn luyện** và các mô hình học máy đã lưu (`*.pkl`);
(3) **kho tri thức** `Data/Knowledge_Base/` (TCVN, văn bản pháp lý, catalog,
kinh nghiệm thiết kế) được đánh chỉ mục vec-tơ bởi `14-RAG_Indexer` phục vụ
truy vấn ngữ nghĩa; (4) **không gian làm việc đa người dùng**
(`utils/workspace.py`) lưu thư viện riêng và các dự án của từng tài khoản
(`users/<user>/projects/<id>/design.json`), tách bạch hoàn toàn khỏi tầng
giao diện.

**f) Lớp xuất hồ sơ và trợ lý AI (Export & Assistant Layer)**

Đầu ra của hệ thống được chuẩn hóa ở ba định dạng hồ sơ kỹ thuật:
bản vẽ **DXF** (ezdxf) cho mặt cắt ngang, trắc dọc, mố trụ; mô hình
**BIM/IFC** (ifcopenshell — `09-Export_CAD_IFC` và `18-IFC_Exporter` xuất
trực tiếp từ lưới 3D thực của mô hình); và **thuyết minh thiết kế cơ sở
DOCX** (`16-TKCS_Generator`) soạn theo bố cục Nghị định 175/2024/NĐ-CP.
Song song, trợ lý AI (`15-Bridge_AI_Assistant`) kết hợp pipeline RAG trên kho
tri thức với mô hình ngôn ngữ lớn để trả lời các câu hỏi chuyên môn ngay trong
ngữ cảnh đồ án đang thiết kế.

Kiến trúc tổng thể và quan hệ giữa sáu lớp được minh họa ở sơ đồ sau:

```
┌──────────────────────────────────────────────────────────────────────┐
│  (a) GIAO DIỆN — Streamlit  ·  00-Interface / 00-Auth / pages/*      │
│      Ribbon: Thuyết minh · PA1 · PA2 · PA3 · So sánh PA · Thư viện   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ design_data (session_state)
┌──────────────────────────────▼───────────────────────────────────────┐
│  (b) ĐIỀU PHỐI — Pipeline 9 bước + PipelineTracker                    │
│      DC → TK → YTHH → KCN → MOT → MONG → LPC → BVK → SSP             │
└──────┬──────────────────────────────────────────────┬────────────────┘
       │                                              │
┌──────▼──────────────────────────┐   ┌───────────────▼───────────────┐
│ (c) LÕI TÍNH TOÁN & AI           │   │ (d) HÌNH HỌC & BẢN VẼ          │
│  01-Tinh_khong  02-YT_HinhHoc    │   │  11-BanVe_KetCau (2D/3D)       │
│  06-AI_KCN  07-AI_MoTru          │   │  17-BeamBuilder(UI)            │
│  08-AI_Mong  10-LopPhu           │   │  19-PierBuilder                │
│  [ML: RF/GB  +  Rule-based TCVN] │   │  [1 lưới 3D → cắt/chiếu 2D]    │
└──────┬──────────────────────────┘   └───────────────┬───────────────┘
       │                                              │
┌──────▼──────────────────────────────────────────────▼────────────────┐
│  (e) DỮ LIỆU & TRI THỨC — Data/Library (JSON) · Dataset v3 · *.pkl   │
│      Knowledge_Base (RAG) · users/<u>/ (workspace đa người dùng)      │
└──────────────────────────────┬───────────────────────────────────────┘
┌──────────────────────────────▼───────────────────────────────────────┐
│  (f) XUẤT HỒ SƠ & TRỢ LÝ — DXF (ezdxf) · IFC (ifcopenshell)          │
│      DOCX TKCS (NĐ 175/2024) · AI Assistant (RAG + LLM)               │
└──────────────────────────────────────────────────────────────────────┘
```

Bên cạnh việc phân lớp, kiến trúc hệ thống tuân thủ bốn nguyên tắc thiết kế
phần mềm xuyên suốt:

1. **Mô-đun hóa theo tiền tố số và nạp động**: mỗi khối nghiệp vụ là một
   file Python độc lập đánh số theo trình tự quy trình thiết kế (00 → 19),
   được nạp động bằng `importlib` tại mô-đun trung tâm; nhờ đó có thể phát
   triển, kiểm thử và thay thế từng khối mà không ảnh hưởng phần còn lại.
2. **Tách lõi tính toán khỏi giao diện**: các mô-đun trong `utils/` và các
   động cơ tính toán được viết thuần Python (không phụ thuộc Streamlit),
   cho phép kiểm thử tự động độc lập và tái sử dụng cho các kênh triển khai
   khác trong tương lai.
3. **Dự phòng phân tầng (graceful degradation)**: mọi nhánh AI đều có nhánh
   luật thay thế, mọi bước pipeline đều được bao bọc bắt lỗi — hệ thống
   suy giảm chức năng từng phần thay vì dừng toàn bộ.
4. **Một nguồn sự thật dữ liệu và hình học**: toàn bộ trạng thái thiết kế
   quy về một từ điển `design_data` duy nhất; toàn bộ hình học quy về một
   mô hình 3D duy nhất mà các bản vẽ 2D là các lát cắt/hình chiếu của nó.

Luồng dữ liệu tổng quát của một phiên thiết kế do đó có thể tóm tắt:
*số liệu khảo sát và yêu cầu thiết kế* → `design_data` → *pipeline 9 bước*
→ *ba phương án kết cấu* (`kcn_3_pa`) → *mô hình 3D và hệ bản vẽ đồng bộ*
→ *khối lượng – dự toán – so sánh phương án* → *hồ sơ DXF/IFC/DOCX*. Các mục
tiếp theo (2.1.2, 2.1.3) sẽ trình bày chi tiết từng lớp và các thuật toán
bên trong quy trình này.
