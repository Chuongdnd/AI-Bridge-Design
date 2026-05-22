import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    Trích xuất Lý trình (X), Khoảng cách cánh (Offset) và Cao độ (Z) từ trắc dọc trắc ngang
    """
    data_points = []
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0
    current_pole = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        # 1. Quét mốc cọc tim tuyến chính
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim
                })
            except ValueError:
                pass
        # 2. Quét điểm mia trắc ngang trích cánh trái/phải
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole, 'Lý trình': current_x, 'Offset': dist_offset, 'Z': z_val
                    })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def parse_coordinate_file(uploaded_file):
    """
    BỘ GIẢI MÃ BẢNG TOẠ ĐỘ VN-2000
    Bỏ qua dòng tiêu đề phụ thứ nhất (skiprows=1) để nhận diện đúng cấu trúc cột Excel/CSV
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        # Chuẩn hóa viết hoa và xóa khoảng trắng ở tên tiêu đề cột
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        # Nhận diện cột tự động bằng bộ lọc từ khóa kỹ thuật trắc đạc
        col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        col_x = [c for c in df_coord.columns if 'X(M)' in c or 'X' in c][0]
        col_y = [c for c in df_coord.columns if 'Y(M)' in c or 'Y' in c][0]
        
        df_clean = pd.DataFrame({
            'Cọc_Excel': df_coord[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': df_coord[col_x].astype(float),
            'Y_VN2000': df_coord[col_y].astype(float)
        })
        # Loại bỏ triệt để dòng trống và Reset cứng Index về chuỗi tăng dần liên tục
        df_clean = df_clean.dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
        return df_clean
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN ĐỒNG BỘ TUẦN TỰ SONG SONG (INDEX-BASED MATCHING)
    Đồng bộ chuẩn xác tọa độ thực tế cho các điểm mốc tim tương ứng bất chấp lệch Index (.iloc tuyển chọn)
    """
    try:
        # 1. Trích xuất thứ tự danh sách lý trình tim tuyến duy nhất từ file NTD (Sắp xếp tăng dần)
        list_ntd_x = sorted(df_ntd['Lý trình'].unique())
        
        # 2. Lấy chuỗi danh sách tọa độ thực tế từ file Excel
        df_coord_clean = df_coord.copy()
        
        # Tính toán chiều dài giới hạn khớp chuỗi liên tiếp của cả 2 tệp dữ liệu
        min_len = min(len(list_ntd_x), len(df_coord_clean))
        if min_len == 0:
            return pd.DataFrame()
            
        # 3. 🎯 SỬA LỖI CORE: Ép cặp dùng .iloc[i] để định vị tuyệt đối theo số thứ tự dòng, bẻ gãy hoàn toàn lỗi KeyError
        map_x_real = {}
        map_y_real = {}
        for i in range(min_len):
            ly_trinh_ntd = list_ntd_x[i]
            map_x_real[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
            map_y_real[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
            
        # 4. Gắn tọa độ thực VN-2000 của mốc tim vào bảng dữ liệu tổng thể điểm mia hình học
        df_merged = df_ntd.copy()
        df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_real)
        df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_real)
        
        # Loại bỏ các điểm nằm ngoài dải đồng bộ thứ tự hàng
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        
        # 5. Tính toán Véc-tơ hướng tuyến phục vụ phép quay lượng giác
        df_tim_calc = df_merged[df_merged['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình').copy()
        df_tim_calc['dX'] = df_tim_calc['X_VN2000'].diff().shift(-1)
        df_tim_calc['dY'] = df_tim_calc['Y_VN2000'].diff().shift(-1)
        df_tim_calc['dX'] = df_tim_calc['dX'].bfill().ffill()
        df_tim_calc['dY'] = df_tim_calc['dY'].bfill().ffill()
        
        df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
        goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
        df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
        
        # 6. PHÉP QUAY LƯỢNG GIÁC PHẲNG: Bắn tọa độ điểm trắc ngang cánh vuông góc ra 2 bên tim thực VN-2000
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def ve_binh_do_goc_2d(df):
    """
    DỰNG BÌNH ĐỒ SỐ ĐỊA HÌNH KHÔNG GIAN 2D TRÊN TOẠ ĐỘ THỰC VN-2000
    """
    if df.empty: 
        return None
    try:
        fig = go.Figure(data=go.Mesh3d(
            x=df['X_Real'], y=df['Y_Real'], z=df['Z'],
            intensity=df['Z'], colorscale='Viridis',
            opacity=0.90, showscale=True,
            colorbar=dict(title="Cao độ Z (m)", thickness=15)
        ))
        
        fig.update_layout(
            title=dict(text="🗺️ BÌNH ĐỒ SỐ ĐỊA HÌNH KHÔNG GIAN ĐỊNH VỊ THỰC TẾ VN-2000", font=dict(size=15, color='#007acc')),
            xaxis_title="Tọa độ thực X (m)", yaxis_title="Tọa độ thực Y (m)",
            yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='#222c3c'),
            xaxis=dict(gridcolor='#222c3c'),
            template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='#0e1117', paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi dựng bình đồ phẳng VN-2000: {e}")
        return None

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D TRÊN HỆ TOẠ ĐỘ THỰC VN-2000
    - Sử dụng Mesh3d đan lưới đa hướng tự do chuẩn trắc địa nhằm xử lý tuyến uốn cong.
    """
    if df.empty:
        return None
        
    try:
        # Bộ lọc thưa nén lưới đa giác nếu tổng số điểm khảo sát quá đồ sộ (>2000 điểm mia)
        df_render = df.iloc[::2].copy() if len(df.index) > 2000 else df.copy()
        
        # Áp dụng trực tiếp hệ số tỉ lệ trục đứng slider (he_so_z) vào ma trận hiển thị
        z_scaled = df_render['Z'] * he_so_z
        
        fig = go.Figure(data=[go.Mesh3d(
            x=df_render['X_Real'],
            y=df_render['Y_Real'],
            z=z_scaled,
            intensity=df_render['Z'], # Đổ dải hệ màu bám sát theo cao độ tự nhiên gốc
            colorscale='Earth',       # Giữ nguyên hệ màu chuẩn địa hình gốc
            opacity=0.95,
            showscale=True,
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Cao độ: %{intensity:.2f} m<extra></extra>"
        )])
        
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH ĐỊA HÌNH 3D ĐỊNH VỊ TOÀN CẦU CHUẨN VN-2000",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='data' # Giữ nguyên ép tuyệt đối về tỷ lệ kích thước thật thực địa
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D VN-2000: {e}")
        return None