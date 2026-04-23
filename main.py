# main.py — 程序入口
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("main")

if __name__ == "__main__":
    logger.info("启动账单附件下载器...")
    from main_window import main
    main()
