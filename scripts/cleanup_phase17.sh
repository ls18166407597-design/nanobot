#!/bin/bash

# Clean up temporary test scripts from Phase 17
rm -f scripts/automate_wechat_final.log
rm -f scripts/automate_wechat_final_run.log
rm -f scripts/automate_wechat_final_run_v2.log
rm -f scripts/automate_wechat_final_run_v3.log
rm -f scripts/automate_wechat_final_run_v4.log
rm -f scripts/automate_wechat_final_run_v5.log
rm -f scripts/automate_wechat_final_run_v6.log
rm -f scripts/automate_wechat_final_run_v7.log
rm -f scripts/automate_wechat_keyboard_pure.log
rm -f scripts/automate_wechat_keyboard_final.log
rm -f scripts/automate_telegram_keyboard_final.log

# Remove intermediate Python scripts
rm -f scripts/automate_wechat_keyboard_pure.py
rm -f scripts/automate_wechat_strict_final.py
rm -f scripts/automate_wechat_now.py
rm -f scripts/automate_wechat_precise.py
rm -f scripts/automate_wechat_strict.py

# Keep the core production scripts:
# - scripts/smart_send.py
# - scripts/manage_contacts.py
# - scripts/contacts.json
# - scripts/automate_wechat_keyboard_final.py
# - scripts/automate_telegram_keyboard_final.py

echo "✅ Cleanup complete. Core production scripts preserved."
