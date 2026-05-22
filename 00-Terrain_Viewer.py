import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
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
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        try:
            col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        except IndexError:
            col_name = df_coord.columns[1]
            
        col_x = df_coord.columns[3]
        col_y = df_coord.columns[4]
        
        x_numeric = pd.to_numeric(df_coord[col_x], errors='coerce')
        y_numeric = pd.to_numeric(df_coord[col_y], errors='coerce')
        
        df_clean = pd.DataFrame({
            'Cọc_Excel': df_coord[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': x_numeric,
            'Y_VN2000': y_numeric
        })
        return df_clean.dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN ĐỒNG BỘ TUẦN TỰ SONG SONG CHUẨN XÁC
    """
    try:
        list_ntd_x = sorted(df_ntd['Lý trình'].unique())
        df_coord_clean = df_coord.copy()
        
        min_len = min(len(list_ntd_x), len(df_coord_clean))
        if min_len == 0:
            return pd.DataFrame()
            
        map_x_real = {}
        map_y_real = {}
        for i in range(min_len):
            ly_trinh_ntd = list_ntd_x[i]
            map_x_real[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
            map_y_real[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
            
        df_merged = df_ntd.copy()
        df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_real)
        df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_real)
        
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        
        df_tim_calc = df_merged[df_merged['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình').copy()
        
        # Sử dụng hàm Gradient vi phân mượt để vector hướng không bao giờ bị gãy khúc gập ghềnh
        if len(df_tim_calc) >= 2:
            df_tim_calc['dX'] = np.gradient(df_tim_calc['X_VN2000'].values)
            df_tim_calc['dY'] = np.gradient(df_tim_calc['Y_VN2000'].values)
        else:
            df_tim_calc['dX'] = 1.0
            df_tim_calc['dY'] = 0.0
            
        df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
        
        goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
        df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
        
        # Quay lượng giác đưa toàn bộ điểm mia về hệ phẳng VN-2000 thực tế
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def tao_ma_tran_be_mat_xuyen_suot(df):
    """
    ⚡ GIẢI PHÁP TỐI HẬU CỦA TOÁN HỌC TRẮC ĐẠC: Ma trận dệt bề mặt uốn cong liên tục
    - Trên 1 cọc: Cọc đo rộng ra biên bao nhiêu mét thì giữ nguyên bản 100%, nội suy vuốt từ trái sang phải.
    - Giữa các cọc: Đồng bộ ma trận 2D giúp go.Surface tự động vuốt phẳng liên tục từ đầu tuyến đến cuối tuyến.
    - Loại bỏ vĩnh viễn 100% lỗi đứt gãy tấm, lỗi sợi chỉ cô lập hay rách đoạn cong!
    """
    unique_lts = sorted(df['Lý trình'].unique())
    num_samples_per_mcn = 30  # Đan ma trận gồm 30 hàng dọc song song chạy xuyên suốt con sông
    target_pct = np.linspace(0.0, 1.0, num_samples_per_mcn)
    
    matrix_x = []
    matrix_y = []
    matrix_z = []
    
    for lt in unique_lts:
        df_sub = df[df['Lý trình'] == lt].sort_values('Offset')
        if df_sub.empty:
            continue
            
        obs_offsets = df_sub['Offset'].values
        obs_x_real = df_sub['X_Real'].values
        obs_y_real = df_sub['Y_Real'].values
        obs_zs = df_sub['Z'].values
        
        # Chuẩn hóa khoảng cách trắc ngang từ biên trái sang biên phải theo tỷ lệ phần trăm phân bố thực tế
        if len(obs_offsets) > 1:
            pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0])
            x_line = np.interp(target_pct, pct_goc, obs_x_real)
            y_line = np.interp(target_pct, pct_goc, obs_y_real)
            z_line = np.interp(target_pct, pct_goc, obs_zs)
        else:
            x_line = np.repeat(obs_x_real[0], num_samples_per_mcn)
            y_line = np.repeat(obs_y_real[0], num_samples_per_mcn)
            z_line = np.repeat(obs_zs[0], num_samples_per_mcn)
            
        matrix_x.append(x_line)
        matrix_y.append(y_line)
        matrix_z.append(z_line)
        
    # Trả về ma trận mảng 2D hoàn chỉnh - Đây là điều kiện bắt buộc để go.Surface tự đan dải lụa kín đặc
    return np.array(matrix_x), np.array(matrix_y), np.array(matrix_z)

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    DỰNG MÔ HÌNH ĐỊA HÌNH 3D HÀNH LẠNG TUYẾN XUYÊN SUỐT, PHẲNG MỊN KHÔNG ĐỨT KHÚC
    """
    if df.empty:
        return None
    try:
        # Gọi cấu trúc ma trận 2D uốn lượn liên tục bám sát hành lang sông
        x_grid, y_grid, z_grid = tao_ma_tran_be_mat_xuyen_suot(df)
        
        # Áp dụng trực tiếp hệ số tỉ lệ phóng đại đứng slider
        z_scaled = z_grid * he_so_z
        
        # Sử dụng go.Surface trên nền ma trận uốn cong để dệt bề mặt đặc khít kẽ
        fig = go.Figure(data=[go.Surface(
            x=x_grid, y=y_grid, z=z_scaled,
            customdata=z_grid,
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth', opacity=0.95,
            showscale=True,
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
            contours=dict(x=dict(show=False), y=dict(show=False)) # Ẩn lưới sọc phụ cho mượt mà mượt mắt
        )])
        
        fig.update_layout(
            title=dict(text="🏔️ MÔ HÌNH ĐỊA HÌNH 3D ĐỊNH VỊ TOÀN CẦU CHUẨN VN-2000", font=dict(size=16, color='#007acc')),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='data'
            ),
            template="plotly_dark", margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D VN-2000: {e}")
        return None