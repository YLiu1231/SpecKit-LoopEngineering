# 开发与验证

运行时入口安装为 `.specify/scripts/loopctl.py`，调用同目录 `loop_runtime` 包。源代码位于 `runtime/loop_runtime/`，安装器 capsule 仍在 `runtime/*.py.md`。只依赖 Python 3.9+ 标准库及本地 Git。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
sh -n install.sh
git diff --check
```

测试创建临时真实 Git 仓库，并实际运行案例适配器；不会连接外网、修改真实全局 Claude 配置或发布项目。完整用例包含本仓上下文、全功能执行与漂移、预算、双仓契约/回执、发版与回滚、四阶段准出及隔离安装。人工业务语义评审、真实企业系统联调和原生 Windows 运行另行验证，不能由本套夹具结果替代。

协议版本未知、路径逃逸、符号链接、摘要不符和合成样例不能当作有效证据。配置/确认记录是本地可审计资料；没有签名认证、防篡改服务或中央权限系统。项目方仍负责完整案例目录、断言、行为输入范围与授权来源的真实性。
