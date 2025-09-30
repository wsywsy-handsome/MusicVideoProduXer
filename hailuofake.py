import os
import time
import base64
import mimetypes
from pathlib import Path


class HailuoVideoGenerator:
    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/v1", output_dir: str = "output"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.cur_dir = Path(__file__).parent
        self.output_dir = Path(output_dir)
        if not self.output_dir.is_absolute():
            self.output_dir = self.cur_dir / self.output_dir

        # 创建目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def image_to_data_url(image_path: str) -> str:
        """本地图片转 base64 Data URL"""
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        with open(image_path, "rb") as f:
            base64_str = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{base64_str}"

    def invoke_text_to_video(self, prompt: str, model: str = "MiniMax-Hailuo-02",
                             duration: int = 6, resolution: str = "768P") -> dict:
        """通过文本发起视频生成任务，返回构造好的请求体"""
        payload = {
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }
        return payload

    def invoke_image_to_video(self, prompt: str, image_path: str,
                              model: str = "MiniMax-Hailuo-02",
                              duration: int = 6, resolution: str = "768P") -> dict:
        """通过本地首帧图像+文本描述发起视频生成任务，返回构造好的请求体"""
        # img_base64 = self.image_to_data_url(image_path)
        img_base64 = image_path
        payload = {
            "prompt": prompt,
            "first_frame_image": img_base64,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }
        return payload

    def query_task_status(self, task_id: str, poll_interval: int = 10) -> dict:
        """轮询任务状态请求参数（不会真正发请求）"""
        return {
            "url": f"{self.base_url}/query/video_generation",
            "headers": self.headers,
            "params": {"task_id": task_id},
            "poll_interval": poll_interval,
        }

    def fetch_video(self, file_id: str, save_path: str) -> dict:
        """获取下载链接请求参数（不会真正下载视频）"""
        return {
            "params": {"file_id": file_id},
            "save_path": str(Path(save_path)),
        }
