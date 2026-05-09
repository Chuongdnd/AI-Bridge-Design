def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # --- DỮ LIỆU GỐC TỪ FORM MẪU V5.0 ---
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
            
            # Tính toán cao độ đáy dầm tối thiểu
            cao_do_dat_goi = h1 + 0.5
            cao_do_day_dam = max(h5+H+0.1, cao_do_dat_goi)
            
            return {
                "status": "success",
                "B": B,
                "H": H,
                "MNCN": h1,   # Mực nước cao nhất
                "MNTT": h5,   # Mực nước thông thuyền
                "MNTC": h10,  # Mực nước thi công
                "MNTN": h98,  # Mực nước thấp nhất
                "day_dam": round(cao_do_day_dam, 2),
                "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
            
    elif loai_cau == "Vượt đường bộ":
        H = 0
        ten = ""
        if loai_duong_vuot == "Cao tốc":
            H = 5.0
            ten = "Đường Cao tốc"
        else:
            H = 4.75 if cap_oto == "1" else 4.5
            ten = "Đường Ô tô"
            
        return {
            "status": "success",
            "B": "Theo quy mô mặt cắt ngang",
            "H": H,
            "day_dam": "Tính theo cao độ mặt đường bị vượt",
            "label": f"Cầu vượt {ten}"
        }
    
    return {"status": "error", "message": "Dữ liệu không hợp lệ"}
import matplotlib.pyplot as plt

def ve_so_do_thuy_van_dong(res):
    """Vẽ sơ đồ trắc dọc tĩnh không với thông số động"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Lấy thông số từ kết quả
    h1 = res.get('H1', 0)
    h5 = res.get('H5', 0)
    h10 = res.get('H10', 0)
    h98 = res.get('H98', 0)
    h_dam = res.get('day_dam', 0)
    H_tinh_khong = res.get('H', 0)
    B_ngang = res.get('B', 0)

    # 1. Vẽ mặt đất/đáy sông (minh họa)
    ax.fill_between([-10, 60], [-1, -1], [h98 - 0.5, h98 - 0.5], color='#d2b48c', alpha=0.5)

    # 2. Vẽ kết cấu nhịp cầu (Dầm)
    # Vẽ đáy dầm là một đường thẳng đậm
    ax.plot([-5, 55], [h_dam, h_dam], color='black', lw=4, label='Đáy dầm cầu')
    ax.fill_between([-5, 55], [h_dam, h_dam], [h_dam + 1.5, h_dam + 1.5], color='gray', alpha=0.3)

    # 3. Vẽ các đường mực nước (Dash lines)
    water_levels = [
        {'val': h1, 'label': f'MNCN H1% ({h1:.3f}m)', 'color': 'red'},
        {'val': h5, 'label': f'MNTT H5% ({h5:.3f}m)', 'color': 'blue'},
        {'val': h10, 'label': f'MNTC H10% ({h10:.3f}m)', 'color': 'green'},
        {'val': h98, 'label': f'MNTN H98% ({h98:.3f}m)', 'color': 'orange'},
    ]

    for wl in water_levels:
        ax.axhline(y=wl['val'], color=wl['color'], linestyle='--', lw=1.2)
        ax.text(56, wl['val'], wl['label'], va='center', color=wl['color'], fontweight='bold')

    # 4. Vẽ đường DIM tĩnh không đứng (H)
    ax.annotate('', xy=(25, h5), xytext=(25, h_dam),
                arrowprops=dict(arrowstyle='<->', color='purple', lw=2))
    ax.text(26, (h5 + h_dam)/2, f"H_tổng = {h_dam - h5:.3f}m\n(H_tk={H_tinh_khong}m + 0.1m)", 
            color='purple', fontweight='bold', va='center')

    # 5. Vẽ đường DIM khổ ngang (B) - Minh họa giữa 2 trụ
    ax.annotate('', xy=(10, h5 - 0.5), xytext=(40, h5 - 0.5),
                arrowprops=dict(arrowstyle='<->', color='blue', lw=2))
    ax.text(25, h5 - 1.2, f"B_ngang = {B_ngang} m", ha='center', color='blue', fontweight='bold')

    # Thiết lập trục tọa độ
    ax.set_xlim(-10, 75)
    ax.set_ylim(h98 - 2, h_dam + 3)
    ax.set_ylabel("Cao độ (m)")
    ax.set_title("SƠ ĐỒ MINH HỌA TĨNH KHÔNG VÀ CÁC MỰC NƯỚC THIẾT KẾ", fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    return fig