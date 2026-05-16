import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import plotly.graph_objects as go

def ve_ky_hieu_muc_nuoc_plotly(fig, x_pos, y_val, label, color):
    """Vẽ ký hiệu mực nước bằng các đường nét tương tác trên Plotly"""
    # Vẽ đường ngang mực nước kéo dài ngắn quanh vị trí đặt nhãn
    fig.add_trace(go.Scatter(
        x=[x_pos - 4, x_pos + 4],
        y=[y_val, y_val],
        mode="lines",
        line=dict(color=color, width=1.5),
        showlegend=False,
        hoverinfo="skip"
    ))
    # Tạo text ghi chú cao độ ngay phía trên đường mực nước
    fig.add_trace(go.Scatter(
        x=[x_pos],
        y=[y_val + 0.4],
        mode="text",
        text=[f"{label}<br>{y_val:.3f}m"],
        textposition="top center",
        textfont=dict(color=color, size=10),
        showlegend=False,
        hoverinfo="skip"
    ))

def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu bằng Plotly - Tự động zoom/pan và khóa tỷ lệ 1-1"""
    geo = res.get('geo_logic')
    if not geo:
        return None
        
    # --- 1. LẤY DỮ LIỆU ĐẦU VÀO VÀ THIẾT LẬP PHẠM VI ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    # Đồng bộ hóa thông số tim cầu động từ file 02
    x_center = geo.get('x_dinh', 150)
    l_cau_thuc = geo.get('L_cau', 120)
    
    # Khung nhìn tự động ôm sát chiều dài cầu + mở rộng 40m ra hai bên đường đầu cầu
    x_start_view = max(0, x_center - (l_cau_thuc / 2) - 40)
    x_limit_view = x_center + (l_cau_thuc / 2) + 40
    
    # Tạo dải 1000 điểm cách đều để nét vẽ mượt mà khi phóng to dầm cầu
    x = np.linspace(x_start_view, x_limit_view, 1000)

    # --- 2. LOGIC TÍNH TOÁN CAO ĐỘ ĐƯỜNG ĐỎ (PARABOL) ---
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
    
    # Tính toán kết cấu các lớp dầm từ thông số AI
    h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban_mat_cau = 0.18
    
    y_duong_do = y_mat
    y_dinh_dam = y_mat - h_ban_mat_cau
    y_day_dam = y_mat - h_ban_mat_cau - h_dam_ai

    # --- 3. KHỞI TẠO BIỂU ĐỒ TƯƠNG TÁC PLOTLY ---
    fig = go.Figure()

    # 3.1 Vẽ Cao độ đường tự nhiên trung bình (Nét đứt màu xanh lá)
    h_tn_tb = geo.get('h_tn_tb', 3.0)
    fig.add_trace(go.Scatter(
        x=x, y=np.full_like(x, h_tn_tb),
        name="Đường TN trung bình",
        line=dict(color='#27ae60', width=1.5, dash='dash')
    ))

    if is_duong_bo:
        # Nếu vượt đường bộ: Vẽ cao độ mặt đường bị vượt
        fig.add_trace(go.Scatter(
            x=x, y=np.full_like(x, h1),
            name="Mặt đường bị vượt",
            line=dict(color='#7f8c8d', width=2)
        ))
    else:
        # Nếu vượt sông: Bố trí các ký hiệu mực nước bao quanh khu vực tim cầu
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center - 30, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center - 10, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center + 10, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_center + 30, h98, "MNTN H98%", "orange")

    # 3.2 Vẽ các lớp cấu tạo trắc dọc cầu
    fig.add_trace(go.Scatter(x=x, y=y_duong_do, name="Mặt cầu (Đường đỏ)", line=dict(color='red', width=2.5)))
    fig.add_trace(go.Scatter(x=x, y=y_dinh_dam, name="Đỉnh dầm", line=dict(color='gray', width=1, dash='dot')))
    fig.add_trace(go.Scatter(x=x, y=y_day_dam, name="Đáy dầm thiết kế", line=dict(color='darkblue', width=2, dash='dashdot')))

    # 3.3 Vẽ sơ họa vị trí kết cấu Mố cầu (Mố Trái / Mố Phải)
    fig.add_trace(go.Scatter(
        x=[geo['x_mo_trai'], geo['x_mo_trai']], y=[h_tn_tb, geo['y_mo']],
        name="Vị trí Mố Trái", line=dict(color='brown', width=3, dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=[geo['x_mo_phai'], geo['x_mo_phai']], y=[h_tn_tb, geo['y_mo']],
        name="Vị trí Mố Phải", line=dict(color='brown', width=3, dash='dash')
    ))

    # --- 4. THIẾT LẬP KHÓA TỶ LỆ HÌNH HỌC 1-1 VÀ GIAO DIỆN ---
    fig.update_layout(
        title=dict(text=f"SƠ HỌA TRẮC DỌC TOÀN CẦU (L_cầu = {l_cau_thuc:.2f}m)", x=0.5),
        xaxis=dict(title="Khoảng cách dọc tuyến (m)", range=[x_start_view, x_limit_view], showgrid=True),
        yaxis=dict(
            title="Cao độ trắc dọc (m)",
            scaleanchor="x",  # KHÓA TRỤC Y THEO TRỤC X
            scaleratio=1,     # ĐẢM BẢO TỶ LỆ KÍCH THƯỚC THỰC TẾ 1-1 (Không bị bẹt hình)
            showgrid=True
        ),
        height=600,
        template="plotly_white",
        dragmode='pan',       # Bật mặc định công cụ Bàn tay để kéo trượt qua lại dễ dàng
        hovermode="x unified" # Hiển thị đồng thời cao độ của các lớp dầm khi di chuột qua
    )
    
    return fig

def ve_mat_cat_ngang(res_mcn):
    """Vẽ mặt cắt ngang cầu bằng Plotly - Hỗ trợ tương tác Zoom/Pan tỷ lệ thực 1-1"""
    bc = res_mcn.get('bc_cau', 12.0) # Lấy tổng bề rộng cầu, mặc định 12m nếu thiếu
    w_lan = res_mcn.get('w_lan', 3.5)
    w_lc = res_mcn.get('w_lc', 0.5)   # Bề rộng gờ lan can
    w_dpc = res_mcn.get('w_dpc', 0.0) # Bề rộng dải phân cách (nếu có)
    
    # --- 1. KHỞI TẠO BIỂU ĐỒ PLOTLY ---
    fig = go.Figure()

    # 1.1 Vẽ Bản mặt cầu (Hình khối chữ nhật từ -Bc/2 đến Bc/2, dày 0.25m làm mẫu)
    # Dùng tính năng vẽ hình khép kín (Filled Tunnels) để giả lập khối bê tông
    fig.add_trace(go.Scatter(
        x=[-bc/2, bc/2, bc/2, -bc/2, -bc/2],
        y=[0, 0, -0.25, -0.25, 0],
        fill="subsection" or "toself",
        fillcolor="#bdc3c7",
        line=dict(color="black", width=2),
        name="Bản mặt cầu",
        hoverinfo="skip"
    ))

    # 1.2 Vẽ các gờ lan can hai bên mặt cắt ngang
    # Gờ bên trái
    fig.add_trace(go.Scatter(
        x=[-bc/2, -bc/2 + w_lc, -bc/2 + w_lc, -bc/2, -bc/2],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        name="Gờ lan can trái", hoverinfo="skip"
    ))
    # Gờ bên phải
    fig.add_trace(go.Scatter(
        x=[bc/2 - w_lc, bc/2, bc/2, bc/2 - w_lc, bc/2 - w_lc],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        name="Gờ lan can phải", hoverinfo="skip"
    ))

    # 1.3 Vẽ vạch sơn phân làn minh họa (Đặt tại tim cầu x=0)
    fig.add_trace(go.Scatter(
        x=[0, 0], y=[0, 0.15],
        mode="lines",
        line=dict(color="yellow", width=3, dash="dash"),
        name="Vạch tim đường"
    ))

    # --- 2. THIẾT LẬP KHÓA TỶ LỆ KỸ THUẬT 1-1 VÀ GIAO DIỆN ---
    fig.update_layout(
        title=dict(text=f"MẶT CẮT NGANG CẦU ĐIỂN HÌNH (B_cầu = {bc}m)", x=0.5),
        xaxis=dict(
            title="Bề rộng cầu (m)", 
            range=[-bc/2 - 2, bc/2 + 2],
            showgrid=False,
            zeroline=True,
            zerolinecolor="gray"
        ),
        yaxis=dict(
            title="Chiều cao cấu tạo (m)",
            scaleanchor="x",  # <<< KHÓA TRỤC Y THEO TRỤC X
            scaleratio=1,     # <<< TỶ LỆ ĐÚNG 1-1: Bản mặt cầu và làn xe không bị bóp méo
            range=[-1, 2],
            showgrid=False
        ),
        height=400,
        template="plotly_white",
        dragmode='pan',       # Bật kéo trượt tự do
        showlegend=False
    )
    
    return fig