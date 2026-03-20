import json
import os

from langchain_core.tools import tool

from utils.config_handler import rag_conf
from utils.log import logger
from utils.path_tools import get_abs_path

_external_data:dict[str, dict[str, dict[str, str]]] = {}


def _generate_external_data() -> None:
    if _external_data:
        return

    configured_path = str(rag_conf["external_data_path"]).strip().strip('"').strip("'")
    external_data_path = os.path.normpath(get_abs_path(configured_path))
    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8") as file_obj:
        for line in file_obj.readlines()[1:]:
            arr:list[str] = line.strip().split(",")
            if len(arr) < 6:
                logger.warning(f"外部数据格式异常，跳过记录: {line.strip()}")
                continue

            user_id = arr[0].replace('"', "")
            feature = arr[1].replace('"', "")
            efficiency = arr[2].replace('"', "")
            consumables = arr[3].replace('"', "")
            comparison = arr[4].replace('"', "")
            time = arr[5].replace('"', "")

            if user_id not in _external_data:
                _external_data[user_id] = {}

            _external_data[user_id][time] = {
                "特征": feature,
                "效率": efficiency,
                "耗材": consumables,
                "对比": comparison,
            }


@tool(description="从外部系统中获取用户的使用记录，返回JSON字符串；如果未检索到则返回空字符串")
def fetch_external_data(user_id:str, month:str) -> str:
    _generate_external_data()

    user_records = _external_data.get(user_id, {})
    record = user_records.get(month)
    if record is None:
        logger.warning(f"未检索到用户{user_id}在{month}的使用记录")
        return ""

    return json.dumps(record, ensure_ascii=False)
