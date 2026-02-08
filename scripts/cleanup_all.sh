#!/bin/bash

echo "🧹 Starting comprehensive project cleanup..."

# 1. Create directory structure for organization
mkdir -p scripts/verification
mkdir -p scripts/diagnostics
mkdir -p scripts/archive

# 2. Delete temporary logs and data dumps from Root
echo "🗑️  Deleting logs and temporary JSON dumps..."
rm -f *.log
rm -f *.json  # Be careful, but root usually doesn't have config json except pyproject.toml is toml. 
# Wait, check if there are any critical json files in root. 
# valid ones: audit_report.json (generated), full_scan_*.json (temp), wechat_scan_*.json (temp).
# All root *.json seem to be temp dumps.
rm -f *.png   # Screenshots

# 3. Delete temporary logs from scripts/
rm -f scripts/*.log

# 4. Move Verification/Test Scripts from Root to scripts/verification/
echo "📦 Moving root verification scripts to scripts/verification/..."
mv verify_*.py scripts/verification/ 2>/dev/null
mv stress_test.py scripts/verification/ 2>/dev/null
mv test_*.py scripts/verification/ 2>/dev/null
# Note: There are existing tests in tests/, but these root ones seem different. 
# Keeping them separate for now to avoid breaking imports in tests/.

# 5. Move Diagnostic Scripts to scripts/diagnostics/
echo "📦 Moving diagnostic scripts to scripts/diagnostics/..."
mv scripts/diagnostic_*.py scripts/diagnostics/ 2>/dev/null

# 6. Delete Obsolete/Temporary Scripts
echo "🗑️  Deleting obsolete scripts..."
# Root
rm -f debug_loop.py
rm -f debug_telegram.py
rm -f get_chat_id.py
rm -f send_wechat_msg.py # Old root script if it exists
rm -f send_wechat_v2.py  # Old root script if it exists

# Scripts/
rm -f scripts/automate_wechat.py
rm -f scripts/automate_wechat_final.py
rm -f scripts/automate_wechat_keyboard_pure.py
rm -f scripts/automate_wechat_now.py
rm -f scripts/automate_wechat_precise.py
rm -f scripts/automate_wechat_strict.py
rm -f scripts/automate_wechat_strict_final.py
rm -f scripts/send_danmaku.py
rm -f scripts/send_wechat_msg.py
rm -f scripts/send_wechat_v2.py

# 7. Preserve Core Production Scripts
# scripts/smart_send.py
# scripts/manage_contacts.py
# scripts/contacts.json
# scripts/automate_wechat_keyboard_final.py
# scripts/automate_telegram_keyboard_final.py

echo "✨ Cleanup complete! Root directory should be clean."
ls -F
echo "--------------------------------"
ls -F scripts/
