import logging
import platform
import json
from typing import Any, List, Dict

try:
    import Quartz
    import Vision
    import AppKit
    from Cocoa import NSURL
except ImportError:
    Quartz = None
    Vision = None
    AppKit = None
    NSURL = None

from nanobot.agent.tools.base import Tool

logger = logging.getLogger(__name__)

class MacVisionTool(Tool):
    """Tool for native macOS OCR using the Vision framework."""

    name = "mac_vision"
    description = """
    使用 macOS 原生 Vision 框架进行内容感知。
    功能：
    - capture_screen: 截取当前全屏并返回临时文件路径。
    - recognize_text: 识别指定图片文件中的文字及其位置。
    - look_at_screen: 自动截屏并进行全屏 OCR 识别，返回识别到的文字和位置。
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["recognize_text", "capture_screen", "look_at_screen"],
                "description": "要执行的操作。",
            },
            "image_path": {
                "type": "string",
                "description": "图片文件的绝对路径 (recognize_text 时必填)。",
            },
            "app_name": {
                "type": "string",
                "description": "指定要截取的应用程序窗口名称 (可选)。如果提供，将仅截取该程序的首个窗口。",
            },
        },
        "required": ["action"],
    }

    async def execute(self, action: str, **kwargs: Any) -> str:
        if platform.system() != "Darwin":
            return "Error: This tool only works on macOS."

        if not (Quartz and Vision and NSURL):
            return "Error: 'pyobjc-framework-Vision' and 'pyobjc-framework-Quartz' are required."

        try:
            app_name: str | None = kwargs.get("app_name")
            if action == "recognize_text":
                image_path = kwargs.get("image_path")
                if not image_path:
                    return "Error: 'image_path' (绝对路径) 是 recognize_text 操作所必需의。"
                return self._recognize_text(image_path)
            elif action == "capture_screen":
                return self._capture_screen(app_name)
            elif action == "look_at_screen":
                path = self._capture_screen(app_name)
                if path.startswith("Error"):
                    return path
                return self._recognize_text(path)
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Mac Vision Error: {str(e)}"

    def _get_window_id(self, app_name: str) -> str | None:
        """Use AppleScript to get the window ID of the given app."""
        import subprocess
        script = f'''
        tell application "System Events"
            if exists (process "{app_name}") then
                tell process "{app_name}"
                    if exists window 1 then
                        return id of window 1
                    end if
                end tell
            end if
        end tell
        '''
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode == 0:
                w_id = result.stdout.strip()
                return w_id if w_id else None
            return None
        except:
            return None

    def _capture_screen(self, app_name: str | None = None) -> str:
        import os
        import subprocess
        import tempfile
        from datetime import datetime

        # 使用临时文件存储截屏
        tmp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nanobot_screenshot_{timestamp}.png"
        path = os.path.join(tmp_dir, filename)

        try:
            cmd = ["screencapture", "-x"]
            
            if app_name:
                window_id = self._get_window_id(app_name)
                if window_id:
                    cmd.extend(["-l", window_id])
                else:
                    return f"Error: Could not find a visible window for application '{app_name}'."
            
            cmd.append(path)
            subprocess.run(cmd, check=True)
            return path
        except Exception as e:
            return f"Error capturing screen: {str(e)}"

    def _recognize_text(self, image_path: str) -> str:
        # Verify file exists
        import os
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"

        image_url = NSURL.fileURLWithPath_(image_path)
        if not image_url:
            return f"Error: Could not create NSURL from {image_path}"

        # Try to load as NSImage first to verify validity
        from AppKit import NSImage
        ns_image = NSImage.alloc().initWithContentsOfURL_(image_url)
        if not ns_image or not ns_image.isValid():
             return f"Error: Invalid image file (NSImage failed to load)"
             
        # Vision handler
        request_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
            image_url, None
        )

        request = Vision.VNRecognizeTextRequest.alloc().init()
        # Set fast for now to test, accurate later
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setUsesLanguageCorrection_(True)
        # request.setrecognitionLanguages_(['zh-Hans', 'en-US']) # Optional

        success, error = request_handler.performRequests_error_([request], None)
        if not success:
            return f"Vision Error: {error}"

        observations = request.results()
        results = []

        # Coordinate system note:
        # Vision uses normalized coordinates (0,0 is bottom-left, 1,1 is top-right).
        # We might want to return these raw or convert them later.
        # For now, returning raw normalized coordinates.

        for obs in observations:
            candidates = obs.topCandidates_(1)
            if candidates:
                text = candidates[0].string()
                # Bounding box is normalized (x, y, w, h)
                box = obs.boundingBox()
                
                # Convert NSRect to list/dict
                bbox = {
                    "x": box.origin.x,
                    "y": box.origin.y,
                    "w": box.size.width,
                    "h": box.size.height
                }
                
                results.append({
                    "text": text,
                    "bbox": bbox,
                    "confidence": candidates[0].confidence()
                })

        return json.dumps(results, indent=2, ensure_ascii=False)
