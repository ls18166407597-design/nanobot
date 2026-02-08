import subprocess

script = '''
tell application "System Events"
    set res to ""
    set plist to every process whose background only is false
    repeat with p in plist
        set pName to name of p
        try
            set wList to every window of p
            repeat with w in wList
                set wTitle to title of w
                set wVisible to visible of w
                set res to res & pName & "|" & wTitle & "|" & (wVisible as string) & "\n"
            end repeat
        on error
            # Some processes might not support window access
        end try
    end repeat
    return res
end tell
'''

try:
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        print("--- Windows List ---")
        print(result.stdout.strip())
    else:
        print(f"Error: {result.stderr.strip()}")
except Exception as e:
    print(f"Exception: {str(e)}")
