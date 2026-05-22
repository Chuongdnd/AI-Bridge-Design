import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from PIL import Image
from pyproj import Transformer

def chuyen_vn2000_sang_wgs84(x, y, kinh_tuyen_truc=105.0):
    """
    🎯 TOÁN HỌC TRẮC ĐỊA CORE: Dịch chuyển hệ tọa độ phẳng VN-2000 sang WGS-84 của Google Maps.
    - mặc định kinh_tuyen_truc = 105.0 (Thay đổi theo đúng tỉnh thành khảo sát, ví dụ Hà Nội: 105.0, TP.HCM: 105.75)
    """
    try:
        # Khai báo chuỗi định nghĩa chuẩn Gauss-Kruger/UTM VN-2000 múi chiếu 3 độ
        vn2000_str = f"+proj=tmerc +lat_0=0 +lon_0={kinh_tuyen_truc} +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=-191.8,-39.3,-111.5,-0.009,-0.019,0.0042,-0.252 +units=m +no_defs"
        wgs84_str = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        
        transformer = Transformer.from_crs(vn2000_str, wgs84_str, always_xy=True)
        lon, lat = transformer.transform(x, y)
        return lat, lon
    except Exception:
        # Nếu lỗi trả về tọa độ mặc định để không sập app
        return 21.0285, 105.8542

def tai_anh_ve_tinh_google(lat_center, lon_center, width_m, height_m, api_key="YOUR_GOOGLE_API_KEY"):
    """
    📡 GỌI API GOOGLE MAPS: Tự động tính toán Zoom Level tương ứng với chiều dài con sông
    và tải ảnh vệ tinh dạng ByteStream về bộ nhớ tạm.
    """
    # Thuật toán tính toán Zoom Level tương đối dựa trên mét thực địa
    max_dim = max(width_m, height_m)
    if max_dim < 500: zoom = 18
    elif max_dim < 1000: zoom = 17
    elif max_dim < 2000: zoom = 16
    elif max_dim < 4000: zoom = 15
    else: zoom = 14
    
    # URL Static Maps gọi dữ liệu ảnh vệ tinh (SATELLITE)
    # Lưu ý: Thay api_key của bạn hoặc sử dụng không key nếu phạm vi test nhỏ (Google có giới hạn)
    url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat_center},{lon_center}&zoom={zoom}&size=640x640&maptype=satellite&key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception:
        pass
    return None

