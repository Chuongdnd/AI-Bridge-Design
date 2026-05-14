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
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    if isinstance(B, str): B = 0
    x = np.linspace(0, 120, 200)

  # --- 2. VẼ ĐỊA HÌNH VÀ ĐƯỜNG TỰ NHIÊN TRUNG BÌNH ---
    h_tn_tb = res.get('H_TN_TB', 0.0)

    # A. VẼ ĐƯỜNG TỰ NHIÊN TRUNG BÌNH (Chung cho cả 2 loại cầu)
    # Vẽ đường nét đứt màu xanh lá cây xuyên suốt trắc dọc
    ax.plot([0, 120], [h_tn_tb, h_tn_tb], color='#27ae60', ls='--', lw=1.5, label="Đường tự nhiên TB", zorder=2)
    
    # Hiển thị nhãn văn bản cho đường TN trung bình
    ax.text(2, h_tn_tb - 0.7, f"ĐƯỜNG TỰ NHIÊN TRUNG BÌNH: {h_tn_tb:.3f}m", 
            color='#27ae60', fontsize=9, fontweight='bold', ha='left')

    if is_duong_bo:
        # B1. TRƯỜNG HỢP VƯỢT ĐƯỜNG: Vẽ mặt đường bị vượt (màu xám)
        y_nen = np.full_like(x, h1)
        ax.plot(x, y_nen, color='#7f8c8d', ls='-', lw=2.5, label="Mặt đường bị vượt", zorder=3)
        
        # Tô màu vùng đất bên dưới (giới hạn từ mặt đường h1 trở xuống)
        ax.fill_between(x, h1 - 5, h1, color='#ecf0f1', alpha=0.6, label="Nền đường cũ")
        
        # Ghi chú cao độ mặt đường
        ax.text(2, h1 + 0.3, f"CAO ĐỘ MẶT ĐƯỜNG: {h1:.3f}m", 
                color='#34495e', fontsize=9, fontweight='bold', ha='left')
    else:
        # B2. TRƯỜNG HỢP VƯỢT SÔNG: Tô màu lòng sông bên dưới đường tự nhiên
        # Đường thẳng h_tn_tb đã vẽ ở trên, giờ chỉ tô màu vùng đất/lòng sông
        ax.fill_between(x, h_tn_tb - 5, h_tn_tb, color='#f1e7d0', alpha=0.5, label="Địa hình tự nhiên")
    # --- 3. VẼ KÝ HIỆU MỰC NƯỚC (Chỉ vẽ khi vượt sông) ---
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc(ax, 75, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "orange")
    
    # --- 4. VẼ KẾT CẤU CẦU (HIỂN THỊ DỰA TRÊN LOGIC TỪ FILE 02) ---
    geo = res.get('geo_logic')
    
    if geo:
        # 4.1. Tạo mảng tọa độ Y cho toàn bộ dải X dựa trên dữ liệu từ file 02
        y_mat = []
        for xi in x:
            if xi < geo['x_t1']:
                # Đoạn tiếp tuyến bên trái
                yi = geo['y_t'] - geo['i_val'] * (geo['x_t1'] - xi)
            elif xi > geo['x_t2']:
                # Đoạn tiếp tuyến bên phải
                yi = geo['y_t'] - geo['i_val'] * (xi - geo['x_t2'])
            else:
                # Đoạn đường cong đứng (Bao phủ cả trường hợp mố nằm trong đường cong)
                yi = geo['y_dinh'] - (xi - 60)**2 / (2 * geo['R'])
            y_mat.append(yi)
        
        y_mat = np.array(y_mat)
        
        # 4.2. Vẽ Đường đỏ và Đáy dầm (cách mặt cầu 2.0m)
        ax.plot(x, y_mat, color='red', lw=3, label="Đường đỏ")
        ax.plot(x, y_mat - 2.0, color='#34495e', ls='-.', lw=1.5)
        
        # 4.3. VẼ PHẠM VI CHIỀU DÀI CẦU (ĐƯỜNG THẲNG ĐỨNG TẠI VỊ TRÍ MỐ)
        # Đường thẳng đứng nối từ cao độ tự nhiên lên đến cao độ đường đỏ tại mố
        ax.vlines(x=[geo['x_mo_trai'], geo['x_mo_phai']], 
                  ymin=geo['h_tn_tb'], ymax=geo['y_mo'], 
                  colors='brown', ls='--', lw=2.5)
        
        # 4.4. Ghi chú thông số Kỹ thuật và Tổng chiều dài L
        # Hiển thị Tổng chiều dài cầu L
        ax.text(60, geo['y_dinh'] + 1.2, f"TỔNG CHIỀU DÀI CẦU: L = {geo['L_cau']:.2f}m", 
                color='brown', fontweight='bold', ha='center', 
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
        
        # Hiển thị thông số Đường đỏ (i và R)
        ax.text(60, geo['y_dinh'] + 0.5, f"ĐƯỜNG ĐỎ: i_max={geo['i_val']*100}% | R={geo['R']}m", 
                color='red', fontweight='bold', fontsize=10, ha='center')
        
        # Hiển thị Cao độ đáy dầm thiết kế tại vị trí tim cầu
        y_day_tim = geo['y_dinh'] - 2.0
        ax.text(60, y_day_tim - 0.8, f"CAO ĐỘ ĐÁY DẦM TẠI TIM: {y_day_tim:.3f}m", 
                color='#34495e', fontsize=9, ha='center', fontweight='bold')
    else:
        # Thông báo nếu dữ liệu geo_logic chưa được truyền từ Interface sang
        ax.text(60, h_dam + 1, "⚠️ CHỜ DỮ LIỆU HÌNH HỌC TỪ FILE 02...", 
                color='orange', ha='center', fontweight='bold')

    # --- 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM ---
    if B > 0:
        # Khung tĩnh không Magenta
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2.5, zorder=3)
        ax.add_patch(rect)
        
        # DIM Bề rộng B (Dời lên cao h5 + 3.0)
        y_dim_b = h5 + H_tk/2
        ax.annotate('', xy=(60 + B/2, y_dim_b), xytext=(60 - B/2, y_dim_b),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60, y_dim_b + 0.2, f"B = {B}m", ha='center', va='bottom', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # DIM Chiều cao H
        ax.annotate('', xy=(60 + B/2 + 3, h5 + H_tk), xytext=(60 + B/2 + 3, h5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60 + B/2 + 3.5, h5 + H_tk/2, f"H = {H_tk}m", ha='left', va='center', rotation=90, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    # Tính toán cao độ mặt cầu cao nhất để đặt giới hạn trục Y
    h_mat_cau_max = h_dam + 2.0 
    
    # Thiết lập giới hạn trục Y an toàn
    y_min = min(h98, h1, h5) - 5
    y_max = h_mat_cau_max + 5
    ax.set_ylim(y_min, y_max)
    ax.axis('off')
    ax.set_title(label_res.upper() if label_res else "SƠ HỌA TRẮC DỌC CẦU", fontsize=16, fontweight='bold', pad=20)
    
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