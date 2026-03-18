# Electron Frontend

## 安装

在项目根目录执行：

```bash
cd electron
npm install
```

## 启动

```bash
npm start
```

启动后 Electron 会优先检测 `http://127.0.0.1:7860` 是否已有后端服务。
如果未检测到，会自动尝试在项目根目录拉起：

```bash
python -m app.main
```

可选环境变量：
- `BACKEND_URL`：后端地址（默认 `http://127.0.0.1:7860`）
- `BACKEND_STARTUP_TIMEOUT_MS`：后端启动超时毫秒数（默认 `45000`）
- `PYTHON_EXE`：指定 Python 可执行路径
