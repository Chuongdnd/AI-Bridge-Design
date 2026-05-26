import streamlit as st
import plotly.graph_objects as go

def tao_khoi_hop_3d(x_center, y_center, z_bottom, length_x, width_y, height_z, color, name):
    """
    Hàm hỗ trợ tạo khối hộp 3D đặc (Solid Box) dựa trên tâm và kích thước
    """
    dx, dy = length_x / 2, width_y / 2
    # Tọa độ 8 đỉnh của khối hộp
    x = [x_center-dx, x_center+dx, x_center+dx, x_center-dx, x_center-dx, x_center+dx, x_center+dx, x_center-dx]
    y = [y_center-dy, y_center-dy, y_center+dy, y_center+dy, y_center-dy, y_center-dy, y_center+dy, y_center+dy]
    z = [z_bottom, z_bottom, z_bottom, z_bottom, z_bottom+height_z, z_bottom+height_z, z_bottom+height_z, z_bottom+height_z]
    
    # Quy tắc nối 12 mặt tam giác (Faces) để tạo thành khối khép kín
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k, 
        color=color, opacity=0.9, name=name, 
        flatshading=True, hoverinfo="name"
    )

def ve_tru_cau_3d():
    st.markdown("### 🏗️ KHỞI TẠO MÔ HÌNH TRỤ CẦU 3D ĐỘC LẬP")
    
    # 1. KHU VỰC NGƯỜI DÙNG KHAI BÁO BIẾN KÍCH THƯỚC
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**1. Bệ trụ (Móng)**")
        l_be = st.number_input("Chiều dài bệ (X):", value=6.0, step=0.5)
        b_be = st.number_input("Chiều rộng bệ (Y):", value=4.0, step=0.5)
        h_be = st.number_input("Chiều cao bệ (Z):", value=1.5, step=0.1)
        
    with col2:
        st.write("**2. Thân trụ (Cột)**")
        l_than = st.number_input("Chiều dài thân (X):", value=3.0, step=0.5)
        b_than = st.number_input("Chiều rộng thân (Y):", value=1.5, step=0.5)
        h_than = st.number_input("Chiều cao thân (Z):", value=5.0, step=0.5)
        
    with col3:
        st.write("**3. Xà mũ trụ (Đỉnh)**")
        l_mu = st.number_input("Chiều dài xà mũ (X):", value=8.0, step=0.5)
        b_mu = st.number_input("Chiều rộng xà mũ (Y):", value=2.0, step=0.5)
        h_mu = st.number_input("Chiều cao xà mũ (Z):", value=1.2, step=0.1)

    # 2. TOÁN HỌC XẾP CHỒNG CÁC KHỐI THEO TRỤC Z
    fig = go.Figure()
    
    # Vẽ Bệ trụ (Nằm sát đất, Z bắt đầu từ 0)
    khoi_be = tao_khoi_hop_3d(0, 0, 0, l_be, b_be, h_be, color='#808080', name="Bệ trụ")
    fig.add_trace(khoi_be)
    
    # Vẽ Thân trụ (Nằm đè lên Bệ trụ, Z bắt đầu từ h_be)
    khoi_than = tao_khoi_hop_3d(0, 0, h_be, l_than, b_than, h_than, color='#A9A9A9', name="Thân trụ")
    fig.add_trace(khoi_than)
    
    # Vẽ Xà mũ (Nằm đè lên Thân trụ, Z bắt đầu từ h_be + h_than)
    khoi_mu = tao_khoi_hop_3d(0, 0, h_be + h_than, l_mu, b_mu, h_mu, color='#696969', name="Xà mũ")
    fig.add_trace(khoi_mu)

    # 3. CẤU HÌNH GIAO DIỆN HIỂN THỊ
    fig.update_layout(
        scene=dict(
            xaxis_title="Phương ngang cầu (X)",
            yaxis_title="Phương dọc cầu (Y)",
            zaxis_title="Cao độ (Z)",
            aspectmode='data' # Ép tỷ lệ 1:1:1 để trụ không bị méo
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Để test độc lập, bạn chỉ cần gọi hàm này ra:
if __name__ == "__main__":
    ve_tru_cau_3d()