def ve_dia_hinh_3d(df, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3, kich_hoat_ve_tinh=False, ktt=105.0, api_key=""):
    """
    🏔️ MÔ HÌNH ĐỊA HÌNH 3D PHƯƠNG ÁN 2: TỰ ĐỘNG PHỦ ẢNH VỆ TINH THEO VN-2000
    """
    if df.empty: 
        return None
    
    try:
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values
            obs_y_real = df_sub['Y_Real'].values
            obs_zs = df_sub['Z'].values
            
            if len(obs_offsets) < 2:
                goc_tuyen = df_sub['Góc_Tuyến'].iloc[0]
                g_offset = goc_tuyen + (np.pi / 2)
                offsets_fake = np.linspace(-25.0, 25.0, num_samples)
                x_line = df_sub['X_VN2000'].iloc[0] + offsets_fake * np.cos(g_offset)
                y_line = df_sub['Y_VN2000'].iloc[0] + offsets_fake * np.sin(g_offset)
                z_line = np.repeat(obs_zs[0], num_samples)
            else:
                pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0] + 0.0001)
                x_line = np.interp(target_pct, pct_goc, obs_x_real)
                y_line = np.interp(target_pct, pct_goc, obs_y_real)
                z_line = np.interp(target_pct, pct_goc, obs_zs)
                
            matrix_x.append(x_line)
            matrix_y.append(y_line)
            matrix_z.append(z_line)
            
        matrix_x = np.array(matrix_x)
        matrix_y = np.array(matrix_y)
        matrix_z = np.array(matrix_z)

        if do_min > 1:
            mz_pd = pd.DataFrame(matrix_z)
            mz_pd = mz_pd.rolling(window=do_min, min_periods=1, center=True).mean()
            matrix_z = mz_pd.T.rolling(window=do_min, min_periods=1, center=True).mean().T.values

        z_scaled = matrix_z * he_so_z
        fig = go.Figure()

        surface_opts = dict(x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z)

        # 🎯 TIẾN TRÌNH XỬ LÝ DÁN ẢNH VỆ TINH CHUẨN GIS
        if kich_hoat_ve_tinh:
            # 1. Tính toán tâm hình học và kích thước vùng đo thực địa VN-2000
            x_min, x_max = matrix_x.min(), matrix_x.max()
            y_min, y_max = matrix_y.min(), matrix_y.max()
            x_center = (x_min + x_max) / 2.0
            y_center = (y_min + y_max) / 2.0
            
            width_m = x_max - x_min
            height_m = y_max - y_min
            
            # 2. Dịch tâm VN-2000 sang Lat/Lon WGS-84
            lat_c, lon_c = chuyen_vn2000_sang_wgs84(x_center, y_center, kinh_tuyen_truc=ktt)
            
            # 3. Tải ảnh tự động từ Google Maps
            img_satellite = tai_anh_ve_tinh_google(lat_c, lon_c, width_m, height_m, api_key=api_key)
            
            if img_satellite is not None:
                # Chuyển đổi ma trận ảnh thành dải màu RGB đồng điệu cho ma trận Surface
                img_resized = img_satellite.resize((num_samples, len(unique_lts)))
                grid_rgb = np.array(img_resized)
                
                # Hàm ánh xạ mảng màu RGB của Plotly dán đè lên mô hình lồi lõm
                surface_opts.update(
                    surfacecolor=grid_rgb[:,:,0], # Lấy kênh màu dẫn hướng
                    colorscale=[[i/255.0, f"rgb({i},{i},{i})"] for i in range(256)], # Đồng bộ kênh màu thực tế
                    showscale=False
                )
            else:
                surface_opts.update(colorscale='Earth', showscale=True)
        else:
            # Cấu hình màu sắc mặc định nếu không bật tính năng vệ tinh
            if che_do == "Đường đồng mức":
                surface_opts.update(colorscale='Viridis', contours_z=dict(show=True, usecolormap=False, color="rgb(0,0,0)", width=2, project=dict(z=True)))
            else:
                show_wf = True if che_do == "Lưới tam giác" else False
                surface_opts.update(colorscale='Earth', contours=dict(x=dict(show=show_wf, color="rgba(0,0,0,0.2)"), y=dict(show=show_wf, color="rgba(0,0,0,0.2)")))

        # Dệt bề mặt Surface đặc kín
        fig.add_trace(go.Surface(**surface_opts))

        # ĐƯỜNG TIM TUYẾN MÀU ĐỎ + NHÃN CỌC 3D
        df_tim_all = df_clean[df_clean['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
        if not df_tim_all.empty:
            nhan_hien_thi = df_tim_all.apply(lambda r: f"{r['Cọc']} (LT: {r['Lý trình']:.1f}m)", axis=1).values
            fig.add_trace(go.Scatter3d(
                x=df_tim_all['X_Real'].values, y=df_tim_all['Y_Real'].values, z=df_tim_all['Z'].values * he_so_z,
                mode='lines+markers+text',
                line=dict(color='red', width=4), marker=dict(size=4, color='yellow'),
                text=nhan_hien_thi, textposition="top center",
                textfont=dict(family="Arial, sans-serif", size=11, color="lightblue"),
                name='Tim đường'
            ))

        fig.update_layout(
            scene=dict(xaxis_title="X VN-2000 (m)", yaxis_title="Y VN-2000 (m)", zaxis_title="Cao độ Z (m)", aspectmode='data'),
            template="plotly_dark", margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi phân tích đồ họa không gian: {e}")
        return None