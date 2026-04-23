# main_window.py - 工业级UI重构版(零重叠·不改后台·最终版)
import sys
import os
import re
import logging
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton,
    QTextEdit, QProgressBar, QGroupBox, QListWidget,
    QMessageBox, QSystemTrayIcon, QMenu,
    QCheckBox, QSpinBox, QFileDialog, QCompleter,
)
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QTextCursor
from PySide6.QtCore import QStringListModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_downloader import EmailDownloader
from config import load_config, save_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("main")

# ==============================================
# 工业级 QSS 样式(统一·整洁·无挤压)
# ==============================================
QSS = """
* {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
    color: #2c3e50;
}

#MainWindow {
    background-color: #f5f7fa;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    margin-top: 10px;
    padding: 16px;
    font-weight: bold;
    color: #303133;
}

QLabel#formLabel {
    min-width: 110px;
    font-weight: 500;
    qproperty-alignment: AlignRight | AlignVCenter;
}

QLineEdit {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 8px 10px;
    min-height: 34px;
    background-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #409eff;
    background-color: #f0f7ff;
}

QPushButton {
    border-radius: 4px;
    min-height: 36px;
}
QPushButton#primary {
    background-color: #409eff;
    color: #ffffff;
    border: none;
    font-weight: 500;
}
QPushButton#primary:hover {
    background-color: #66b1ff;
}
QPushButton#primary:disabled {
    background-color: #a0cfff;
}

QPushButton#secondary {
    background-color: #ffffff;
    border: 1px solid #dcdfe6;
}
QPushButton#secondary:hover {
    background-color: #f5f7fa;
    border-color: #c0c4cc;
}

QPushButton#danger {
    background-color: #ffffff;
    border: 1px solid #f56c6c;
    color: #f56c6c;
}
QPushButton#danger:hover {
    background-color: #fef0f0;
}

QListWidget {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    min-height: 80px;
}

QTextEdit#log {
    background-color: #fafafa;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    font-family: Consolas;
    font-size: 13px;
}

QProgressBar {
    background-color: #e4e7ed;
    border: none;
    height: 6px;
    border-radius: 3px;
}
QProgressBar::chunk {
    background-color: #409eff;
    border-radius: 3px;
}

QRadioButton {
    spacing: 6px;
}

QCheckBox {
    spacing: 6px;
    color: #606266;
}

QScrollBar:vertical {
    width: 8px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #c0c4cc;
    border-radius: 4px;
    min-height: 20px;
}
"""

# ==============================================
# 下载线程(完全不动·原样保留)
# ==============================================
class DownloadThread(QThread):
    sig_log = Signal(str)
    sig_progress = Signal(int, int)
    sig_finished = Signal(int, int)
    sig_error = Signal(str)

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        self._stop_flag = False
        self._downloader = None

    def stop(self):
        self._stop_flag = True
        if self._downloader:
            self._downloader.stop()

    def run(self):
        try:
            self._downloader = EmailDownloader(
                email=self.kwargs["email"],
                auth_code=self.kwargs.get("auth_code", ""),
                sender=self.kwargs.get("sender", ""),
                subject_keywords=self.kwargs.get("subject_keywords", []),
                allow_exts=self.kwargs.get("allow_exts", [".pdf"]),
                save_dir=self.kwargs["save_dir"],
                check_days=self.kwargs.get("check_days", 30),
                progress_callback=lambda d, t: self.sig_progress.emit(d, t),
                status_callback=lambda msg: self.sig_log.emit(msg),
            )
            down, skip = self._downloader.run(stop_flag=lambda: self._stop_flag)
            self.sig_finished.emit(down, skip)
        except Exception as e:
            self.sig_error.emit(str(e))

