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
    
    # 2. Vẽ đường gạch ngang chính 
    ax.plot([x_pos - 3, x_pos + 3], [y_val, y_val], color=color, lw=1.2, zorder=4)
    
    # 3. Vẽ 3 gạch nhỏ bên dưới (Ký hiệu sóng nước chuẩn kỹ thuật)
    # Các nét gạch ngắn dần và cách nhau một khoảng nhỏ
    dash_widths = [2.0, 1.2, 0.5] # Độ dài các nét gạch
    for i, w in enumerate(dash_widths):
        y_dash = y_val - (i + 1) * 0.25  
        ax.plot([x_pos - w/2, x_pos + w/2], [y_dash, y_dash], color=color, lw=0.8)

    # 4. Ghi chú Text cao độ
    ax.text(x_pos, y_val + d_y + 0.3, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontsize=9, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0))
def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu - Tự động thích ứng Vượt Sông hoặc Đường Bộ"""
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # 1. Lấy dữ liệu
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    # Lấy nhãn để phân biệt loại cầu
    label_cau = res.get('label', "")
    is_duong_bo = "Cầu vượt" in label_cau # Kiểm tra nếu là cầu vượt đường bộ

    # 2. VẼ ĐỊA HÌNH / MẶT ĐƯỜNG BỊ VƯỢT
    x = np.linspace(0, 120, 200)
    if is_duong_bo:
        # Nếu là đường bộ: Vẽ đường thẳng nằm ngang (mặt đường bên dưới)
        y_nen = np.full_like(x, h1) 
        ax.plot(x, y_nen, color='#7f8c8d', ls='-', lw=2, label="Mặt đường bị vượt")
        # Tô màu xám mô phỏng đường nhựa/bê tông
        ax.fill_between(x, h1 - 5, h1, color='#ecf0f1', alpha=0.5)
    else:
        # Nếu là vượt sông: Vẽ lòng sông trũng như cũ
        y_tn = h1 - 2.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000))
        ax.plot(x, y_tn, color='#27ae60', ls='--', lw=1.5)
        ax.fill_between(x, h1 - 5, y_tn, color='#f1e7d0', alpha=0.5)

    # 3. VẼ THỦY VĂN (Chỉ vẽ nếu KHÔNG PHẢI đường bộ)
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, 15, res.get('MNCN', 0), "MNCN", "red")
        ve_ky_hieu_muc_nuoc(ax, 45, res.get('MNTT', 0), "MNTT", "blue")
        ve_ky_hieu_muc_nuoc(ax, 75, res.get('MNTC', 0), "MNTC", "green")
        ve_ky_hieu_muc_nuoc(ax, 105, res.get('MNTN', 0), "MNTN", "orange")
    else:
        # Nếu là đường bộ, chỉ vẽ một ký hiệu cao độ mặt đường tại vị trí biên
        ax.text(5, h1 + 0.2, f"Cao độ mặt đường: {h1:.3f}m", color='#34495e', fontsize=9)

    # 4. VẼ KẾT CẤU CẦU (ĐƯỜNG ĐỎ) - Giữ nguyên
    h_mat_cau = h_dam + 2.0
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=3)
    ax.plot([0, 120], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5)
    ax.text(2, h_mat_cau + 0.3, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold')

    # 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM
    if B > 0:
        # Khung tĩnh không nét đứt Magenta
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2)
        ax.add_patch(rect)
        
        # DIM Bề rộng B (Dời lên cao h5 + 2.5)
        y_dim_b = h5 + 2.5
        ax.annotate('', xy=(60+B/2, y_dim_b), xytext=(60-B/2, y_dim_b),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60, y_dim_b + 0.2, f"B = {B}m", ha='center', fontweight='bold', bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))

        # DIM Chiều cao H
        ax.annotate('', xy=(60+B/2+3, h5+H_tk), xytext=(60+B/2+3, h5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60+B/2+3.5, h5+H_tk/2, f"H = {H_tk}m", rotation=90, va='center', fontweight='bold', bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    ax.set_ylim(h1 - 4, h_mat_cau + 5)
    ax.axis('off')
    ax.set_title(label_cau.upper(), fontsize=14, fontweight='bold')
    
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