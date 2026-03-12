import os,hashlib
from log import logger


def get_file_md5_hex(filepath,str):
    if not os.path.exists(filepath):
        logger.error(f"文件{filepath}不存在")
        return

    if not os.path.isfile(filepath):
        logger.error(f"{filepath}不是一个文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 4096
    try:
        with open(filepath,"rb")as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)

def listdir_with_allowed_type():
    if 

def pdf_loader():
    pass

def txt_loader():
    pass

