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

from nanobot.agent.tools.base import Tool, ToolResult

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
            "confirm": {
                "type": "boolean",
                "description": "确认执行截图相关操作。",
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

    def __init__(self, confirm_mode: str = "warn") -> None:
        self._confirm_mode = confirm_mode
        self._confirm_actions = {"capture_screen", "look_at_screen"}

    @property
    def confirm_mode(self) -> str:
        """Override base property to return instance value."""
        return self._confirm_mode

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        if platform.system() != "Darwin":
            return ToolResult(success=False, output="Error: This tool only works on macOS.")

        if not (Quartz and Vision and NSURL):
            return ToolResult(success=False, output="Error: 'pyobjc-framework-Vision' and 'pyobjc-framework-Quartz' are required for this tool.")

        try:
            # Type safety: Handled by ToolExecutor

            confirm = bool(kwargs.get("confirm"))
            warning: str | None = None
            if action in self._confirm_actions and not confirm:
                if self.confirm_mode == "require":
                    return ToolResult(
                        success=False,
                        output="Confirmation required: re-run with confirm=true.",
                        requires_user_confirmation=True,
                    )
                if self.confirm_mode == "warn":
                    warning = "Warning: action executed without confirm=true."

            app_name: str | None = kwargs.get("app_name")
            frontmost_info = ""
            if action in ["capture_screen", "look_at_screen"]:
                # 自动检测当前前台应用，辅助 AI 进行环境感知 (隔离异常)
                try:
                    from nanobot.agent.tools.mac import MacTool
                    tester = MacTool()
                    app_info = tester.get_frontmost_app_info()
                    frontmost_info = f"Current Frontmost App Context: {app_info}\n"
                except Exception as e:
                    # 不影响主功能的 OCR/截图流程
                    logger.warning(f"Failed to get frontmost app context for vision: {e}")

            result = ""
            if action == "recognize_text":
                image_path = kwargs.get("image_path")
                if not image_path:
                    return ToolResult(success=False, output="Error: 'image_path' (绝对路径) 是 recognize_text 操作所必需的。")
                result = self._recognize_text(image_path)
            elif action == "capture_screen":
                result = self._capture_screen(app_name)
            elif action == "look_at_screen":
                path = self._capture_screen(app_name)
                if path.startswith("Error"):
                    result = path
                else:
                    result = self._recognize_text(path)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")

            # 合并元数据
            final_output = f"{frontmost_info}{result}" if frontmost_info else result
            if warning:
                final_output = f"{warning}\n{final_output}"
            
            is_error = "Error" in final_output or "Vision Error" in final_output
            return ToolResult(
                success=not is_error,
                output=final_output,
                remedy="请检查系统屏幕录制权限是否已开启，或图片路径是否有效。" if is_error else None
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Mac Vision Error: {str(e)}")

    def _get_window_id(self, app_name: str) -> str | None:
        """Use Quartz to get the window ID of the given app bypass permissions."""
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        
        if not window_list:
            return None

        # Try exact match first, then fuzzy
        app_name_lower = app_name.lower()
        
        # 1. Look for matching owner name
        for window in window_list:
            owner = str(window.get(Quartz.kCGWindowOwnerName, "")).lower()
            if app_name_lower in owner or owner in app_name_lower:
                return str(window.get(Quartz.kCGWindowNumber))
        
        if "bridge" in app_name_lower or "electron" in app_name_lower:
            for window in window_list:
                owner = str(window.get(Quartz.kCGWindowOwnerName, "")).lower()
                if "bridge" in owner or "electron" in owner:
                    return str(window.get(Quartz.kCGWindowNumber))

        # 3. Last resort: just return the first on-screen window (likely frontmost)
        return str(window_list[0].get(Quartz.kCGWindowNumber))

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

        image_url = NSURL.fileURLWithPath_(image_path)  # pyre-ignore[16]
        if not image_url:
            return f"Error: Could not create NSURL from {image_path}"

        # Try to load as NSImage first to verify validity
        from AppKit import NSImage
        ns_image = NSImage.alloc().initWithContentsOfURL_(image_url)  # pyre-ignore[16]
        if not ns_image or not ns_image.isValid():  # pyre-ignore[16]
             return f"Error: Invalid image file (NSImage failed to load)"
             
        # Vision handler
        request_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(  # pyre-ignore[16]
            image_url, None
        )

        request = Vision.VNRecognizeTextRequest.alloc().init()  # pyre-ignore[16]
        # Set fast for now to test, accurate later
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)  # pyre-ignore[16]
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
