# email_downloader.py — 邮件下载核心逻辑（imaplib）

import imaplib
import ssl
import logging
import time
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

logger = logging.getLogger("email_downloader")


def decode_str(s: str) -> str:
    """解码 MIME 字符串，兼容各种编码"""
    if s is None:
        return ""
    try:
        decoded_parts = decode_header(s)
        result = []
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                if charset:
                    result.append(content.decode(charset, errors="ignore"))
                else:
                    for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
                        try:
                            result.append(content.decode(enc))
                            break
                        except Exception:
                            continue
                    else:
                        result.append(content.decode("utf-8", errors="ignore"))
            else:
                result.append(str(content))
        return "".join(result)
    except Exception:
        return str(s) if s else ""


class EmailDownloader:
    """邮件下载器（IMAP 授权码方式）"""

    # IMAP 服务器配置（常见邮箱）
    IMAP_SERVERS = {
        "126": "imap.126.com",
        "163": "imap.163.com",
        "qq": "imap.qq.com",
        "sina": "imap.sina.com",
        "outlook": "imap-mail.outlook.com",
        "gmail": "imap.gmail.com",
        "aliyun": "imap.aliyun.com",
    }

    # 信用卡账单默认主题关键词
    DEFAULT_SUBJECT_KEYWORDS = [
        "账单", "信用卡账单", "电子账单", "月度账单",
        "还款账单", "消费账单", "月结单", "对账单",
        "CMB账单", "广发账单", "招行账单", "信用卡对账单",
    ]

    # 银行中文名/简称 → 官方发件邮箱映射（用于发件人过滤）
    _BANK_SENDER_MAP = {
        # 国有六大行
        "工商银行": "creditcard@icbc.com.cn", "工行": "creditcard@icbc.com.cn", "icbc": "creditcard@icbc.com.cn",
        "建设银行": "creditcardbill@ccb.com", "建行": "creditcardbill@ccb.com", "ccb": "creditcardbill@ccb.com",
        "中国银行": "personalservice@bank-of-china.com", "中行": "personalservice@bank-of-china.com", "boc": "personalservice@bank-of-china.com",
        "农业银行": "creditcard@abchina.com", "农行": "creditcard@abchina.com", "abchina": "creditcard@abchina.com",
        "交通银行": "creditcard@bankcomm.com", "交行": "creditcard@bankcomm.com", "bankcomm": "creditcard@bankcomm.com",
        "邮储银行": "creditcardcenter@cardmail.psbc.com", "邮储": "creditcardcenter@cardmail.psbc.com", "psbc": "creditcardcenter@cardmail.psbc.com",
        # 股份制商业银行
        "招商银行": "creditcard@cmbchina.com", "招行": "creditcard@cmbchina.com", "cmbchina": "creditcard@cmbchina.com",
        "广发银行": "creditcard@cgbchina.com.cn", "广发": "creditcard@cgbchina.com.cn", "cgbchina": "creditcard@cgbchina.com.cn",
        "浦发银行": "estmtservice@eb.spdb.com.cn", "浦发": "estmtservice@eb.spdb.com.cn", "spdb": "estmtservice@eb.spdb.com.cn",
        "中信银行": "citiccard@citiccard.com", "中信": "citiccard@citiccard.com", "citiccard": "citiccard@citiccard.com",
        "民生银行": "creditcard@cmbc.com.cn", "民生": "creditcard@cmbc.com.cn", "cmbc": "creditcard@cmbc.com.cn",
        "平安银行": "creditcard@18ebank.com", "平安": "creditcard@18ebank.com", "18ebank": "creditcard@18ebank.com",
        "华夏银行": "admin@creditcardmail.hxb.com.cn", "华夏": "admin@creditcardmail.hxb.com.cn", "hxb": "admin@creditcardmail.hxb.com.cn",
        "兴业银行": "creditcard@cib.com.cn", "兴业": "creditcard@cib.com.cn", "cib": "creditcard@cib.com.cn",
        "光大银行": "creditcard@cebbank.com", "光大": "creditcard@cebbank.com", "cebbank": "creditcard@cebbank.com",
    }

    def __init__(self,
                 email: str,
                 auth_code: str = "",
                 password: str = "",
                 sender: str = "",
                 subject_keywords: list = None,
                 allow_exts: list = None,
                 save_dir: str = "",
                 check_days: int = 30,
                 progress_callback=None,
                 status_callback=None):
        self.email = email
        self.auth_code = auth_code
        self.password = password
        self.sender = sender
        self.subject_keywords = subject_keywords or []
        self.allow_exts = [e.lower() for e in (allow_exts or [".pdf"])]
        self.save_dir = save_dir
        self.check_days = check_days
        self.progress_callback = progress_callback
        self.status_callback = status_callback

        self._mail = None
        self._connected = False
        self._stop_flag = False  # 内部停止标志

    def stop(self) -> None:
        """停止下载"""
        self._stop_flag = True
        logger.info("停止标志已设置")

    def _update_status(self, msg: str) -> None:
        if self.status_callback:
            self.status_callback(msg)
        logger.info(msg)

    def _imap_server(self) -> str:
        """根据邮箱域名推断 IMAP 服务器"""
        domain = self.email.split("@")[1].lower()
        for key, server in self.IMAP_SERVERS.items():
            if domain == key or domain.endswith(f".{key}"):
                return server
        if "qq" in domain:
            return "imap.qq.com"
        if "126" in domain or "163" in domain:
            return "imap.126.com"
        if "aliyun" in domain:
            return "imap.aliyun.com"
        if "outlook" in domain or "hotmail" in domain:
            return "imap-mail.outlook.com"
        return f"imap.{domain}"

    def connect(self) -> bool:
        """连接邮箱服务器"""
        server = self._imap_server()
        self._update_status(f"连接 {server}:993 ...")
        try:
            imaplib.Commands["ID"] = ("AUTH",)

            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self._mail = imaplib.IMAP4_SSL(server, 993, ssl_context=context)
            self._connected = True
            self._update_status(f"✅ 连接成功（{server}）")
            return True
        except Exception as e:
            self._update_status(f"❌ 连接失败: {e}")
            return False

    def login(self) -> bool:
        """登录邮箱"""
        if not self._connected:
            ok = self.connect()
            if not ok:
                return False

        self._update_status(f"登录 {self.email} ...")
        try:
            credential = self.auth_code if self.auth_code else self.password
            self._mail.login(self.email, credential)
            self._update_status("✅ 登录成功")
            self._send_client_id()
            return True
        except Exception as e:
            self._update_status(f"❌ 登录失败: {e}")
            return False

    def _send_client_id(self) -> None:
        """发送 IMAP ID 命令伪装成常见邮件客户端"""
        try:
            client_info = (
                "name", "Thunderbird",
                "version", "115.0",
                "vendor", "Mozilla",
                "contact", self.email,
            )
            id_string = '("' + '" "'.join(client_info) + '")'
            self._mail._simple_command("ID", id_string)
            logger.info("IMAP ID 命令已发送")
        except Exception as e:
            logger.warning("IMAP ID 命令失败（不影响主流程）: %s", e)

    def _select_inbox(self) -> bool:
        """选择收件箱"""
        try:
            result = self._mail.select("INBOX")
            if result[0] != "OK":
                self._update_status(f"❌ 选择收件箱失败: {result[1]}")
                return False
            self._update_status("✅ 收件箱已打开")
            return True
        except Exception as e:
            self._update_status(f"❌ 选择收件箱失败: {e}")
            return False

    def _search_mails(self) -> list:
        """搜索邮件 ID 列表。

        只用 SINCE 做服务端日期过滤，发件人和关键词在客户端逐封匹配
        （IMAP FROM/SUBJECT 搜索对中文不可靠）。
        """
        if self.check_days > 0:
            since_date = self._days_ago(self.check_days)
            criteria = f"SINCE {since_date}"
            self._update_status(f"搜索最近 {self.check_days} 天邮件（{since_date} 之后）")
        else:
            criteria = "ALL"
            self._update_status("搜索全部邮件")

        try:
            status, data = self._mail.search(None, criteria)
            if status != "OK" or not data[0]:
                self._update_status("未找到邮件")
                return []
            mail_ids = data[0].split()
            self._update_status(f"找到 {len(mail_ids)} 封邮件")
            return mail_ids
        except Exception as e:
            self._update_status(f"❌ 搜索失败: {e}")
            return []

    @staticmethod
    def _days_ago(n: int) -> str:
        """返回 N 天前的日期字符串（IMAP 格式: dd-Mon-YYYY）"""
        d = datetime.now() - timedelta(days=n)
        return d.strftime("%d-%b-%Y")

    def _fetch_with_retry(self, mail_id, retries: int = 3):
        """带重试的邮件获取"""
        for i in range(retries):
            try:
                status, data = self._mail.fetch(mail_id, "(RFC822)")
                if status == "OK" and data:
                    return status, data
            except Exception as e:
                if i == retries - 1:
                    raise
                time.sleep(1)
        return None, None

    def _parse_email(self, msg_data: bytes) -> tuple:
        """解析邮件，返回 (from, subject, date_str, msg)"""
        parser = BytesParser()
        msg = parser.parsebytes(msg_data)
        from_ = decode_str(msg.get("From", ""))
        subject = decode_str(msg.get("Subject", ""))
        date_str = ""
        try:
            dt = parsedate_to_datetime(msg.get("Date", ""))
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return from_, subject, date_str, msg

    def _should_stop(self, external_flag=None) -> bool:
        """检查是否应该停止"""
        return self._stop_flag or (external_flag and external_flag())

    def run(self, save_callback=None, stop_flag=None) -> tuple:
        """
        执行下载，返回 (downloaded_count, skipped_count)
        save_callback(msg, filename) — 每处理一封邮件时回调
        stop_flag() — 返回 True 时停止下载
        """
        self._stop_flag = False  # 重置停止标志

        if not self.login():
            return 0, 0

        if not self._select_inbox():
            self.disconnect()
            return 0, 0

        mail_ids = self._search_mails()
        if not mail_ids:
            self.disconnect()
            return 0, 0

        downloaded = 0
        skipped = 0
        total = len(mail_ids)
        processed = 0
        exist_files = self._existing_files()

        for mail_id in reversed(mail_ids):
            # 检查停止标志
            if self._should_stop(stop_flag):
                self._update_status("⚠ 用户停止下载")
                break

            try:
                status, msg_data = self._fetch_with_retry(mail_id)
                if not status or not msg_data:
                    self._update_status(f"⚠ 获取邮件失败，跳过")
                    skipped += 1
                    continue

                from_, subject, date_str, msg = self._parse_email(msg_data[0][1])

                # 发件人过滤（大小写不敏感子串匹配）
                if self.sender and not self._is_sender_matched(from_):
                    skipped += 1
                    continue

                # 主题词过滤（大小写不敏感子串匹配）
                if self.subject_keywords and not self._is_subject_matched(subject):
                    skipped += 1
                    continue

                # 客户端日期二次校验
                if self.check_days > 0 and not self._is_within_days(msg.get("Date", ""), self.check_days):
                    skipped += 1
                    continue

                # 遍历附件
                attachments_found = False
                for part in msg.walk():
                    cd = part.get("Content-Disposition", "")
                    if not cd.startswith("attachment"):
                        continue

                    attachments_found = True
                    filename = decode_str(part.get_filename())
                    if not filename:
                        continue

                    if not any(filename.lower().endswith(ext) for ext in self.allow_exts):
                        continue

                    try:
                        payload = part.get_payload(decode=True)
                        if payload is None:
                            continue
                        # 尝试根据主题生成标准化文件名
                        final_name = self._rename_by_subject(filename, subject)
                        save_path = self._save_file(final_name, payload, exist_files)
                        if save_path:
                            downloaded += 1
                            display = final_name if final_name != filename else filename
                            if save_callback:
                                save_callback(f"✅ 下载成功: {display}", display)
                            self._update_status(f"✅ {display} → {save_path}")
                    except Exception as e:
                        self._update_status(f"⚠️ 下载失败: {filename} — {e}")

                if not attachments_found and save_callback:
                    save_callback(f"📭 无附件: {subject[:50]}", "")

            except Exception as e:
                self._update_status(f"⚠️ 处理邮件失败: {e}")
                skipped += 1

            processed += 1
            if self.progress_callback:
                self.progress_callback(processed, total)

        self.disconnect()
        self._update_status(f"🎉 完成！下载 {downloaded} 个，跳过 {skipped} 个")
        return downloaded, skipped

    # ---- 客户端过滤辅助（参考 cmb_bill_downloader.py） ----

    # 广发银行主题匹配正则（内置）
    GDB_SUBJECT_PATTERNS = [
        r"广发信用卡.*?(\d{4})年(\d{1,2})月.*?对账单",  # 匹配：广发信用卡2017年12月个人补寄对账单
        r"广发.*?信用卡.*?账单",
        r"对账单",
    ]

    def _is_sender_matched(self, sender: str) -> bool:
        """发件人匹配，支持三种模式：
        1. 邮箱子串匹配（大小写不敏感）
        2. 银行中文名/简称 → 映射邮箱后再匹配
        3. 银行域名关键字匹配（如输入 cgbchina 匹配 xxx@cgbchina.com.cn）
        """
        if not self.sender:
            return True
        keyword = self.sender.strip().lower()

        # 1. 直接子串匹配（输入的是邮箱地址或邮箱的一部分）
        if keyword in sender.lower():
            return True

        # 2. 银行中文名/简称映射
        if keyword in self._BANK_SENDER_MAP:
            mapped_email = self._BANK_SENDER_MAP[keyword].lower()
            if mapped_email in sender.lower():
                return True

        # 3. 域名关键字匹配（输入 cgbchina 可匹配 xxx@cgbchina.com.cn）
        if "@" not in keyword and keyword in sender.lower().split("@")[-1]:
            return True

        return False

    def _is_subject_matched(self, subject: str) -> bool:
        """主题匹配，支持三种模式：
        1. 广发银行内置正则（发件人含 cgbchina 时自动应用）
        2. 用户正则模式（含 .*? / ( ) / \d 等正则语法）→ re.search
        3. 纯文本模式（普通关键词）→ 大小写不敏感子串匹配
        无用户关键词时，自动使用 DEFAULT_SUBJECT_KEYWORDS 过滤。
        """
        # 广发银行自动匹配
        if self.sender and "cgbchina" in self.sender.lower():
            for pattern in self.GDB_SUBJECT_PATTERNS:
                try:
                    if re.search(pattern, subject, re.IGNORECASE):
                        return True
                except re.error:
                    pass

        # 确定使用的关键词列表：用户关键词优先，否则用默认账单关键词
        keywords = self.subject_keywords if self.subject_keywords else self.DEFAULT_SUBJECT_KEYWORDS
        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            # 判断是否为正则：含正则特殊字符（排除纯中文/普通字符）
            if re.search(r'[.*+?()\[\]{}|^$\\]', kw):
                try:
                    if re.search(kw, subject, re.IGNORECASE):
                        return True
                except re.error:
                    # 正则语法错误，回退到子串匹配
                    if kw.lower() in subject.lower():
                        return True
            else:
                if kw.lower() in subject.lower():
                    return True
        return False

    @staticmethod
    def _extract_year_month(subject: str) -> tuple:
        """从主题中提取年月，如 '广发信用卡2017年12月对账单' → (2017, 12)"""
        m = re.search(r'(\d{4})年(\d{1,2})月', subject)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None, None

    def _rename_by_subject(self, original_filename: str, subject: str) -> str:
        """根据主题提取年月，生成标准化文件名（如：XX银行_2017年12月账单.pdf）。
        提取失败时返回原始文件名。
        """
        year, month = self._extract_year_month(subject)
        if year and month:
            ext = os.path.splitext(original_filename)[1] or ".pdf"
            # 从发件人取银行简称
            bank = "账单"
            if self.sender:
                # 从发件人邮箱提取域名作为银行标识
                parts = self.sender.split("@")
                if len(parts) > 1:
                    domain = parts[1].lower().split(".")[0]
                    # 常见银行域名映射
                    domain_map = {
                        "cgbchina": "广发银行",
                        "cmbchina": "招商银行",
                        "ccb": "建设银行",
                        "icbc": "工商银行",
                        "abchina": "农业银行",
                        "boc": "中国银行",
                        "spdb": "浦发银行",
                        "cib": "兴业银行",
                        "cmbc": "民生银行",
                        "cebbank": "光大银行",
                        "citic": "中信银行",
                        "cgb": "广发银行",
                        "comm": "交通银行",
                        "psbc": "邮储银行",
                    }
                    bank = domain_map.get(domain, domain)
            return f"{bank}_{year}年{month:02d}月账单{ext}"
        return original_filename

    @staticmethod
    def _is_within_days(date_str: str, days: int) -> bool:
        """客户端日期校验（IMAP SINCE 只精确到天，此处做二次确认）"""
        if not days or days <= 0:
            return True
        try:
            msg_date = parsedate_to_datetime(date_str)
            cutoff = datetime.now(msg_date.tzinfo) - timedelta(days=days)
            return msg_date >= cutoff
        except Exception:
            return True  # 解析失败则保留

    def _existing_files(self) -> set:
        """获取保存目录中已有文件名集合"""
        if os.path.isdir(self.save_dir):
            return set(os.listdir(self.save_dir))
        return set()

    def _save_file(self, filename: str, payload: bytes, exist_files: set) -> str:
        """保存附件到本地，跳过已存在文件，返回文件路径"""
        os.makedirs(self.save_dir, exist_ok=True)
        if filename in exist_files:
            self._update_status(f"   ⏭ 已存在: {filename}")
            return ""
        save_path = os.path.join(self.save_dir, filename)
        # 同名不同内容时加序号
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            filename = f"{base}_{counter}{ext}"
            save_path = os.path.join(self.save_dir, filename)
            counter += 1
        with open(save_path, "wb") as f:
            f.write(payload)
        exist_files.add(filename)
        return save_path

    def disconnect(self) -> None:
        """断开连接"""
        if self._mail:
            try:
                self._mail.close()
                self._mail.logout()
                self._update_status("已断开连接")
            except Exception:
                pass
            self._mail = None
            self._connected = False