# bridge_components.py
import cadquery as cq
import numpy as np
import plotly.graph_objects as go
from stl import mesh

def create_pier(H, W, L, top_W, top_H, base_W, base_H, base_L):
    """
    Tạo mô hình trụ cầu với các thông số:
    - H: chiều cao thân trụ
    - W: chiều rộng thân trụ (theo phương ngang cầu)
    - L: chiều dài thân trụ (theo phương dọc cầu)
    - top_W: chiều rộng đỉnh trụ (phần mũ)
    - top_H: chiều cao mũ trụ
    - base_W: chiều rộng bệ trụ
    - base_H: chiều cao bệ trụ
    - base_L: chiều dài bệ trụ
    Trả về CadQuery object
    """
    # Thân trụ hình hộp chữ nhật
    pier_body = cq.Workplane("XY").box(L, W, H)
    # Mũ trụ (phần trên)
    pier_top = cq.Workplane("XY").box(L, top_W, top_H).translate((0, 0, H/2 + top_H/2))
    # Bệ trụ (phần dưới)
    pier_base = cq.Workplane("XY").box(base_L, base_W, base_H).translate((0, 0, -base_H/2))
    # Kết hợp
    pier = pier_body.union(pier_top).union(pier_base)
    return pier

def cadquery_to_plotly_mesh(cq_obj):
    """
    Chuyển đổi CadQuery object sang Plotly Mesh3d (vertices, faces)
    """
    # Xuất tạm thời sang STL
    stl_file = "temp.stl"
    cq.exporters.export(cq_obj, stl_file)
    # Đọc STL
    data = mesh.Mesh.from_file(stl_file)
    vertices = data.vectors.reshape(-1, 3)
    # Tạo faces: mỗi tam giác có 3 đỉnh, indices theo thứ tự
    n_faces = len(data.vectors)
    faces = []
    for i in range(n_faces):
        base_idx = i * 3
        faces.append([base_idx, base_idx+1, base_idx+2])
    faces = np.array(faces)
    # Lọc bỏ các đỉnh trùng lặp? Plotly yêu cầu faces là chỉ số, không cần lọc.
    return vertices, faces