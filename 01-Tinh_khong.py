import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment
def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # (Giữ nguyên logic tra cứu dữ liệu của bạn ở đây...)
    # Giả định trả về dictionary res
    return {
        "status": "success", "B": 40, "H": 7.0, 
        "H1": h1, "H5": h5, "H10": h10, "H98": h98, 
        "day_dam": h5 + 7.0 + 0.1
    }

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    """
    Vẽ ký hiệu tam giác mức nước và text cao độ
    """
    d_x = 1.2   # Độ rộng tam giác
    d_y = 0.8   # Chiều cao tam giác
    
    # Vẽ tam giác
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)
    ], facecolor=color, edgecolor='black', lw=1)
    ax.add_patch(triangle)
    
    # Vẽ 3 gạch nhỏ bên dưới (sóng nước)
    for i in range(1, 4):
        dash_w = d_x * (1 - i*0.2)
        ax.plot([x_pos - dash_w, x_pos + dash_w], [y_val - i*0.3, y_val - i*0.3], color='black', lw=0.8)
    
    # Ghi chú Text
    ax.text(x_pos, y_val + d_y + 0.2, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontweight='bold', fontsize=9)

def ve_so_do_bo_tri_chung(res):
    fig, ax = plt.subplots(figsize=(16, 8))
    
    h1, h5, h10, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H10', 0), res.get('H98', 0)
    h_dam, H_tk, B = res.get('day_dam', 0), res.get('H', 0), res.get('B', 0)
    
    # --- PHẦN 1: ĐƯỜNG TỰ NHIÊN & ĐẤT ---
    x = np.linspace(0, 120, 200)
    y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000)) 
    ax.plot(x, y_tn, color='#27ae60', linestyle='--', lw=1.5)
    ax.fill_between(x, h98 - 6, y_tn, color='#f1e7d0', alpha=0.5)

    # --- PHẦN 2: KÝ HIỆU MỰC NƯỚC (TAM GIÁC) ---
    # Sắp xếp vị trí x để các tam giác không đè lên nhau
    ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
    ve_ky_hieu_muc_nuoc(ax, 35, h10, "MNTC H10%", "green")
    ve_ky_hieu_muc_nuoc(ax, 85, h5, "MNTT H5%", "blue")
    ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "#d35400")

    # --- PHẦN 3: ĐƯỜNG ĐỎ & KẾT CẤU CẦU ---
    h_mat_cau = h_dam + 2.0
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=2.5)
    ax.text(2, h_mat_cau + 0.5, "ĐƯỜNG ĐỎ", color='red', fontweight='bold')
    
    # Dầm và Trụ
    ax.add_patch(patches.Rectangle((15, h_dam), 90, 1.6, color='#bdc3c7', ec='black', zorder=3))
    for x_tru in [40, 80]:
        idx = int(x_tru * 200 / 120)
        ax.add_patch(patches.Rectangle((x_tru-1.5, y_tn[idx]), 3, h_dam - y_tn[idx], color='#7f8c8d'))

    # --- PHẦN 4: KHUNG TĨNH KHÔNG ---
    ax.add_patch(patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2))
    ax.text(60, h5 + H_tk/2, f"KHUNG TĨNH KHÔNG\n{B}m x {H_tk}m", ha='center', color='magenta', fontweight='bold')

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    ax.set_ylim(h98 - 5, h_mat_cau + 5)
    ax.axis('off')
    ax.set_title("SƠ HỌA TRẮC DỌC CẦU & THỦY VĂN", fontsize=15, fontweight='bold')
    
    return fig
def xuat_file_cad(res):
    import ezdxf
    import numpy as np
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # 1. Lấy thông số chung (Cực kỳ quan trọng để khớp dữ liệu)
    h1, h5, h10, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H10', 0), res.get('H98', 0)
    h_dam, H_tk, B = res.get('day_dam', 0), res.get('H', 0), res.get('B', 0)
    L_tong = 120

    # 2. VẼ ĐƯỜNG TỰ NHIÊN (Giống hệt logic Matplotlib)
    x_coords = np.linspace(0, L_tong, 200)
    y_tn_coords = h98 - 1.5 + 2.5 * (1 - np.exp(-((x_coords - 60)**2) / 1000))
    points = list(zip(x_coords, y_tn_coords))
    msp.add_lwpolyline(points, dxfattribs={'color': 3, 'linetype': 'DASHED'}) # Màu xanh lá, nét đứt

    # 3. VẼ ĐƯỜNG ĐỎ (Mặt cầu)
    h_mat_cau = h_dam + 2.0
    msp.add_line((0, h_mat_cau), (L_tong, h_mat_cau), dxfattribs={'color': 1}) # Màu đỏ

    # 4. VẼ DẦM (Rectangle giống patches.Rectangle)
    # Tọa độ: (x_start, y_start) đến (x_end, y_end)
    msp.add_lwpolyline([(15, h_dam), (105, h_dam), (105, h_dam + 1.6), (15, h_dam + 1.6), (15, h_dam)], 
                       dxfattribs={'closed': True, 'color': 7})

    # 5. VẼ TRỤ CẦU (Logic vòng lặp y hệt Matplotlib)
    for x_tru in [40, 80]:
        idx = int(x_tru * 200 / L_tong)
        y_day_tru = y_tn_coords[idx]
        msp.add_lwpolyline([(x_tru-1.5, y_day_tru), (x_tru+1.5, y_day_tru), 
                            (x_tru+1.5, h_dam), (x_tru-1.5, h_dam), (x_tru-1.5, y_day_tru)], 
                           dxfattribs={'closed': True, 'color': 8})

    # 6. VẼ CÁC KÝ HIỆU TAM GIÁC MỰC NƯỚC
    def ve_tam_giac_cad(x, y, label, col_idx):
        # Tam giác ngược
        msp.add_lwpolyline([(x-1.2, y+0.8), (x+1.2, y+0.8), (x, y), (x-1.2, y+0.8)], dxfattribs={'color': col_idx})
        # Text cao độ
        msp.add_text(f"{label}: {y:.3f}m", dxfattribs={'height': 0.5, 'color': col_idx}).set_placement((x, y + 1.2), align=TextEntityAlignment.CENTER)

    ve_tam_giac_cad(15, h1, "MNCN H1%", 1)   # Đỏ
    ve_tam_giac_cad(85, h5, "MNTT H5%", 5)   # Xanh dương
    ve_tam_giac_cad(105, h98, "MNTN H98%", 40) # Cam/Nâu

    # 7. KHUNG TĨNH KHÔNG (Nét đứt Magenta)
    msp.add_lwpolyline([(60-B/2, h5), (60+B/2, h5), (60+B/2, h5+H_tk), (60-B/2, h5+H_tk), (60-B/2, h5)], 
                       dxfattribs={'color': 6, 'linetype': 'DOTTED'})

    return doc