# oc2api Deploy SOP — 标准部署流程

## 核心原则
**所有 oc2api 的改动，最后一步必须运行 `bash build.sh deploy <port>`，不得手动分离步骤。**
该命令自动完成：bump version → git commit+push → build → rsync → systemd restart jpkbb。

## 前置条件
- 代码改动已完成、go build 可通过
- 当前目录: `/home/moclaw/projects/oc2api/`
- 远程目标: jpkbb (root@100.127.66.71, Tailscale)
- 默认端口: 8000

## 步骤

### 1. 确保改动完整
```bash
cd /home/moclaw/projects/oc2api
git status          # 确认改动符合预期
go build .         # 确保能编译通过（可选，build.sh 也会做）
```

### 2. 执行一键部署
```bash
bash build.sh deploy 8000
```
build.sh 自动做：
1. **bump version** — version.txt 中 patch +1（v3.003 → v3.004）
2. **git commit + push** — 包含所有改动，commit message 含版本号
3. **build** — Go 编译，注入 commit hash + date
4. **deploy** — rsync -z 上传 → systemd stop → symlink update → systemd start → health check

### 3. 验证
```bash
# 检查 GUI 版本显示
curl -s http://100.127.66.71:8000/api/config | python3 -m json.tool
# 预期: build_version = v3.xxx, build_commit = short hash(如 a1b2c3d), build_time = 当天日期
# ⚠️ build_commit 不能为空！若为空 → ldflags 未正确注入，检查 build.sh 的 -X main.buildCommit=${COMMIT}
```

### 4. Deploy 总结（必须报告）
部署完成后，输出版本摘要：
```
v3.xxx a1b2c3d (2026-06-22)
```
格式：`v{major}.{patch} {short_hash} ({date})`
- 从 `build_version` + `build_commit` + `build_time` 拼接
- 此摘要记录到 `global_mem.txt` 的 `## Recent` 节

## 禁止事项
- ❌ **不要手动 `go build` + scp** — 会跳过 version bump 和 ldflags hash 注入，导致 `build_commit=""`、版本号不更新
- ❌ **不要手动改 version.txt**
- ❌ **不要手动 git add/commit/push**（build.sh 代劳）
- ❌ **不要手动上传二进制或手动操作进程（用 build.sh deploy）**
- ❌ **不要 deploy 到 localhost 或其他地址**
- ❌ **admin/index.html 是 embedded 的** — 改完跑 build.sh deploy，不要单独 scp（没用）

## 版本号规则
- 格式: `v{major}.{patch}`，如 `v3.004`
- major 跟随大版本（当前 3），patch 自动递增（build.sh 每次 +1）
- 版本号注入位置: version.txt（运行时读取）+ 二进制名（opencode2api_v3.004）
- GUI 显示: `v3.xxx + short hash + date`

## 故障处理
| 问题 | 处理方式 |
|------|---------|
| go build 失败 | 检查代码错误，修复后重试 |
| git push 失败 | 可能远程有冲突，手动 `git pull --rebase` 后重试 |
| rsync/SSH 连接失败 | 检查 Tailscale 连通性: `ping 100.127.66.71` |
| health check 失败 | ssh 到 jpkbb 看日志: `tail -20 /tmp/oc2api-v{port}.log` |
| **build.sh deploy 后版本未更新** | build.sh 的 systemd restart 可能未生效（旧进程仍在跑）。手动: `systemctl restart oc2api.service`（**不是** opencode2api）|
| SSH 到 jpkbb 查看进程 | `ssh root@100.127.66.71 'systemctl status oc2api.service --no-pager'`，确认 PID 是新的|

## 附加知识 (2026-06-18)

### jpkbb 服务管理
- systemd unit: **`oc2api.service`**（不是 `opencode2api`）
- 二进制: `/opt/oc2api/opencode2api` → symlink 指向 `./opencode2api_v3.XXX`
- 版本文件: `/opt/oc2api/version.txt`
- 验证版本: `cat /opt/oc2api/version.txt`

### 服务器 timezone
- jpkbb 已改为 `Asia/Hong_Kong` (HKT, UTC+8)
- 改时区: `timedatectl set-timezone Asia/Hong_Kong`
- 原时区: America/New_York (EDT, UTC-5)
- **Console Log 时间**: 后端用 `time.Now().In(time.FixedZone("HKT", 8*3600)).Format("01-02 15:04:05")` 双重保障

### config.json 同步 (2026-06-21)
- **build.sh 只部署 admin/，不部署 config.json** — deploy时自动rsync admin/到远程
- 部署内容: binary + version.txt + admin/ 目录
- ⚠️ **远程config.json是真相源** — GUI保存会修改远程config，本地config.json可能过时
- 如需手动同步proip节点到远程: SSH直接merge，不要用build.sh覆盖
- 验证: `curl -sf http://100.127.66.71:8000/api/proip-stats` 看节点数据

### admin/index.html 重排section注意事项 (2026-06-21)
- **重排后必须验证div平衡**: `content.count('<div') == content.count('</div>')`
- **section移动时确保整个div块完整移动** — 注释+div都要一起，不能只移动注释
- **从card内部拆分sub-section**: 需计算opens/closes差异，补/删多余的`</div>`
- **热力图setInterval不要低于30s** — 5s会overwhelm浏览器
- PROIP节点ID是2字母大写(SG/DE/FR等)，modeOf需匹配`/^[A-Z]{2}$/`
- proip-stats API用`status`字段(值为"healthy"/"dead")，不是`healthy`布尔值
