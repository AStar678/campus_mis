#!/usr/bin/env python3
"""快速恢复脚本：将备份数据恢复到 MySQL。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reset_db import restore_from_backup
restore_from_backup("/Users/aoxiang/Desktop/校园MIS/campus_mis/backups/reset_20260617_105527")
