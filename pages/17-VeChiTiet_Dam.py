"""
Trang standalone: Vẽ Chi Tiết Dầm.
Khi Streamlit chạy file này trực tiếp, nó nạp engine + UI rồi render tab.
"""
import importlib.util
import pathlib
import sys

import streamlit as st

_ROOT = pathlib.Path(__file__).parent.parent

# Load engine
_espec = importlib.util.spec_from_file_location(
    "BeamBuilder", _ROOT / "17-BeamBuilder.py")
_emod = importlib.util.module_from_spec(_espec)
sys.modules["BeamBuilder"] = _emod
_espec.loader.exec_module(_emod)

# Load UI module
_uspec = importlib.util.spec_from_file_location(
    "BeamBuilderUI", _ROOT / "17-BeamBuilderUI.py")
_umod = importlib.util.module_from_spec(_uspec)
_uspec.loader.exec_module(_umod)

st.set_page_config(page_title="Vẽ Chi Tiết Dầm", layout="wide", page_icon="📐")
st.title("📐 Vẽ Chi Tiết Dầm")
st.caption("Section Sketcher + Parametric Beam Builder  |  Đơn vị: mm")

_umod.render_tab()
