"""mcda — Module chấm điểm so sánh phương án MCDA / AHP-Saaty.

Cấu trúc:
  criteria_config  — bộ tiêu chí động (10 mặc định / 4 nhóm, thêm bớt được)
  data_adapter     — trích dữ liệu 3 PA tự động từ Session State (Module 06+12)
  scoring_formulas — công thức chấm điểm thô 0–10 (threshold + minmax)
  ahp_calculator   — thuật toán AHP-Saaty (trọng số, λ_max, CI, CR) + 2 cấp
  ahp_interface    — UI so sánh cặp + kết quả (bảng, radar, tổng điểm)
  criteria_manager — UI bật/tắt/thêm/xóa tiêu chí + nhập dữ liệu thủ công
"""
