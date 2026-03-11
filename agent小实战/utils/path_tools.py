"""
为每个工程提供统一的绝对路径
"""

import os

def get_project_root() -> str:
    current_file = os.path.abspath(__file__) #获取当前文件的绝对路径
    current_dir = os.path.dirname(current_file)  # 获取当前文件所在目录
    project_root = os.path.dirname(current_dir)  # 获取项目根目录
    return project_root

def get_abs_path(relative_path: str) -> str:
    p