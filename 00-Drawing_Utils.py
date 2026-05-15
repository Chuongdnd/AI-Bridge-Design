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
    
    # Lấy thông số geo_logic để đồng bộ tim cầu và chiều dài
    geo = res.get('geo_logic')
    # Ưu tiên x_dinh từ geo_logic (150), nếu chưa có thì dùng 60 làm fallback
    x_center = geo.get('x_dinh', 60) if geo else 60
    # Mở rộng phạm vi vẽ lên 300m để thấy hết cầu dài
    x_limit = 300 if x_center > 100 else 120
    
    # Kiểm tra loại cầu
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    if isinstance(B, str): B = 0
    # Tạo dải X rộng để bao phủ toàn bộ phạm vi quét địa hình
    x = np.linspace(0, x_limit, 500)

    # --- 2. VẼ ĐỊA HÌNH VÀ ĐƯỜNG TỰ NHIÊN TB ---
    h_tn_tb = res.get('h_tn_tb', 3.0) 

    if is_duong_bo:
        # Vẽ mặt đường bị vượt (Màu xám)
        y_nen = np.full_like(x, h1)
        ax.plot(x, y_nen, color='#7f8c8d', ls='-', lw=2.5, label="Mặt đường bị vượt", zorder=3)
        ax.fill_between(x, h1 - 5, h1, color='#ecf0f1', alpha=0.6)
        ax.text(2, h1 + 0.3, f"CAO ĐỘ MẶT ĐƯỜNG: {h1:.3f}m", color='#34495e', fontsize=9, fontweight='bold')

        # Vẽ đường TN trung bình
        y_tn_flat = np.full_like(x, h_tn_tb)
        ax.plot(x, y_tn_flat, color='#27ae60', ls='--', lw=1.5, label="Đường TN TB", zorder=2)
        ax.text(2, h_tn_tb - 0.8, f"ĐƯỜNG TỰ NHIÊN TRUNG BÌNH: {h_tn_tb:.3f}m", 
                color='#27ae60', fontsize=9, fontweight='bold')
    else:
        # Vượt sông: Chỉ vẽ đường TN trung bình
        y_tn_flat = np.full_like(x, h_tn_tb)
        ax.plot(x, y_tn_flat, color='#27ae60', ls='--', lw=2.0)
        ax.fill_between(x, h_tn_tb - 5, h_tn_tb, color='#f1e7d0', alpha=0.5)
        ax.text(2, h_tn_tb - 0.8, f"ĐƯỜNG TỰ NHIÊN TRUNG BÌNH: {h_tn_tb:.3f}m", 
                color='#27ae60', fontsize=9, fontweight='bold')

    # --- 3. VẼ KÝ HIỆU MỰC NƯỚC (Điều chỉnh vị trí theo x_center) ---
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, x_center - 45, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc(ax, x_center - 15, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc(ax, x_center + 15, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc(ax, x_center + 45, h98, "MNTN H98%", "orange")
    
    # --- 4. VẼ KẾT CẤU CẦU ---
    if geo:
        # 4.1. Tạo mảng tọa độ Y dựa trên x_center động
        y_mat = []
        for xi in x:
            if xi < geo['x_t1']:
                yi = geo['y_t'] - geo['i_val'] * (geo['x_t1'] - xi)
            elif xi > geo['x_t2']:
                yi = geo['y_t'] - geo['i_val'] * (xi - geo['x_t2'])
            else:
                # THAY 60 THÀNH x_center Ở ĐÂY
                yi = geo['y_dinh'] - (xi - x_center)**2 / (2 * geo['R'])
            y_mat.append(yi)
        
        y_mat = np.array(y_mat)
        # --- LẤY THÔNG SỐ CẤU TẠO DẦM TỪ AI ---

        h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65) # Mặc định 1.65m nếu chưa có AI
        h_ban_mat_cau = 0.18  # Bản mặt cầu 180mm
        
        # 4.2. Vẽ cấu tạo nhịp cầu: Đường đỏ -> Đỉnh dầm -> Đáy dầm
        # Tính toán các cao độ
        y_duong_do = y_mat
        y_dinh_dam = y_mat - h_ban_mat_cau
        y_day_dam_thuc = y_dinh_dam - h_dam_ai
        
        # Vẽ các đường nét
        ax.plot(x, y_duong_do, color='red', lw=3, label="Đường đỏ")
        ax.plot(x, y_dinh_dam, color='darkblue', ls='-', lw=1.2, label="Đỉnh dầm")
        ax.plot(x, y_day_dam_thuc, color='#34495e', ls='-.', lw=1.5, label="Đáy dầm")

        # Tô màu cho dầm và bản mặt cầu để dễ phân biệt
        ax.fill_between(x, y_dinh_dam, y_duong_do, color='gray', alpha=0.3) # Bản mặt cầu

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
        y_day_tim = geo['y_dinh'] - h_ban_mat_cau - h_dam_ai
        ax.text(60, y_day_tim - 0.8, f"CAO ĐỘ ĐÁY DẦM TẠI TIM: {y_day_tim:.3f}m", 
                color='#34495e', fontsize=9, ha='center', fontweight='bold')
    else:
        # Thông báo nếu dữ liệu geo_logic chưa được truyền từ Interface sang
        ax.text(60, h_dam + 1, "⚠️ CHỜ DỮ LIỆU HÌNH HỌC TỪ FILE 02...", 
                color='orange', ha='center', fontweight='bold')

    # --- 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM (Cập nhật hiển thị góc xiên) ---
    if B > 0:
        # 5.1. Khung tĩnh không Magenta
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2.5, zorder=3)
        ax.add_patch(rect)
        
        # 5.2. Tính toán text hiển thị cho B
        alpha = res.get('goc_giao', 90.0)
        if alpha < 90:
            # Tính ngược lại B tiêu chuẩn để hiển thị công thức: B_tc = B_tk * sin(alpha)
            B_tieuchuan = round(B * np.sin(np.radians(alpha)), 1)
            label_B = f"B_tk = {B}m\n({B_tieuchuan} / sin({alpha}°))"
        else:
            label_B = f"B = {B}m"

        # 5.3. DIM Bề rộng B (Dời lên cao h5 + H_tk/2)
        y_dim_b = h5 + H_tk/2
        ax.annotate('', xy=(60 + B/2, y_dim_b), xytext=(60 - B/2, y_dim_b),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        
        # Hiển thị text với 2 dòng nếu có góc xiên
        ax.text(60, y_dim_b + 0.3, label_B, ha='center', va='bottom', 
                fontweight='bold', fontsize=9, 
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # 5.4. DIM Chiều cao H
        ax.annotate('', xy=(60 + B/2 + 3, h5 + H_tk), xytext=(60 + B/2 + 3, h5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60 + B/2 + 3.5, h5 + H_tk/2, f"H = {H_tk}m", ha='left', va='center', 
                rotation=90, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        # --- 5.5. FIX LỖI CHỒNG LẤN NHÃN DIM CẤU TẠO ---
        x_dim_cau_tao = 30  # Đẩy vị trí DIM sang trái thêm một chút (từ 35 về 30) để thoáng hơn
        
        idx_dim = np.argmin(np.abs(x - x_dim_cau_tao))
        y_day_pt = y_day_dam_thuc[idx_dim]
        y_dinh_pt = y_dinh_dam[idx_dim]
        y_do_pt = y_duong_do[idx_dim]
        
        # 1. DIM Chiều cao dầm (Màu xanh)
        ax.annotate('', xy=(x_dim_cau_tao, y_day_pt), xytext=(x_dim_cau_tao, y_dinh_pt),
                    arrowprops=dict(arrowstyle='<->', color='blue', lw=1.2))
        # Căn lề 'top' để đẩy chữ xuống dưới điểm giữa đường DIM
        ax.text(x_dim_cau_tao - 1.5, y_day_pt, f"h_dầm = {h_dam_ai}m", 
                ha='left', va='center', rotation=90, color='blue', fontsize=9, fontweight='bold')

        # 2. DIM Bản mặt cầu (Màu đỏ)
        ax.annotate('', xy=(x_dim_cau_tao, y_dinh_pt), xytext=(x_dim_cau_tao, y_do_pt),
                    arrowprops=dict(arrowstyle='<->', color='red', lw=1.2))
        # Căn lề 'bottom' để đẩy chữ lên trên điểm giữa đường DIM
        ax.text(x_dim_cau_tao - 1.5, y_do_pt, f"h_bmc = {h_ban_mat_cau}m", 
                ha='right', va='bottom', rotation=90, color='red', fontsize=9, fontweight='bold')
        
        # 3. KÝ HIỆU ĐƯỜNG DÓNG NGẮN (Gọn gàng hơn)
        line_style = dict(color='black', lw=0.6, ls=':', alpha=0.6)
        ax.plot([x_dim_cau_tao - 2, x_dim_cau_tao + 1], [y_day_pt, y_day_pt], **line_style)
        ax.plot([x_dim_cau_tao - 2, x_dim_cau_tao + 1], [y_dinh_pt, y_dinh_pt], **line_style)
        ax.plot([x_dim_cau_tao - 2, x_dim_cau_tao + 1], [y_do_pt, y_do_pt], **line_style)
    # --- 6. CẤU HÌNH TRỤC VÀ HIỂN THỊ ---
    ax.set_xlim(-5, 125)
    
    # Cao độ mặt cầu cao nhất để đặt giới hạn trục Y (Sử dụng np.max để lấy Scalar)
    h_mat_cau_max = np.max(y_duong_do) if geo else h_dam + 2.0
    
    # Thiết lập giới hạn trục Y an toàn, bao phủ cả mực nước và đáy dầm
    y_min_elements = [h98, h1, h5]
    if geo:
        y_min_elements.append(np.min(y_day_dam_thuc)) # Thêm đáy dầm vào danh sách so sánh
    
    y_min = min(y_min_elements) - 5
    y_max = h_mat_cau_max + 5
    
    ax.set_ylim(y_min, y_max)
    ax.axis('off')
    ax.set_title(label_res.upper() if label_res else "SƠ HỌA TRẮC DỌC CẦU", 
                 fontsize=16, fontweight='bold', pad=20)
    
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