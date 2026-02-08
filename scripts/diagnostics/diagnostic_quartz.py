import Quartz
import json

def list_windows_quartz():
    # kCGWindowListOptionOnScreenOnly = 1
    # kCGWindowListExcludeDesktopElements = 16
    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    
    results = []
    for window in window_list:
        name = window.get(Quartz.kCGWindowOwnerName, 'Unknown')
        title = window.get(Quartz.kCGWindowName, 'No Title')
        w_id = window.get(Quartz.kCGWindowNumber, 'No ID')
        pid = window.get(Quartz.kCGWindowOwnerPID, 'No PID')
        results.append({
            "owner": name,
            "title": title,
            "id": w_id,
            "pid": pid
        })
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    list_windows_quartz()
