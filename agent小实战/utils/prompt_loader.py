from config_handler import prompts_conf
from path_tools import get_abs_path
from log import logger

def load_system_prompt():
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompt]在yaml配置下没有main_prompt_path配置项")
        raise e
    
    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompt]加载系统提示词失败: {str(e)}")
        raise e

def load_report_prompt():
    try:
        report_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompt]在yaml配置下没有report_prompt_path配置项")
        raise e
    
    try:
        return open(report_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompt]加载报告提示词失败: {str(e)}")
        raise e

def load_rag_prompt():
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompt]在yaml配置下没有rag_summarize_prompt_path配置项")
        raise e
    
    try:
        return open(rag_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]解析RAG提示词出错: {str(e)}")
        raise e

if __name__ == "__main__":
    print(load_system_prompt())
    print(load_report_prompt())
    print(load_rag_prompt())
