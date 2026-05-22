import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.interpolate import griddata
def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    Lấy đầy đủ POLE (Lý trình + Cao độ tim Y=0) và TARGETL/R (Khoảng cách lẻ Y + Cao độ Z)
    """
    data_points = []
    
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0  # Lý trình trắc dọc (Trục X tổng thể)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        # 1. LẤY CỌC TIM TUYẾN: Xác định Lý trình X và Cao độ Z tại vị trí tim Y = 0
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'X': current_x, 
                    'Y': 0.0, 
                    'Z': z_tim,
                    'Type': 'Tim tuyến'
                })
            except ValueError:
                pass
                
        # 2. LẤY TRẮC NGANG CÁNH: Xác định Khoảng cách Y và Cao độ Z tương ứng
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1]) # Khoảng cách trắc ngang (Trục Y)
                z_val = float(parts[2])        # Cao độ trắc ngang (Trục Z)
                
                data_points.append({
                    'X': current_x, 
                    'Y': dist_offset, 
                    'Z': z_val,
                    'Type': 'Mia địa hình'
                })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def ve_dia_hinh_3d(df, he_so_z=5.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - HIỂN THỊ ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH TRÊN BỀ MẶT
    - Đường đồng mức hiển thị tĩnh trực tiếp trên bề mặt 3D ngay từ đầu.
    - Không chiếu đáy, không phụ thuộc hover chuột.
    """
    if df.empty or len(df.index) < 3:
        return None

    try:
        # ── 1. XÂY DỰNG LƯỚI ĐỊA HÌNH ──────────────────────────────────────────
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)

        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values

        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)
        z_range    = z_max_real - z_min_real

        # ── 2. TỰ ĐIỀU CHỈNH BƯỚC CAO ĐỀU NẾU BIÊN ĐỘ Z QUÁ HẸP ───────────────
        if z_range > 0 and buoc_nhay_cao_do > z_range / 3:
            buoc_nhay_cao_do = round(z_range / 5, 2)
            buoc_nhay_cao_do = max(buoc_nhay_cao_do, 0.1)   # tối thiểu 0.1 m

        # Scale trục Z để khối nhìn cân đối hơn
        z_scaled       = z_real * he_so_z
        buoc_ve_scaled = buoc_nhay_cao_do * he_so_z

        contour_start = np.ceil(z_min_real  / buoc_nhay_cao_do) * buoc_nhay_cao_do * he_so_z
        contour_end   = np.floor(z_max_real / buoc_nhay_cao_do) * buoc_nhay_cao_do * he_so_z

        # ── 3. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC HIỂN THỊ TĨNH TRÊN BỀ MẶT 3D ───────────
        if hien_dong_muc and contour_start < contour_end:
            contour_config = dict(
                show           = True,
                start          = contour_start,
                end            = contour_end,
                size           = buoc_ve_scaled,
                usecolormap    = False,
                color          = "rgba(255, 255, 255, 0.95)",  # TRẮNG - nổi rõ trên Earth
                width          = 3,
                highlight      = True,                          # BẬT để Plotly render tĩnh ngay
                highlightcolor = "rgba(255, 80, 80, 1.0)",     # ĐỎ khi hover - phân biệt rõ
                highlightwidth = 6,
                project        = dict(z=False)                  # KHÔNG chiếu xuống đáy
            )
        else:
            contour_config = dict(show=False)

        # ── 4. BỀ MẶT ĐỊA HÌNH ──────────────────────────────────────────────────
        surface = go.Surface(
            x          = x_grid,
            y          = y_grid,
            z          = z_scaled,
            customdata = z_real,
            hovertemplate = (
                "X: %{x:.1f} m<br>"
                "Y: %{y:.2f} m<br>"
                "Z gốc: %{customdata:.2f} m<extra></extra>"
            ),
            colorscale = 'Earth',
            opacity    = 1.0,
            flatshading = True,          # PHẲNG HOÁ BỀ MẶT → đường đồng mức không bị che
            contours   = dict(z=contour_config),

            # Ánh sáng phẳng tuyệt đối — không bóng đổ che khuất nét đường
            lighting = dict(
                ambient  = 1.0,
                diffuse  = 0.0,
                specular = 0.0,
                roughness= 1.0,
                fresnel  = 0.0
            ),
            lightposition = dict(x=0, y=0, z=1e5),

            colorbar = dict(
                title     = dict(text="Cao độ Z (m)", side="right"),
                thickness = 15,
                tickvals  = np.arange(
                    np.ceil(z_min_real),
                    np.floor(z_max_real) + 1,
                    buoc_nhay_cao_do
                ) * he_so_z,
                ticktext  = [
                    f"{v/he_so_z:.1f} m"
                    for v in np.arange(
                        np.ceil(z_min_real),
                        np.floor(z_max_real) + 1,
                        buoc_nhay_cao_do
                    ) * he_so_z
                ]
            )
        )

        fig = go.Figure(data=[surface])

        # ── 5. LAYOUT & KHUNG NHÌN ───────────────────────────────────────────────
        fig.update_layout(
            title = dict(
                text   = f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D  —  ĐƯỜNG ĐỒNG MỨC {buoc_nhay_cao_do:.2f} M",
                font   = dict(size=14, color='#7ec8e3', family='Arial'),
                x      = 0.5,
                xanchor= 'center'
            ),
            scene = dict(
                xaxis_title = "Lý trình X (m)",
                yaxis_title = "Trắc ngang Y (m)",
                zaxis_title = "Cao độ Z (m)",

                aspectmode  = 'manual',
                aspectratio = dict(x=1.0, y=0.7, z=0.4),

                xaxis = dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                yaxis = dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                zaxis = dict(
                    range    = [np.min(z_scaled) - buoc_ve_scaled,
                                np.max(z_scaled) + buoc_ve_scaled],
                    showgrid = True,
                    gridcolor= 'rgba(255,255,255,0.1)',
                    tickvals = np.arange(
                        np.ceil(z_min_real),
                        np.floor(z_max_real) + 1,
                        buoc_nhay_cao_do
                    ) * he_so_z,
                    ticktext = [
                        f"{v:.1f} m"
                        for v in np.arange(
                            np.ceil(z_min_real),
                            np.floor(z_max_real) + 1,
                            buoc_nhay_cao_do
                        )
                    ]
                ),

                camera = dict(
                    eye  = dict(x=1.25, y=1.25, z=0.8),   # Góc nhìn bao quát, không quá cao
                    up   = dict(x=0, y=0, z=1)
                )
            ),
            template       = "plotly_dark",
            margin         = dict(l=10, r=10, t=50, b=10),
            paper_bgcolor  = '#0e1117',
            hoverlabel     = dict(bgcolor='#1e2130', font_size=12)
        )

        return fig

    except Exception as e:
        print(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None