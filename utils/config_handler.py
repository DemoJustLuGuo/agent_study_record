from utils.path_tools import get_abs_path
import yaml


def load_chroma_config(
    config_path: str = get_abs_path("rag/config/chroma.yml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_prompts_config(
    config_path: str = get_abs_path("agent/config/prompts.yml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_agent_config(
    config_path: str = get_abs_path("model/config/agent.yml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()

if __name__ == "__main__":
    print(agent_conf["chat_model_name"])
