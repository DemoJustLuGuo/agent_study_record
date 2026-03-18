#agent工具

from langchain_core.tools import tool
from rag.rag_service import RAGSummarizeService
from rag.memory_service import LongTermMemoryService
from utils.config_handler import agent_conf
from utils.path_tools import get_abs_path
from utils.log import logger

import json
import os
import shutil
import subprocess
import sys
import tempfile
from html import unescape
from typing import Optional
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

rag = RAGSummarizeService()
memory = LongTermMemoryService()
external_data = {}
TOOL_TIMEOUT_SECONDS = 30
TOOL_OUTPUT_MAX_CHARS = 6000
WEB_SEARCH_TIMEOUT_SECONDS = 15
BING_CN_SEARCH_URL = "https://cn.bing.com/search?q="


def _truncate_output(text:str) -> str:
    if len(text) <= TOOL_OUTPUT_MAX_CHARS:
        return text
    return text[:TOOL_OUTPUT_MAX_CHARS] + "\n...[输出过长，已截断]"


def _run_subprocess(command:list[str], tool_name:str) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=get_abs_path(""),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"【失败】{tool_name}执行超时（>{TOOL_TIMEOUT_SECONDS}s）"
    except Exception as e:
        logger.error(f"{tool_name}执行失败: {str(e)}", exc_info=True)
        return f"【失败】{tool_name}执行异常: {str(e)}"

    parts:list[str] = [
        f"tool={tool_name}",
        f"exit_code={completed.returncode}",
    ]

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if stdout:
        parts.append("stdout:\n" + stdout)
    if stderr:
        parts.append("stderr:\n" + stderr)
    if not stdout and not stderr:
        parts.append("stdout/stderr为空")

    return _truncate_output("\n".join(parts))


def _resolve_matlab_runtime() -> Optional[tuple[str, str]]:
    matlab_exe = (os.environ.get("MATLAB_EXE") or "").strip()
    if matlab_exe:
        if os.path.exists(matlab_exe):
            return "matlab", matlab_exe
        logger.warning(f"环境变量MATLAB_EXE指向路径不存在: {matlab_exe}")

    matlab_path = shutil.which("matlab")
    if matlab_path:
        return "matlab", matlab_path

    octave_cli_path = shutil.which("octave-cli")
    if octave_cli_path:
        return "octave", octave_cli_path

    octave_path = shutil.which("octave")
    if octave_path:
        return "octave", octave_path

    return None


def _load_text_from_url(url:str, timeout:int) -> Optional[str]:
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"

            return response.read().decode(encoding, errors="replace")
    except URLError as e:
        logger.warning(f"联网请求失败: {str(e)}")
    except Exception as e:
        logger.warning(f"联网请求异常: {str(e)}")
    return None


def _parse_bing_rss_items(rss_text:str, max_items:int=5) -> list[str]:
    try:
        root = ET.fromstring(rss_text)
    except ET.ParseError as e:
        logger.warning(f"必应RSS解析失败: {str(e)}")
        return []

    snippets:list[str] = []
    items = root.findall("./channel/item")

    rank = 1
    for item in items:
        if rank > max_items:
            break

        title = unescape((item.findtext("title") or "").strip())
        link = unescape((item.findtext("link") or "").strip())
        desc = unescape((item.findtext("description") or "").strip())

        title = " ".join(title.split())
        desc = " ".join(desc.split())
        link = " ".join(link.split())

        if not title:
            continue

        if desc and link:
            snippets.append(f"{rank}. {title} - {desc} ({link})")
        elif desc:
            snippets.append(f"{rank}. {title} - {desc}")
        elif link:
            snippets.append(f"{rank}. {title} ({link})")
        else:
            snippets.append(f"{rank}. {title}")
        rank += 1

    return snippets

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str) -> str:
    return rag.rag_summarize(query)


@tool(description="联网搜索公开信息并返回前几条结果摘要，适用于标准、术语、参数范围、行业资料快速核验")
def web_search(query:str) -> str:
    query = (query or "").strip()
    if not query:
        return "【失败】web_search查询为空"

    bing_rss_url = BING_CN_SEARCH_URL + quote(query) + "&format=rss&setlang=zh-cn"
    rss_text = _load_text_from_url(bing_rss_url, timeout=WEB_SEARCH_TIMEOUT_SECONDS)
    if rss_text is None:
        return "【失败】web_search联网请求失败，请稍后重试"

    snippets = _parse_bing_rss_items(rss_text, max_items=5)

    if not snippets:
        return "【成功】web_search已执行（必应中国RSS），但未检索到可用摘要结果"

    return _truncate_output("\n".join(snippets))

@tool(description="执行Python代码并返回执行结果，适用于通信算法快速计算、验证与仿真")
def python(code:str) -> str:
    code = (code or "").strip()
    if not code:
        return "【失败】python代码为空"

    return _run_subprocess(
        [sys.executable, "-c", code],
        tool_name="python",
    )


@tool(description="执行MATLAB代码并返回执行结果；若未安装MATLAB将自动尝试Octave")
def matlab(code:str) -> str:
    code = (code or "").strip()
    if not code:
        return "【失败】matlab代码为空"

    runtime = _resolve_matlab_runtime()
    if runtime is None:
        return "【失败】未检测到MATLAB/Octave可执行程序，请安装后重试，或设置环境变量MATLAB_EXE。"

    runtime_type, runtime_exe = runtime
    temp_script = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".m", encoding="utf-8", delete=False) as f:
            temp_script = f.name
            f.write(code)

        script_path = temp_script.replace("\\", "/").replace("'", "''")

        if runtime_type == "matlab":
            batch_cmd = f"try, run('{script_path}'); catch ME, disp(getReport(ME,'extended')); exit(1); end; exit(0);"
            batch_result = _run_subprocess([runtime_exe, "-batch", batch_cmd], tool_name="matlab")

            if "-batch" in batch_result and "option" in batch_result.lower():
                legacy_cmd = f"try, run('{script_path}'); catch ME, disp(getReport(ME,'extended')); end; exit;"
                return _run_subprocess(
                    [runtime_exe, "-nosplash", "-nodesktop", "-r", legacy_cmd],
                    tool_name="matlab",
                )

            return batch_result

        octave_cmd = f"run('{script_path}');"
        return _run_subprocess(
            [runtime_exe, "--quiet", "--eval", octave_cmd],
            tool_name="octave",
        )
    finally:
        if temp_script and os.path.exists(temp_script):
            os.remove(temp_script)

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
                    

@tool(description="从外部系统中获取用户的使用记录，返回JSON字符串；如果未检索到则返回空字符串")
def fetch_external_data(user_id:str,month:str) -> str:
    generate_external_data()

    user_records = external_data.get(user_id, {})
    record = user_records.get(month)
    if record is None:
        logger.warning(f"未检索到用户{user_id}在{month}的使用记录")
        return ""

    return json.dumps(record, ensure_ascii=False)

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已经调用"


@tool(description="将用户偏好或项目笔记写入长期向量记忆，支持指定user_id、scope、project标签")
def store_memory(note:str, user_id:str="global", scope:str="preference", project:str="") -> str:
    return memory.add_memory(note=note, user_id=user_id, scope=scope, project=project)


@tool(description="按query检索长期向量记忆，可按user_id、project过滤，返回相关记忆摘要")
def search_memory(query:str, user_id:str="global", project:str="") -> str:
    return memory.search_memory(query=query, user_id=user_id, project=project)
