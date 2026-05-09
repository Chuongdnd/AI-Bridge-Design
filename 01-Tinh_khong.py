import matplotlib.pyplot as plt
import matplotlib.patches as patches

def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    data_thuy = {
        "1": { # Bắc
            "1": {"1": 70, "2": 85, "H": 11.0}, "2": {"1": 40, "2": 50, "H": 9.5},
            "3": {"1": 30, "2": 40, "H": 7.0},  "4": {"1": 25, "2": 30, "H": 6.0},
            "5": {"1": 15, "2": 20, "H": 4.0},  "6": {"1": 10, "2": 10, "H": 3.0},
        },
        "2": { # Nam
            "1": {"1": 75, "2": 120, "H": 11.0}, "2": {"1": 50, "2": 60, "H": 9.5},
            "3": {"1": 30, "2": 50, "H": 7.0},  "4": {"1": 25, "2": 30, "H": 6.0},
            "5": {"1": 15, "2": 25, "H": 4.0},  "6": {"1": 10, "2": 13, "H": 3.0},
        }
    }

    if loai_cau == "Vượt sông":
        if mien in data_thuy and cap_num in data_thuy[mien]:
            target = data_thuy[mien][cap_num]
            B = target.get(loai_hinh, "N/A")
            H = target["H"]
            
            cao_do_dat_goi = h1 + 0.5
            # Công thức H5 + H + 0.1
            cao_do_day_dam = max(h5 + H + 0.1, cao_do_dat_goi)
            
            return {
                "status": "success",
                "B": B, "H": H,
                "H1": h1, "H5": h5, "H10": h10, "H98": h98,
                "day_dam": round(cao_do_day_dam, 3),
                "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
            
    elif loai_cau == "Vượt đường bộ":
        H = 5.0 if loai_duong_vuot == "Cao tốc" else (4.75 if cap_oto == "1" else 4.5)
        return {
            "status": "success",
            "B": 20.0, "H": H, "day_dam": "Theo trắc dọc",
            "label": f"Cầu vượt {loai_duong_vuot}"
        }
    return {"status": "error", "message": "Dữ liệu không hợp lệ"}

def ve_so_do_dam_gian_don_dong(res):
    """Vẽ sơ đồ trắc dọc dầm giản đơn với thông số động"""
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Lấy thông số (Sử dụng đúng key từ dictionary res)
    h1, h5, h10, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H10', 0), res.get('H98', 0)
    h_dam, H_tk, B = res.get('day_dam', 0), res.get('H', 0), res.get('B', 0)
    
    # 1. Vẽ vùng nước màu xanh nhạt
    ax.fill_between([-10, 80], h98 - 1, h1, color='#E3F2FD', alpha=0.6)
    
    # 2. Vẽ Trụ cầu (Pier)
    ax.add_patch(patches.Rectangle((5, h98 - 2), 4, h_dam - h98 + 2.5, color='#BDBDBD', ec='black'))
    ax.add_patch(patches.Rectangle((61, h98 - 2), 4, h_dam - h98 + 2.5, color='#BDBDBD', ec='black'))

    # 3. Vẽ DẦM GIẢN ĐƠN (Chiều cao không đổi h=2m)
    ax.add_patch(patches.Rectangle((-5, h_dam), 80, 2.0, color='#546E7A', ec='black', lw=2))
    
    # 4. Vẽ các đường mực nước
    levels = [(h1, 'MNCN H1%', '#D32F2F'), (h5, 'MNTT H5%', '#1976D2'), 
              (h10, 'MNTC H10%', '#388E3C'), (h98, 'MNTN H98%', '#F57C00')]
    
    for val, label, col in levels:
        ax.axhline(y=val, color=col, linestyle='--', lw=1.5, alpha=0.7)
        ax.text(72, val + 0.1, f"{label}: {val:.3f}m", color=col, fontweight='bold', fontsize=9)

    # 5. Vẽ DIM Tĩnh không H (H5 đến đáy dầm)
    if isinstance(h_dam, (int, float)):
        ax.annotate('', xy=(35, h5), xytext=(35, h_dam), arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
        ax.text(36, (h5 + h_dam)/2, f"H_thực = {h_dam - h5:.3f}m\n(H_tk={H_tk}m + 0.1m)", fontweight='bold')
    
    # 6. Vẽ DIM Khổ ngang B
    ax.annotate('', xy=(9, h5 - 0.5), xytext=(61, h5 - 0.5), arrowprops=dict(arrowstyle='<->', color='#0D47A1', lw=2))
    ax.text(35, h5 - 1.2, f"Khổ ngang B = {B} m", ha='center', color='#0D47A1', fontweight='bold', fontsize=12)

    ax.set_xlim(-5, 90)
    ax.set_ylim(h98 - 3, h_dam + 5)
    ax.axis('off')
    ax.set_title("SƠ ĐỒ TRẮC DỌC TĨNH KHÔNG & THỦY VĂN (DẦM GIẢN ĐƠN)", fontsize=14, fontweight='bold')
    return fig