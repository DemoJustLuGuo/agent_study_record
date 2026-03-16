#agent工具

from langchain_core.tools import tool
from rag.rag_service import RAGSummarizeService
from utils.config_handler import agent_conf
from utils.path_tools import get_abs_path
from utils.log import logger

import os,random

rag = RAGSummarizeService()
user_id =["1001","1002","1003","1004","1005","1006","1007","1008","1009","1010"]
month = ["2024-01","2024-02","2024-03","2024-04","2024-05","2024-06","2024-07","2024-08","2024-09","2024-10","2024-11","2024-12"]
external_data = {}

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str) -> str:
    return rag.rag_summarize(query)

@tool(description="获取指定城市的天气信息，以消息字符串的方式返回")
def get_weather(city:str) -> str:
    return f"{city}的天气晴朗，温度25摄氏度，空气湿度为50%，南风1级，最近6小时降雨概率极低。"
    
@tool(description="获取用户的位置信息，以纯字符串形式返回")
def get_user_location() -> str:
    return random.choice(["北京市", "上海市", "广州市", "深圳市", "杭州市"])

@tool(description="获取用户的id信息，以纯字符串形式返回")
def get_user_id() -> str:
    return "用户ID: 123456"

@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return "当前月份是6月。"

def generate_external_data():
    """
    {
    "user_id":{
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...} 
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}  
        ...   
        }    
        
        "user_id":{
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...} 
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}   
        ...  
        }    
        
        "user_id":{
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...} 
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...}     
        "month":{"特征": feature,"效率": efficiency,"耗材": consumables,"对比": ...} 
        ...    
        }    
        
    }
    :return:
    """

    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr:list[str] = line.strip().split(",")
                user_id:str = arr[0].replace('"', "")
                feature:str = arr[1].replace('"', "")
                efficiency:str = arr[2].replace('"', "")
                consumables:str = arr[3].replace('"', "")
                comparison:str = arr[4].replace('"', "")
                time:str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }
                    

@tool(description="从外部系统中获用户的使用记录，以消息字符串的形式返回，如果未检索到则返回空字符串")
def fetch_external_data(user_id:str,month:str) -> str:
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
            logger.warning(f"未检索到用户{user_id}在{month}的使用记录")

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已经调用"