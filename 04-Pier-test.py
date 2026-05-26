import plotly.graph_objects as go

def tao_khoi_hop_3d(x_center, y_center, z_bottom, length_x, width_y, height_z, color, name):
    """Hàm toán học sinh tọa độ 8 đỉnh để bọc lưới Mesh3d thành khối hộp đặc"""
    dx, dy = length_x / 2, width_y / 2
    x = [x_center-dx, x_center+dx, x_center+dx, x_center-dx, x_center-dx, x_center+dx, x_center+dx, x_center-dx]
    y = [y_center-dy, y_center-dy, y_center+dy, y_center+dy, y_center-dy, y_center-dy, y_center+dy, y_center+dy]
    z = [z_bottom, z_bottom, z_bottom, z_bottom, z_bottom+height_z, z_bottom+height_z, z_bottom+height_z, z_bottom+height_z]
    
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k, 
        color=color, opacity=0.9, name=name, 
        flatshading=True, hoverinfo="name"
    )

# ✨ TÊN HÀM VÀ 9 THAM SỐ ĐÃ KHỚP KHÍT 100% VỚI FILE INTERFACE CỦA BẠN
def ve_tru_cau_3d(l_be, b_be, h_be, l_than, b_than, h_than, l_mu, b_mu, h_mu):
    fig = go.Figure()
    
    # 1. Vẽ Bệ trụ (Z đáy = 0)
    fig.add_trace(tao_khoi_hop_3d(0, 0, 0, l_be, b_be, h_be, '#808080', "Bệ trụ"))
    
    # 2. Vẽ Thân trụ (Z đáy = h_be)
    fig.add_trace(tao_khoi_hop_3d(0, 0, h_be, l_than, b_than, h_than, '#A9A9A9', "Thân trụ"))
    
    # 3. Vẽ Xà mũ (Z đáy = h_be + h_than)
    fig.add_trace(tao_khoi_hop_3d(0, 0, h_be + h_than, l_mu, b_mu, h_mu, '#696969', "Xà mũ"))
    
    fig.update_layout(
        scene=dict(
            xaxis_title="Phương ngang (X)", 
            yaxis_title="Phương dọc (Y)", 
            zaxis_title="Cao độ (Z)", 
            aspectmode='data' # Ép tỷ lệ 1:1:1 để trụ không bị bóp méo
        ),
        margin=dict(l=0, r=0, b=0, t=30), height=650, 
        template="plotly_dark", paper_bgcolor='#0e1117'
    )
    return fig