# ==============================================
# 主窗口(UI 100% 重构·逻辑 0 修改)
# ==============================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.cfg = load_config()
        self._thread = None

        self.setWindowTitle("账单附件下载器 v1.0")
        self.setMinimumSize(700, 850)
        self._init_ui()
        self._setup_tray()
        self._load_config()
        self._bind_events()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        main_layout.addWidget(self._group_email())
        main_layout.addWidget(self._group_settings())
        main_layout.addLayout(self._action_bar())
        main_layout.addWidget(self._group_log(), stretch=1)
        main_layout.addWidget(self._footer())

    # ===================== 邮箱配置(不重叠·标准行) =====================
    def _group_email(self):
        g = QGroupBox("📧 邮箱配置")
        v = QVBoxLayout(g)
        v.setSpacing(16)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("例如:yourname@126.com")
        self._setup_email_completer()
        v.addLayout(self._form_line("邮箱地址", self.email_edit, required=True))

        self.radio_auth = QRadioButton("授权码登录")
        self.radio_auth.setChecked(True)
        row_login = QHBoxLayout()
        row_login.addWidget(self.radio_auth)
        row_login.addStretch()
        v.addLayout(self._form_line("登录方式", row_login))

        self.auth_edit = QLineEdit()
        self.auth_edit.setPlaceholderText("IMAP 授权码(非登录密码)")
        self.auth_edit.setEchoMode(QLineEdit.Password)
        v.addLayout(self._form_line("授权码", self.auth_edit, required=True))

        self.dir_edit = QLineEdit()
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.clicked.connect(self._select_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.dir_edit, stretch=1)
        dir_row.addWidget(self.browse_btn)
        v.addLayout(self._form_line("保存目录", dir_row, required=True))

        return g

    # ===================== 下载设置(每行独立) =====================
    def _group_settings(self):
        g = QGroupBox("⚙️ 下载设置")
        v = QVBoxLayout(g)
        v.setSpacing(16)

        self.sender_edit = QLineEdit()
        self.sender_edit.setPlaceholderText("输入银行简称或邮箱,如:广发、招行、cmbchina")
        v.addLayout(self._form_line("发件人过滤", self.sender_edit))
        self._setup_sender_completer()

        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("多个关键词用空格或逗号分隔,例如:账单, 消费, 还款")
        v.addLayout(self._form_line("主题关键词", self.kw_edit))

        self.ext_edit = QLineEdit(".pdf")
        v.addLayout(self._form_line("文件类型", self.ext_edit))

        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setSuffix(" 天")
        v.addLayout(self._form_line("查询范围", self.days_spin))

        return g

    # ===================== 按钮栏 =====================
    def _action_bar(self):
        lay = QHBoxLayout()
        lay.setSpacing(10)

        self.start_btn = QPushButton("▶ 开始下载")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setObjectName("secondary")
        self.stop_btn.setEnabled(False)
        self.save_btn = QPushButton("💾 保存配置")
        self.save_btn.setObjectName("secondary")
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setObjectName("danger")

        lay.addWidget(self.start_btn)
        lay.addWidget(self.stop_btn)
        lay.addWidget(self.save_btn)
        lay.addWidget(self.clear_btn)
        return lay

    # ===================== 日志 =====================
    def _group_log(self):
        g = QGroupBox("📋 运行日志")
        v = QVBoxLayout(g)
        self.pro_bar = QProgressBar()
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        v.addWidget(self.pro_bar)
        v.addWidget(self.log_view, stretch=1)
        return g

    # ===================== 底部 =====================
    def _footer(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        self.status_lab = QLabel("就绪")
        self.tray_check = QCheckBox("关闭时最小化到托盘")
        lay.addWidget(self.status_lab)
        lay.addStretch()
        lay.addWidget(self.tray_check)
        lay.addWidget(QLabel("v1.0"))
        return w

    # ===================== 核心:绝对不重叠的表单行 =====================
    # ---- 发件人银行简称自动补全 ----

    # 银行简称/别名 → 官方信用卡邮箱(主流银行白名单)
    _BANK_SENDERS = [
        # ===== 国有六大行 =====
        # 工商银行
        ("工商银行", "creditcard@icbc.com.cn"),
        ("工行", "creditcard@icbc.com.cn"),
        ("icbc", "creditcard@icbc.com.cn"),
        ("工商银行备用", "ebank@icbc.com.cn"),
        # 建设银行
        ("建设银行", "creditcardbill@ccb.com"),
        ("建行", "creditcardbill@ccb.com"),
        ("ccb", "creditcardbill@ccb.com"),
        ("建设银行备用", "statement@ccb.com"),
        # 中国银行
        ("中国银行", "personalservice@bank-of-china.com"),
        ("中行", "personalservice@bank-of-china.com"),
        ("boc", "personalservice@bank-of-china.com"),
        # 农业银行
        ("农业银行", "creditcard@abchina.com"),
        ("农行", "creditcard@abchina.com"),
        ("abchina", "creditcard@abchina.com"),
        # 交通银行
        ("交通银行", "creditcard@bankcomm.com"),
        ("交行", "creditcard@bankcomm.com"),
        ("bankcomm", "creditcard@bankcomm.com"),
        ("交通银行备用", "bill@bankcomm.com"),
        # 邮储银行
        ("邮储银行", "creditcardcenter@cardmail.psbc.com"),
        ("邮储", "creditcardcenter@cardmail.psbc.com"),
        ("psbc", "creditcardcenter@cardmail.psbc.com"),
        ("邮储银行备用", "creditcardcenter@cardmail.psbcltd.cn"),

        # ===== 股份制商业银行 =====
        # 招商银行
        ("招商银行", "creditcard@cmbchina.com"),
        ("招行", "creditcard@cmbchina.com"),
        ("cmbchina", "creditcard@cmbchina.com"),
        ("招商银行备用", "ccsvc@message.cmbchina.com"),
        ("招商银行备用2", "card@mail.cmbchina.com"),
        # 广发银行
        ("广发银行", "creditcard@cgbchina.com.cn"),
        ("广发", "creditcard@cgbchina.com.cn"),
        ("cgbchina", "creditcard@cgbchina.com.cn"),
        # 浦发银行
        ("浦发银行", "estmtservice@eb.spdb.com.cn"),
        ("浦发", "estmtservice@eb.spdb.com.cn"),
        ("spdb", "estmtservice@eb.spdb.com.cn"),
        # 中信银行
        ("中信银行", "citiccard@citiccard.com"),
        ("中信", "citiccard@citiccard.com"),
        ("citiccard", "citiccard@citiccard.com"),
        # 民生银行
        ("民生银行", "creditcard@cmbc.com.cn"),
        ("民生", "creditcard@cmbc.com.cn"),
        ("cmbc", "creditcard@cmbc.com.cn"),
        # 平安银行
        ("平安银行", "creditcard@18ebank.com"),
        ("平安", "creditcard@18ebank.com"),
        ("18ebank", "creditcard@18ebank.com"),
        # 华夏银行
        ("华夏银行", "admin@creditcardmail.hxb.com.cn"),
        ("华夏", "admin@creditcardmail.hxb.com.cn"),
        ("hxb", "admin@creditcardmail.hxb.com.cn"),
        # 兴业银行
        ("兴业银行", "creditcard@cib.com.cn"),
        ("兴业", "creditcard@cib.com.cn"),
        ("cib", "creditcard@cib.com.cn"),
        # 光大银行
        ("光大银行", "creditcard@cebbank.com"),
        ("光大", "creditcard@cebbank.com"),
        ("cebbank", "creditcard@cebbank.com"),
    ]

    # 去重后的邮箱列表(completer 数据源)
    _SENDER_ADDRESSES = list(dict.fromkeys(addr for _, addr in _BANK_SENDERS))

    def _setup_sender_completer(self):
        """发件人输入框:输入银行简称自动补全官方邮箱"""
        model = QStringListModel(self._SENDER_ADDRESSES)
        completer = QCompleter()
        completer.setModel(model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(8)
        self.sender_edit.setCompleter(completer)
        self.sender_edit.textChanged.connect(self._on_sender_text_changed)

    def _on_sender_text_changed(self, text: str):
        """输入银行简称时,动态过滤并补全为官方邮箱地址"""
        text = text.strip()
        if not text or "@" in text:
            self._sender_completer_model().setStringList(self._SENDER_ADDRESSES)
            return
        low = text.lower()
        matched = list({
            addr for name, addr in self._BANK_SENDERS
            if low in name or low in addr
        })
        self._sender_completer_model().setStringList(matched)

    def _sender_completer_model(self):
        """获取发件人 completer 的 model"""
        c = self.sender_edit.completer()
        return c.model() if c else QStringListModel()

    # ---- 邮箱自动补全 ----

    _EMAIL_DOMAINS = [
        "@qq.com", "@163.com", "@126.com", "@188.com",
        "@gmail.com", "@outlook.com", "@hotmail.com",
        "@sina.com", "@sohu.com", "@foxmail.com",
        "@yeah.net", "@139.com", "@aliyun.com",
    ]

    def _setup_email_completer(self):
        """邮箱输入框自动补全:输入 @ 后弹出主流后缀"""
        self._email_completer_model = QStringListModel()
        completer = QCompleter()
        completer.setModel(self._email_completer_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(8)
        self.email_edit.setCompleter(completer)
        self.email_edit.textChanged.connect(self._on_email_text_changed)

    def _on_email_text_changed(self, text: str):
        """根据当前输入动态生成补全列表"""
        at_pos = text.find("@")
        if at_pos < 0:
            # 还没输入 @,用前缀 + 所有域名
            if not text:
                self._email_completer_model.setStringList([])
                return
            suggestions = [text + d for d in self._EMAIL_DOMAINS]
        else:
            # 已输入 @,用前缀 + 匹配的域名
            prefix = text[:at_pos + 1]
            partial = text[at_pos + 1:].lower()
            suggestions = [
                prefix + d[1:] for d in self._EMAIL_DOMAINS
                if d.lower().startswith("@" + partial) or partial == ""
            ]
        self._email_completer_model.setStringList(suggestions)

    def _form_line(self, label_text, content, required=False):
        """创建一行:标签 + 内容。

        content 可以是 QWidget 或 QLayout,统一返回 QVBoxLayout。
        """
        line = QVBoxLayout()
        line.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(10)

        mark = '<span style="color:#C53030;font-weight:bold;">*</span>' if required else ""
        lab = QLabel(f"{mark} {label_text}")
        lab.setObjectName("formLabel")
        top.addWidget(lab)

        # 关键:区分 Widget 和 Layout
        if isinstance(content, QWidget):
            top.addWidget(content, stretch=1)
        else:
            top.addLayout(content, stretch=1)

        line.addLayout(top)
        return line

    # ===================== 以下所有逻辑:完全不动 =====================
    def _bind_events(self):
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.save_btn.clicked.connect(self._save_config)
        self.clear_btn.clicked.connect(self.log_view.clear)


    def _setup_tray(self):
        self.tray = QSystemTrayIcon()
        px = QPixmap(16,16)
        px.fill(QColor("#409eff"))
        self.tray.setIcon(QIcon(px))
        menu = QMenu()
        menu.addAction("显示窗口", self.show)
        menu.addAction("退出", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _select_dir(self):
        start_dir = self.dir_edit.text().strip()
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = ""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", start_dir)
        if path: self.dir_edit.setText(path)



    def _validate(self):
        email = self.email_edit.text().strip()
        auth = self.auth_edit.text().strip()
        folder = self.dir_edit.text().strip()
        if not email:
            QMessageBox.warning(self,"提示","请输入邮箱")
            return False
        if not auth:
            QMessageBox.warning(self,"提示","请输入授权码")
            return False
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self,"提示","保存目录无效")
            return False
        return True

    def _start(self):
        if not self._validate(): return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_lab.setText("下载中...")
        self.pro_bar.setVisible(True)

        kws = [k.strip() for k in re.split(r'[,\s,]+', self.kw_edit.text()) if k.strip()]
        exts = [e.strip() for e in self.ext_edit.text().split() if e.startswith(".")] or [".pdf"]

        self._thread = DownloadThread(
            email=self.email_edit.text().strip(),
            auth_code=self.auth_edit.text().strip(),
            sender=self.sender_edit.text().strip(),
            subject_keywords=kws,
            allow_exts=exts,
            save_dir=self.dir_edit.text().strip(),
            check_days=self.days_spin.value()
        )
        self._thread.sig_log.connect(self._log)
        self._thread.sig_progress.connect(self._update_progress)
        self._thread.sig_finished.connect(self._done)
        self._thread.sig_error.connect(self._err)
        self._thread.start()

    def _stop(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(2000)
        self._reset()

    def _log(self, msg):
        self.log_view.append(msg)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _update_progress(self, processed, total):
        """进度条更新:设置最大值和当前值"""
        self.pro_bar.setMaximum(total)
        self.pro_bar.setValue(processed)

    def _done(self, down, skip):
        self._log(f"✅ 完成:新文件 {down} 个,跳过 {skip} 个")
        self._reset()

    def _err(self, msg):
        self._log(f"❌ 错误:{msg}")
        self._reset()

    def _reset(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_lab.setText("就绪")
        QTimer.singleShot(1500, lambda: self.pro_bar.setVisible(False))

    def _save_config(self):
        cfg = {
            "email": self.email_edit.text().strip(),
            "auth_code": self.auth_edit.text().strip(),
            "save_dir": self.dir_edit.text().strip(),
            "sender": self.sender_edit.text().strip(),
            "subject_keywords": [k.strip() for k in re.split(r'[,\s，]+', self.kw_edit.text()) if k.strip()],
            "check_days": self.days_spin.value(),
            "allow_exts": self.ext_edit.text().strip(),
            "minimize_to_tray": self.tray_check.isChecked()
        }
        save_config(cfg)
        QMessageBox.information(self,"成功","配置已保存")

    def _load_config(self):
        c = self.cfg
        self.email_edit.setText(c.get("email",""))
        self.auth_edit.setText(c.get("auth_code",""))
        self.dir_edit.setText(c.get("save_dir",""))
        self.sender_edit.setText(c.get("sender",""))
        self.kw_edit.setText(", ".join(c.get("subject_keywords", [])))
        self.days_spin.setValue(c.get("check_days",30))
        exts = c.get("allow_exts", [".pdf"])
        self.ext_edit.setText(" ".join(exts) if isinstance(exts, list) else str(exts))
        self.tray_check.setChecked(c.get("minimize_to_tray",True))

    def closeEvent(self, e):
        if self._thread and self._thread.isRunning():
            if QMessageBox.question(self,"提示","下载中,确定退出?") != QMessageBox.Yes:
                e.ignore()
                return
        if self.tray_check.isChecked():
            self.hide()
            e.ignore()
        else:
            e.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
