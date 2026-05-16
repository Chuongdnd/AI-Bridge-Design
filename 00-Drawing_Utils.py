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
    """Vẽ sơ họa trắc dọc cầu bằng Plotly - Gốc tọa độ (0,0) đặt tại TIM TĨNH KHÔNG"""
    geo = res.get('geo_logic')
    if not geo:
        return None
        
    # --- 1. LẤY DỮ LIỆU ĐẦU VÀO VÀ THIẾT LẬP MỐC DỜI TỌA ĐỘ ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    # CHỌN MỐC CAO ĐỘ ĐÁY TĨNH KHÔNG LÀM GỐC Y = 0
    # Nếu vượt sông lấy MNTT (h5), vượt đường bộ lấy Mặt đường bị vượt (h1)
    y_base_goc = h1 if is_duong_bo else h5
    
    # TIM CẦU MẶC ĐỊNH VỀ X = 0
    x_center = 0 
    l_cau_thuc = geo.get('L_cau', 120)
    
    # Tính toán lại vị trí mố trái và mố phải đối xứng qua tim 0
    x_mo_trai_moi = -l_cau_thuc / 2
    x_mo_phai_moi = l_cau_thuc / 2
    
    # Thiết lập phạm vi vẽ dải tuyến (Quét rộng ra 2 bên mố 50m)
    x_start_view = x_mo_trai_moi - 50
    x_limit_view = x_mo_phai_moi + 50
    x = np.linspace(x_start_view, x_limit_view, 1500)

    # --- 2. TÍNH TOÁN CAO ĐỘ ĐƯỜNG ĐỎ (ĐÃ TRỪ ĐI Y_BASE_GOC) ---
    # Lấy các thông số hình học gốc từ file 02 để tính toán hình học tương đối
    x_dinh_cu = geo.get('x_dinh', 150)
    
    y_mat = []
    for xi in x:
        # Chuyển đổi ngược tọa độ xi mới về hệ tọa độ cũ để tận dụng logic hình học cũ của bạn
        xi_cu = xi + x_dinh_cu 
        
        if xi_cu < geo['x_t1']:
            yi_cu = geo['y_t'] - geo['i_val'] * (geo['x_t1'] - xi_cu)
        elif xi_cu > geo['x_t2']:
            yi_cu = geo['y_t'] - geo['i_val'] * (xi_cu - geo['x_t2'])
        else:
            yi_cu = geo['y_dinh'] - (xi_cu - x_dinh_cu)**2 / (2 * geo['R'])
            
        # DỜI TRỤC Y: Trừ đi cao độ mốc để đưa về gốc 0
        y_mat.append(yi_cu - y_base_goc)
        
    y_mat = np.array(y_mat)
    
    h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban_mat_cau = 0.18
    
    y_duong_do = y_mat
    y_dinh_dam = y_mat - h_ban_mat_cau
    y_day_dam = y_mat - h_ban_mat_cau - h_dam_ai

    # --- 3. KHỞI TẠO BIỂU ĐỒ PLOTLY ---
    fig = go.Figure()

    # 3.1 Đường tự nhiên trung bình (Đã dời trục Y)
    h_tn_tb_moi = geo.get('h_tn_tb', 3.0) - y_base_goc
    fig.add_trace(go.Scatter(
        x=x, y=np.full_like(x, h_tn_tb_moi),
        name="Đường TN trung bình",
        line=dict(color='#27ae60', width=1.5, dash='dash')
    ))

    # 3.2 Vẽ các mực nước / Mặt đường bị vượt (Đã dời trục Y)
    if is_duong_bo:
        # Mặt đường bị vượt chính là đường thẳng Y = 0
        fig.add_trace(go.Scatter(
            x=x, y=np.full_like(x, 0),
            name="Mặt đường bị vượt (Y=0)",
            line=dict(color='#7f8c8d', width=2.5)
        ))
    else:
        # Bố trí các mực nước đối xứng qua tim 0, cao độ tương đối so với h5 (Y_goc)
        ve_ky_hieu_muc_nuoc_plotly(fig, -40, h1 - y_base_goc, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, -15, h5 - y_base_goc, "MNTT H5% (Y=0)", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, 15, h10 - y_base_goc, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, 40, h98 - y_base_goc, "MNTN H98%", "orange")

    # 3.3 Vẽ Bản mặt cầu, Đỉnh dầm, Đáy dầm
    fig.add_trace(go.Scatter(x=x, y=y_duong_do, name="Mặt cầu (Đường đỏ)", line=dict(color='red', width=3)))
    fig.add_trace(go.Scatter(x=x, y=y_day_dam, name="Đáy dầm thiết kế", line=dict(color='darkblue', width=2, dash='dashdot')))

    # 3.4 Vẽ vị trí Mố cầu đối xứng
    y_mo_moi = geo['y_mo'] - y_base_goc
    fig.add_trace(go.Scatter(
        x=[x_mo_trai_moi, x_mo_trai_moi], y=[h_tn_tb_moi, y_mo_moi],
        name="Mố Trái", line=dict(color='brown', width=3, dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=[x_mo_phai_moi, x_mo_phai_moi], y=[h_tn_tb_moi, y_mo_moi],
        name="Mố Phải", line=dict(color='brown', width=3, dash='dash')
    ))

    # 3.5 VẼ KHUNG TĨNH KHÔNG GỐC TOÀN CỤC (0,0)
    if B > 0 and H_tk > 0:
        # Lúc này x0, y0 xuất phát chính xác từ tâm hoành độ và tung độ gốc
        fig.add_shape(
            type="rect",
            x0=-B/2, y0=0,
            x1=B/2, y1=H_tk,
            line=dict(color="magenta", width=2),
            fillcolor="rgba(255, 0, 255, 0.08)"
        )
        fig.add_trace(go.Scatter(
            x=[0], y=[H_tk / 2],
            mode="text",
            text=[f"TĨNH KHÔNG KỸ THUẬT<br>B x H = {B}m x {H_tk}m<br>Tâm đặt tại (0,0)"],
            textposition="middle center",
            textfont=dict(color="magenta", size=10, family="Arial Black"),
            showlegend=False,
            hoverinfo="skip"
        ))

    # --- 4. THIẾT LẬP LAYOUT KHUNG NHÌN ĐỐI XỨNG ---
    fig.update_layout(
        title=dict(text=f"SƠ HỌA TRẮC DỌC CẦU VỚI GỐC TOẠ ĐỘ TIM TĨNH KHÔNG (0,0)", x=0.5),
        xaxis=dict(title="Khoảng cách tính từ Tim cầu (m)", range=[x_start_view, x_limit_view], showgrid=True),
        yaxis=dict(
            title="Cao độ tương đối (m)",
            scaleanchor="x",  
            scaleratio=1,     
            showgrid=True,
            zeroline=True,         # Bật đường chuẩn vị trí 0
            zerolinecolor="black", # Tô đậm trục tọa độ X gốc
            zerolinewidth=1.5
        ),
        height=550,
        template="plotly_white",
        dragmode='pan',       
        hovermode="x unified" 
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