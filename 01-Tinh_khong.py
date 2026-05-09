import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # Dữ liệu tra cứu chuẩn
    data_thuy = {
        "1": { "1": {"1": 70, "2": 85, "H": 11.0}, "2": {"1": 40, "2": 50, "H": 9.5}, "3": {"1": 30, "2": 40, "H": 7.0}, "4": {"1": 25, "2": 30, "H": 6.0}, "5": {"1": 15, "2": 20, "H": 4.0}, "6": {"1": 10, "2": 10, "H": 3.0} },
        "2": { "1": {"1": 75, "2": 120, "H": 11.0}, "2": {"1": 50, "2": 60, "H": 9.5}, "3": {"1": 30, "2": 50, "H": 7.0}, "4": {"1": 25, "2": 30, "H": 6.0}, "5": {"1": 15, "2": 25, "H": 4.0}, "6": {"1": 10, "2": 13, "H": 3.0} }
    }

    if loai_cau == "Vượt sông":
        if mien in data_thuy and cap_num in data_thuy[mien]:
            target = data_thuy[mien][cap_num]
            B = target.get(loai_hinh, "N/A")
            H = target["H"]
            cao_do_day_dam = max(h5 + H + 0.1, h1 + 0.5)
            return {
                "status": "success", "B": B, "H": H, "H1": h1, "H5": h5, "H10": h10, "H98": h98,
                "day_dam": round(cao_do_day_dam, 3), "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
    elif loai_cau == "Vượt đường bộ":
        H = 5.0 if loai_duong_vuot == "Cao tốc" else (4.75 if cap_oto == "1" else 4.5)
        return {"status": "success", "B": 20.0, "H": H, "day_dam": 0.0, "label": f"Cầu vượt {loai_duong_vuot}"}
    return {"status": "error"}

def ve_so_do_bo_tri_chung(res):
    # Tạo khổ ảnh rộng (Panorama) để giống bản vẽ kỹ thuật
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # 1. Lấy thông số từ kết quả
    h1, h5, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H98', 0)
    h_dam = res.get('day_dam', 0)
    H_tk, B = res.get('H', 0), res.get('B', 0)
    
    # Giả định các thông số hình học để vẽ sơ đồ (tỉ lệ m)
    L_tong = 120
    L_nhip = B + 20 # Nhịp chính rộng hơn khổ B
    x_center = L_tong / 2
    
    # 2. Vẽ ĐƯỜNG TỰ NHIÊN (Màu xanh lá, nét đứt)
    x_ground = np.linspace(0, L_tong, 100)
    y_ground = h98 - 3 + 2 * np.sin(x_ground/20) # Tạo độ nhấp nhô giả lập
    ax.plot(x_ground, y_ground, color='#2ecc71', linestyle='--', lw=2, label='Cao độ tự nhiên')

    # 3. Vẽ ĐƯỜNG ĐỎ / MẶT CẦU (Màu đỏ, nét liền)
    h_mat_cau = h_dam + 2.5 # Giả định dầm + bản mặt cầu dày 2.5m
    ax.plot([0, L_tong], [h_mat_cau, h_mat_cau], color='red', lw=3, label='Đường đỏ (Mặt cầu)')

    # 4. Vẽ KẾT CẤU DẦM GIẢN ĐƠN (Các nhịp)
    # Nhịp biên trái, Nhịp chính, Nhịp biên phải
    nhip_coords = [(0, 30), (30, 30+L_nhip), (30+L_nhip, L_tong)]
    for start, end in nhip_coords:
        rect = patches.Rectangle((start + 0.5, h_dam), (end - start - 1), 2.0, 
                                 linewidth=1.5, edgecolor='black', facecolor='#95a5a6', alpha=0.8)
        ax.add_patch(rect)

    # 5. Vẽ MỐ & TRỤ CẦU
    # Trụ 1 và Trụ 2 (Pier)
    ax.add_patch(patches.Rectangle((30 - 2, y_ground[25]), 4, h_dam - y_ground[25], color='#7f8c8d')) 
    ax.add_patch(patches.Rectangle((30 + L_nhip - 2, y_ground[75]), 4, h_dam - y_ground[75], color='#7f8c8d'))
    # Mố cầu (Abutment) - Vẽ đơn giản dạng hình thang
    ax.fill([0, 10, 10, 0], [h_dam, h_dam, y_ground[0], y_ground[0]], color='#7f8c8d')
    ax.fill([L_tong-10, L_tong, L_tong, L_tong-10], [h_dam, h_dam, y_ground[-1], y_ground[-1]], color='#7f8c8d')

    # 6. Vẽ VÙNG NƯỚC & CÁC MỰC NƯỚC
    ax.fill_between([10, L_tong-10], h98 - 1, h1, color='#E3F2FD', alpha=0.4)
    
    # MNCN H1%
    ax.axhline(y=h1, xmin=0.1, xmax=0.9, color='blue', linestyle='-', lw=1)
    ax.text(L_tong-5, h1, f"MNCN H1%: {h1:.3f}m", color='blue', fontsize=9, fontweight='bold')
    
    # 7. Vẽ KHUNG TĨNH KHÔNG (H x B) - Hình chữ nhật nét đứt màu tím
    tk_rect = patches.Rectangle((x_center - B/2, h5), B, H_tk, 
                                linewidth=2, edgecolor='magenta', facecolor='none', linestyle='--')
    ax.add_patch(tk_rect)
    
    # Ghi chú Tĩnh không trong khung
    ax.text(x_center, h5 + H_tk/2, f"Tĩnh không\nHtk = {H_tk}m\nB = {B}m", 
            ha='center', va='center', color='magenta', fontweight='bold', bbox=dict(facecolor='white', alpha=0.8))

    # 8. Đường DIM Cao độ đáy dầm tối thiểu
    ax.annotate('', xy=(x_center + B/2 + 5, h_dam), xytext=(x_center + B/2 + 5, h5),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1))
    ax.text(x_center + B/2 + 6, (h_dam + h5)/2, f"H_thực = {h_dam-h5:.3f}m", fontweight='bold')

    # Thiết lập khung nhìn
    ax.set_xlim(-5, L_tong + 20)
    ax.set_ylim(min(y_ground) - 2, h_mat_cau + 5)
    ax.axis('off')
    ax.set_title(f"SƠ ĐỒ BỐ TRÍ CHUNG MẶT CẮT DỌC CẦU (DẦM GIẢN ĐƠN)\nKhổ thông thuyền: B={B}m, H={H_tk}m", 
                 fontsize=16, fontweight='bold', pad=20)

    return fig