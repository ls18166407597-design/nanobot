import subprocess

# This script tries multiple ways to access window info to see what works
script = '''
set out to "--- Diagnostics ---\n"
tell application "System Events"
    try
        set frontProcess to first process whose frontmost is true
        set pName to name of frontProcess
        set out to out & "Frontmost Name: " & pName & "\n"
        
        try
            set wCount to count of windows of frontProcess
            set out to out & "Window Count: " & (wCount as string) & "\n"
            
            if wCount > 0 then
                set wTitle to title of window 1 of frontProcess
                set wID to id of window 1 of frontProcess
                set out to out & "Window 1 Title: " & wTitle & "\n"
                set out to out & "Window 1 ID: " & (wID as string) & "\n"
            end if
        on error e
            set out to out & "Error accessing window properties: " & e & "\n"
        end try
    on error e
        set out to out & "Error accessing frontmost process: " & e & "\n"
    end try
end tell
return out
'''

try:
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"CLI Error: {result.stderr.strip()}")
except Exception as e:
    print(f"Exception: {str(e)}")
