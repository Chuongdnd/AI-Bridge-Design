import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    """Vẽ tam giác ngược và các nét gạch sóng nước chuẩn kỹ thuật"""
    d_x, d_y = 1.2, 0.8
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)], 
        facecolor='none', edgecolor=color, lw=1.2, zorder=5)
    ax.add_patch(triangle)
    ax.plot([x_pos - 3, x_pos + 3], [y_val, y_val], color=color, lw=1.2, zorder=4)
    dash_widths = [2.0, 1.2, 0.5] 
    for i, w in enumerate(dash_widths):
        y_dash = y_val - (i + 1) * 0.25  
        ax.plot([x_pos - w/2, x_pos + w/2], [y_dash, y_dash], color=color, lw=0.8)
    ax.text(x_pos, y_val + d_y + 0.3, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontsize=9, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0))

def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu - Tự động nhận diện Vượt sông hoặc Vượt đường"""
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # --- 1. LẤY DỮ LIỆU ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")

    # Kiểm tra loại cầu: Nếu là vượt đường bộ, các mực nước thường bằng nhau hoặc label chứa chữ 'Vượt'
    is_duong_bo = (h1 == h5 == h10 == h98) or ("Vượt đường" in label_res)
    
    if isinstance(B, str): B = 0
    x = np.linspace(0, 120, 200)

    # --- 2. VẼ ĐỊA HÌNH ---
    if is_duong_bo:
        # Nếu là đường bộ: Chỉ vẽ vùng không gian bao quanh B
        # Tạo lề trái/phải mỗi bên bằng 20% của B
        le = B * 0.2 if B > 0 else 5
        x_min = 60 - B/2 - le
        x_max = 60 + B/2 + le
        
        ax.set_xlim(x_min, x_max)
        # Cập nhật lại đường Đỏ và Đáy dầm cho vừa khít khung nhìn mới
        ax.plot([x_min, x_max], [h_mat_cau, h_mat_cau], color='red', lw=3)
        ax.plot([x_min, x_max], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5)
    else:
        # Nếu là vượt sông: Giữ nguyên khung cảnh 120m để thấy lòng sông
        ax.set_xlim(-5, 125)

    # --- 3. VẼ KÝ HIỆU MỰC NƯỚC (Chỉ vẽ khi vượt sông) ---
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc(ax, 75, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "orange")

    # --- 4. VẼ KẾT CẤU CẦU ---
    h_mat_cau = h_dam + 2.0 
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=3)
    ax.plot([0, 120], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5)
    ax.text(2, h_mat_cau + 0.3, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold', fontsize=10)
    ax.text(2, h_dam - 0.8, f"CAO ĐỘ ĐÁY DẦM: {h_dam:.3f}m", color='#34495e', fontsize=9)

    # --- 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM ---
    if B > 0:
        # Thiết lập vùng vẽ bao quanh khung tĩnh không để nhìn đúng tỷ lệ
        # Chúng ta sẽ cho lề hai bên rộng thêm khoảng 20% của B để hình đẹp
        margin = B * 0.2
        x_min_view = 60 - (B/2 + margin)
        x_max_view = 60 + (B/2 + margin)
        
        # Tọa độ thực của khung
        x_start = 60 - B/2
        x_end = 60 + B/2
        
        # A. Vẽ khung tĩnh không Magenta nét đứt
        rect = patches.Rectangle((x_start, h5), B, H_tk, 
                                 fill=False, edgecolor='magenta', ls='--', lw=2.5, zorder=10)
        ax.add_patch(rect)

        # B. VẼ NÉT DIM BỀ RỘNG B (Nằm ngay trên nóc khung)
        y_dim_b = h5 + H_tk + 0.5 
        ax.annotate('', 
                    xy=(x_end, y_dim_b),     
                    xytext=(x_start, y_dim_b), 
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5, mutation_scale=15))
        
        ax.text(60, y_dim_b + 0.1, f"B = {B}m", 
                ha='center', va='bottom', color='black', fontweight='bold', fontsize=12)

        # C. VẼ NÉT DIM CHIỀU CAO H (Nằm sát cạnh phải khung)
        x_dim_h = x_end + (margin * 0.3) # Đặt nét DIM trong khoảng lề
        ax.annotate('', 
                    xy=(x_dim_h, h5 + H_tk), 
                    xytext=(x_dim_h, h5),    
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5, mutation_scale=15))
        
        ax.text(x_dim_h + 0.2, h5 + H_tk/2, f"H = {H_tk}m", 
                ha='left', va='center', color='black', fontweight='bold', fontsize=11, rotation=90)

        # --- QUAN TRỌNG: THIẾT LẬP LẠI TRỤC TỌA ĐỘ THEO B ---
        ax.set_xlim(x_min_view, x_max_view)
    else:
        # Nếu không có B (hoặc vượt sông mặc định), dùng khung nhìn cũ
        ax.set_xlim(-5, 125)

    # Cập nhật giới hạn trục Y cho cân đối
    ax.set_ylim(h1 - 2, h_mat_cau + 3)
    ax.axis('off')

def ve_mat_cat_ngang(res_mcn):
    fig, ax = plt.subplots(figsize=(10, 5))
    bc = res_mcn.get('bc_cau', 0)
    w_lan = res_mcn.get('w_lan', 3.5)
    # Vẽ bản mặt cầu đơn giản
    ax.add_patch(patches.Rectangle((-bc/2, 0), bc, 0.5, color='#bdc3c7', ec='black'))
    # Vẽ vạch sơn phân làn (minh họa)
    ax.plot([0, 0], [0.5, 0.7], color='black', lw=2) 
    
    ax.set_xlim(-bc/2 - 2, bc/2 + 2)
    ax.set_ylim(-1, 2)
    ax.set_title(f"MẶT CẮT NGANG CẦU (Bc = {bc}m)")
    ax.axis('off')
    return fig