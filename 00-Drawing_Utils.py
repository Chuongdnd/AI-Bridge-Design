import numpy as np
import plotly.graph_objects as go

def ve_ky_hieu_muc_nuoc_plotly(fig, x_pos, y_val, label, color):
    """Vẽ ký hiệu mực nước tương tác bằng nét vẽ của Plotly"""
    # Vẽ đường ngang mực nước (Dài 8m vây quanh vị trí đặt)
    fig.add_trace(go.Scatter(
        x=[x_pos - 4, x_pos + 4],
        y=[y_val, y_val],
        mode="lines",
        line=dict(color=color, width=1.5),
        showlegend=False,
        hoverinfo="skip"
    ))
    # Tạo nhãn chữ hiển thị thông số cao độ ngay phía trên nét gạch
    fig.add_trace(go.Scatter(
        x=[x_pos],
        y=[y_val + 0.3],
        mode="text",
        text=[f"{label}<br>{y_val:.3f}m"],
        textposition="top center",
        textfont=dict(color=color, size=9, family="Arial Black"),
        showlegend=False,
        hoverinfo="skip"
    ))

def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu bằng Plotly - Hỗ trợ tương tác Zoom/Pan và tỷ lệ 1-1"""
    geo = res.get('geo_logic')
    if not geo:
        return None
        
    # --- 1. LẤY DỮ LIỆU ĐẦU VÀO VÀ THIẾT LẬP KHUNG NHÌN ĐỘNG ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    # Thiết lập tim cầu và dải phạm vi động từ file 02 hình học
    x_center = geo.get('x_dinh', 150)
    l_cau_thuc = geo.get('L_cau', 120)
    
    # Khung nhìn tự động ôm sát chiều dài cầu và mở rộng 50m ra hai bên đường đầu cầu
    x_start_view = max(0, x_center - (l_cau_thuc / 2) - 50)
    x_limit_view = x_center + (l_cau_thuc / 2) + 50
    
    # Chia 1000 điểm để các đường cong đứng Parabol đạt độ mịn tối đa khi zoom sâu
    x = np.linspace(x_start_view, x_limit_view, 1000)

    # --- 2. TÍNH TOÁN CAO ĐỘ ĐƯỜNG ĐỎ VÀ CÁC LỚP KẾT CẤU ---
    y_mat = []
    for xi in x:
        if xi < geo['x_t1']:
            yi = geo['y_t'] - geo['i_val'] * (geo['x_t1'] - xi)
        elif xi > geo['x_t2']:
            yi = geo['y_t'] - geo['i_val'] * (xi - geo['x_t2'])
        else:
            yi = geo['y_dinh'] - (xi - x_center)**2 / (2 * geo['R'])
        y_mat.append(yi)
    y_mat = np.array(y_mat)
    
    # Chiều cao dầm từ kết quả AI và bản mặt cầu cố định
    h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban_mat_cau = 0.18
    
    y_duong_do = y_mat
    y_dinh_dam = y_mat - h_ban_mat_cau
    y_day_dam = y_mat - h_ban_mat_cau - h_dam_ai

    # --- 3. KHỞI TẠO BIỂU ĐỒ HOÀN TOÀN BẰNG PLOTLY ---
    fig = go.Figure()

    # 3.1 Đường tự nhiên trung bình (Nét đứt màu xanh lá cây)
    h_tn_tb = geo.get('h_tn_tb', 3.0)
    fig.add_trace(go.Scatter(
        x=x, y=np.full_like(x, h_tn_tb),
        name="Đường TN trung bình",
        line=dict(color='#27ae60', width=1.5, dash='dash')
    ))

    # 3.2 Nhận diện Vượt Sông hoặc Vượt Đường
    if is_duong_bo:
        # Mặt đường bị vượt (Màu xám đại diện cho đường bộ phía dưới)
        fig.add_trace(go.Scatter(
            x=x, y=np.full_like(x, h1),
            name="Mặt đường bị vượt",
            line=dict(color='#7f8c8d', width=2.5)
        ))
    else:
        # Sắp xếp các ký hiệu mực nước đối xứng vây quanh khu vực tim cầu
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center - 45, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center - 15, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center + 15, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center + 45, h98, "MNTN H98%", "orange")

    # 3.3 Bản mặt cầu, đỉnh dầm, đáy dầm thiết kế
    fig.add_trace(go.Scatter(x=x, y=y_duong_do, name="Mặt cầu (Đường đỏ)", line=dict(color='red', width=3)))
    fig.add_trace(go.Scatter(x=x, y=y_dinh_dam, name="Đỉnh dầm", line=dict(color='gray', width=1, dash='dot'), showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=y_day_dam, name="Đáy dầm thiết kế", line=dict(color='darkblue', width=2, dash='dashdot')))

    # 3.4 Sơ họa kết cấu mố cầu hai bên đầu nhịp (Đường thẳng đứng màu nâu)
    fig.add_trace(go.Scatter(
        x=[geo['x_mo_trai'], geo['x_mo_trai']], y=[h_tn_tb, geo['y_mo']],
        name="Mố Trái", line=dict(color='brown', width=3, dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=[geo['x_mo_phai'], geo['x_mo_phai']], y=[h_tn_tb, geo['y_mo']],
        name="Mố Phải", line=dict(color='brown', width=3, dash='dash')
    ))

    # 3.5 Tải khung Khổ thông thuyền / Khung tĩnh không kỹ thuật (Khối màu Magenta)
    if B > 0 and H_tk > 0:
        # Tính toán tọa độ cao độ đặt khung thông thuyền (Lấy từ mực nước thiết kế h5 hoặc h1 tuỳ loại cầu)
        y_base_tk = h1 if is_duong_bo else h5
        fig.add_shape(
            type="rect",
            x0=x_center - B/2, y0=y_base_tk,
            x1=x_center + B/2, y1=y_base_tk + H_tk,
            line=dict(color="magenta", width=1.5),
            fillcolor="rgba(255, 0, 255, 0.05)",
            name="Khung tĩnh không"
        )
        # Bổ sung nhãn Text ghi rõ kích thước tĩnh không ngay tâm khung hình
        fig.add_trace(go.Scatter(
            x=[x_center], y=[y_base_tk + H_tk/2],
            mode="text",
            text=[f"TĨNH KHÔNG KỸ THUẬT<br>B x H = {B}m x {H_tk}m"],
            textposition="middle center",
            textfont=dict(color="magenta", size=10, family="Arial"),
            showlegend=False,
            hoverinfo="skip"
        ))

    # --- 4. THIẾT LẬP KHÓA CỨNG TỶ LỆ HÌNH HỌC 1-1 VÀ GIAO DIỆN ---
    fig.update_layout(
        title=dict(text=f"SƠ HỌA TRẮC DỌC TOÀN CẦU ĐỘNG (L_cầu = {l_cau_thuc:.2f}m)", x=0.5, font=dict(size=14, color="black")),
        xaxis=dict(title="Khoảng cách dọc tuyến (m)", range=[x_start_view, x_limit_view], showgrid=True, gridcolor="#f0f0f0"),
        yaxis=dict(
            title="Cao độ trắc dọc (m)",
            scaleanchor="x",  # <<< QUAN TRỌNG NHẤT: Khóa trục Y theo trục X
            scaleratio=1,     # <<< TỶ LỆ THỰC TẾ 1-1: Bản vẽ kỹ thuật chuẩn xác không bị bẹt
            showgrid=True,
            gridcolor="#f0f0f0"
        ),
        height=550,
        template="plotly_white",
        dragmode='pan',       # Đặt mặc định là công cụ Bàn tay để kéo trượt trái/phải tự do
        hovermode="x unified" # Hiển thị đồng bộ cao độ toàn bộ các cấu kiện khi rê chuột qua tuyến
    )
    
    return fig

def ve_mat_cat_ngang(res_mcn):
    """Vẽ mặt cắt ngang cầu điển hình bằng Plotly - Khóa tỷ lệ 1-1"""
    bc = res_mcn.get('bc_cau', 12.0)
    w_lc = res_mcn.get('w_lc', 0.5)   # Mặc định bề rộng gờ lan can
    
    fig = go.Figure()

    # Vẽ Khối bản mặt cầu bê tông (Hình hộp chữ nhật dày 25cm)
    fig.add_trace(go.Scatter(
        x=[-bc/2, bc/2, bc/2, -bc/2, -bc/2],
        y=[0, 0, -0.25, -0.25, 0],
        fill="toself",
        fillcolor="#bdc3c7",
        line=dict(color="black", width=2),
        name="Bản mặt cầu",
        hoverinfo="skip"
    ))

    # Vẽ gờ chắn lan can bên trái
    fig.add_trace(go.Scatter(
        x=[-bc/2, -bc/2 + w_lc, -bc/2 + w_lc, -bc/2, -bc/2],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        showlegend=False, hoverinfo="skip"
    ))
    
    # Vẽ gờ chắn lan can bên phải
    fig.add_trace(go.Scatter(
        x=[bc/2 - w_lc, bc/2, bc/2, bc/2 - w_lc, bc/2 - w_lc],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        showlegend=False, hoverinfo="skip"
    ))

    # Khóa trục tỷ lệ 1-1 cho mặt cắt ngang
    fig.update_layout(
        title=dict(text=f"MẶT CẮT NGANG CẦU ĐIỂN HÌNH (B_cầu = {bc}m)", x=0.5),
        xaxis=dict(title="Bề rộng cầu (m)", range=[-bc/2 - 2, bc/2 + 2], showgrid=False, zeroline=True),
        yaxis=dict(
            title="Chiều cao cấu tạo (m)",
            scaleanchor="x",
            scaleratio=1, # Tỉ lệ 1-1 thực thụ
            range=[-1, 2],
            showgrid=False
        ),
        height=380,
        template="plotly_white",
        dragmode='pan'
    )
    
    return fig