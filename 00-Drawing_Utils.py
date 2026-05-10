import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    """
    Vẽ tam giác ngược và các nét gạch sóng nước chuẩn kỹ thuật
    """
    d_x, d_y = 1.2, 0.8
    
    # 1. Vẽ hình tam giác ngược (vị trí chạm đỉnh vào mực nước)
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)], 
        facecolor='none', edgecolor=color, lw=1.2, zorder=5)
    ax.add_patch(triangle)
    
    # 2. Vẽ đường gạch ngang chính (Mặt nước)
    ax.plot([x_pos - 3, x_pos + 3], [y_val, y_val], color=color, lw=1.2, zorder=4)
    
    # 3. Vẽ 3 gạch nhỏ bên dưới (Ký hiệu sóng nước chuẩn kỹ thuật)
    # Các nét gạch ngắn dần và cách nhau một khoảng nhỏ
    dash_widths = [2.0, 1.2, 0.5] # Độ dài các nét gạch
    for i, w in enumerate(dash_widths):
        y_dash = y_val - (i + 1) * 0.25  # Khoảng cách xuống dưới
        ax.plot([x_pos - w/2, x_pos + w/2], [y_dash, y_dash], color=color, lw=0.8)

    # 4. Ghi chú Text cao độ
    ax.text(x_pos, y_val + d_y + 0.3, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontsize=9, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0))
def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu với đầy đủ DIM tĩnh không"""
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # --- 1. LẤY DỮ LIỆU ĐÃ ĐỒNG BỘ KEY ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    
    # Xử lý an toàn cho B
    if isinstance(B, str): B = 0

    # --- 2. VẼ ĐỊA HÌNH VÀ TỰ NHIÊN ---
    x = np.linspace(0, 120, 200)
    # Hàm mô phỏng lòng sông trũng
    y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000))
    ax.plot(x, y_tn, color='#27ae60', ls='--', lw=1.5)
    # Tô màu đất
    ax.fill_between(x, min(h98, y_tn.min()) - 5, y_tn, color='#f1e7d0', alpha=0.5)

    # --- 3. VẼ KÝ HIỆU MỰC NƯỚC (FIX LỖI TRÙNG LẤN) ---
    # Phân bổ lại vị trí x để các ký hiệu không đè lên nhau
    ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
    ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT H5%", "blue")
    ve_ky_hieu_muc_nuoc(ax, 75, h10, "MNTC H10%", "green")
    ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "orange")

    # --- 4. VẼ KẾT CẤU CẦU ---
    h_mat_cau = h_dam + 2.0  # Giả sử chiều dày kết cấu nhịp là 2m
    # Đường đỏ (mặt cầu)
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=3, label="Mặt cầu")
    # Cao độ đáy dầm
    ax.plot([0, 120], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5)
    # Chú thích
    ax.text(2, h_mat_cau + 0.3, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold', fontsize=10)
    ax.text(2, h_dam - 0.8, f"CAO ĐỘ ĐÁY DẦM: {h_dam:.3f}m", color='#34495e', fontsize=9)

    # --- 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM (YÊU CẦU MỚI) ---
    if B > 0:
        # A. Vẽ khung tĩnh không Magenta nét đứt
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, 
                                 fill=False, edgecolor='magenta', ls='--', lw=2, zorder=3)
        ax.add_patch(rect)
        ax.text(60, h5 + 0.3, "H5", ha='center', va='bottom', color='magenta', fontweight='bold')

        # B. BỔ SUNG NÉT DIM (MŨI TÊN KÍCH THƯỚC)
        
        # --- DIM Bề rộng tĩnh không B ---
        # Đường gióng và mũi tên B (xytext đến xy)
        ax.annotate('', 
                    xy=(60 + B/2, h5 + 1.0),     # Điểm cuối mũi tên phải
                    xytext=(60 - B/2, h5 + 1.0), # Điểm đầu mũi tên trái
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        # Text giá trị B ở giữa
        ax.text(60, h5 + 1.2, f"B = {B}m", 
                ha='center', va='bottom', color='black', fontweight='bold', fontsize=10,
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # --- DIM Chiều cao tĩnh không H ---
        # Đường gióng và mũi tên H ( xytext đến xy)
        ax.annotate('', 
                    xy=(60 + B/2 + 3, h5 + H_tk), # Điểm trên của mũi tên
                    xytext=(60 + B/2 + 3, h5),    # Điểm dưới của mũi tên
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        # Text giá trị H bên cạnh
        ax.text(60 + B/2 + 3.5, h5 + H_tk/2, f"H = {H_tk}m", 
                ha='left', va='center', color='black', fontweight='bold', fontsize=10,
                rotation=90, # Xoay dọc text
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    ax.set_ylim(min(h98, y_tn.min(), h5) - 5, h_mat_cau + 5)
    ax.axis('off')
    ax.set_title("SƠ HỌA TRẮC DỌC CẦU", fontsize=16, fontweight='bold', pad=20)
    
    return fig

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