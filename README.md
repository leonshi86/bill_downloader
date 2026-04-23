# 账单附件下载器

## 项目结构

```
E:\bill_downloader\
├── config.py             # 配置读写（JSON）
├── email_downloader.py   # 邮箱连接 + 附件下载核心
├── main_window.py        # PySide6 图形界面
├── main.py               # 程序入口
├── requirements.txt      # Python 依赖
├── bill_downloader.spec  # PyInstaller 打包配置
└── README.md
```

## 依赖安装

```bash
pip install PySide6
```

## 运行

```bash
python main.py
```

## 打包成 EXE（Windows）

```bash
# 安装打包工具
pip install pyinstaller

# 打包
pyinstaller bill_downloader.spec

# 输出目录: dist\bill_downloader\
# 双击 bill_downloader.exe 即可运行
```

## 功能说明

| 功能 | 说明 |
|------|------|
| 授权码登录 | 支持 126/163/QQ 等主流邮箱的 IMAP 授权码 |
| 发件人过滤 | 支持按发件人地址精确过滤 |
| 主题词过滤 | 支持多关键词（OR 组合） |
| 附件类型过滤 | 支持 .pdf/.zip/.xlsx 等多类型 |
| 时间范围 | 支持指定最近 N 天 |
| 配置持久化 | 配置保存到 config.json |
| 断点续传 | 已下载的文件自动跳过 |
| 托盘运行 | 关闭窗口时最小化到托盘 |

## 授权码获取

### 126 邮箱
1. 登录 mail.126.com
2. 设置 → POP3/SMTP/IMAP → 开启 IMAP/SMTP 服务
3. 获取授权码

### 163 邮箱
同上，服务地址为 mail.163.com

### QQ 邮箱
1. 设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 → 开启 IMAP 服务
2. 获取授权码
